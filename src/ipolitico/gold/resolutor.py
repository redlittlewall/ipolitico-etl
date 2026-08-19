"""Resolução de entidade política (hub de identidade ``politico_id``).

Funções **puras e vetorizadas** (Polars) da issue 01 — camada Gold de
identidade. Recebem DataFrames Silver e produzem as tabelas ``politicos``,
``politicos_aliases`` e ``resolucoes`` (trilha de auditoria). Nenhuma I/O aqui;
o builder (``entidade_canonica.py``) orquestra leitura/escrita.

Regras de resolução (hub-and-spoke, CPF como chave-mestre onde existe — só na
Câmara):
  1. Determinística primeiro: CPF exato (``deputados_detalhe``) e chaves
     naturais diretas (``id_deputado``/``codigo``/``codSenador``).
  2. Fuzzy **conservador** para o cruzamento Câmara↔Senado: nome normalizado +
     DN + UF (alta) ou nome + UF (média); só merge **não-ambíguo**. Ambíguo ou
     divergente vira ``resolucoes`` ``candidata_revisao`` (baixa), sem merge.
  3. Servidores do Senado só viram aliases quando casados com um senador por
     nome (o hub fica no patamar de políticos, não de servidores).

Âncora ``politico_id``: ``pol_camara_{id}`` quando existe registro na Câmara
(prioriza o membro com CPF do detalhe; senão o menor ``id`` do cluster), senão
``pol_senado_{codigo}``.
"""

from __future__ import annotations

import polars as pl

# Namespaces de alias por fonte (ids naturais disjuntos).
FONTE_CAMARA = "camara"
FONTE_SENADO = "senado"
FONTE_SERVIDOR = "senado_servidor"

# Métodos de resolução.
METODO_CPF = "cpf_exato"
METODO_CHAVE = "chave_natural"
METODO_FUZZY_DN = "nome_normalizado_dn_uf"
METODO_FUZZY_UF = "nome_normalizado_uf"
METODO_FUZZY_AMBIGUO = "fuzzy_ambiguo"
METODO_ROSTER = "roster_servidor"
METODO_ROSTER_AMBIGUO = "roster_servidor_ambiguo"

# Níveis de confiança (auditáveis).
CONF_ALTA = "alta"
CONF_MEDIA = "media"
CONF_BAIXA = "baixa"

# Prioridade de método na dedup de aliases por ``(fonte, id_natural)``
# (menor vence): CPF > fuzzy > chave natural > roster.
_METODO_PRIORIDADE = {
    METODO_CPF: 0,
    METODO_FUZZY_DN: 1,
    METODO_FUZZY_UF: 2,
    METODO_CHAVE: 3,
    METODO_ROSTER: 4,
}

ALIAS_SCHEMA = {
    "fonte": pl.String,
    "id_natural": pl.Int64,
    "politico_id": pl.String,
    "metodo": pl.String,
    "confianca": pl.String,
    "_source_url": pl.String,
}

RESOLUCAO_SCHEMA = {
    "fonte_origem": pl.String,
    "id_origem": pl.Int64,
    "fonte_destino": pl.String,
    "id_destino": pl.Int64,
    "metodo": pl.String,
    "confianca": pl.String,
    "justificativa": pl.String,
    "_source_url": pl.String,
}

POLITICO_SCHEMA = {
    "politico_id": pl.String,
    "nome_civil": pl.String,
    "cpf": pl.String,
    "data_nascimento": pl.String,
    "uf": pl.String,
    "_source_url": pl.String,
}


def normalizar_nome(expr: pl.Expr) -> pl.Expr:
    """Normaliza um nome para comparação (upper, sem acento, espaços colapsados).

    Args:
        expr: Expressão de coluna string com o nome bruto.

    Returns:
        Expressão com o nome normalizado; ``null`` preserva ``null``.
    """
    return (
        expr.str.to_uppercase()
        .str.normalize("NFKD")
        .str.replace_all(r"\p{Mn}", "")
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
    )


def _politico_id_camara(id_expr: pl.Expr) -> pl.Expr:
    """Monta a âncora ``pol_camara_{id}`` a partir de uma expressão de id.

    Args:
        id_expr: Expressão com o ``id`` da Câmara (``Int64``).

    Returns:
        Expressão string ``pol_camara_{id}``.
    """
    return pl.format("pol_camara_{}", id_expr)


def _politico_id_senado(codigo_expr: pl.Expr) -> pl.Expr:
    """Monta a âncora ``pol_senado_{codigo}`` a partir de uma expressão de código.

    Args:
        codigo_expr: Expressão com o ``codigo`` do Senado (``Int64``).

    Returns:
        Expressão string ``pol_senado_{codigo}``.
    """
    return pl.format("pol_senado_{}", codigo_expr)


def _aliases_vazio() -> pl.DataFrame:
    """DataFrame ``politicos_aliases`` vazio com o schema contratual.

    Returns:
        DataFrame vazio com o schema de ``ALIAS_SCHEMA`` (0 linhas).
    """
    return pl.DataFrame(schema=ALIAS_SCHEMA)


def _resolucoes_vazio() -> pl.DataFrame:
    """DataFrame ``resolucoes`` vazio com o schema contratual.

    Returns:
        DataFrame vazio com o schema de ``RESOLUCAO_SCHEMA`` (0 linhas).
    """
    return pl.DataFrame(schema=RESOLUCAO_SCHEMA)


def resolve_por_cpf(deputados_detalhe: pl.DataFrame) -> pl.DataFrame:
    """Aliases Câmara a partir de CPF íntegro (chave-mestre quando disponível).

    Args:
        deputados_detalhe: Silver ``deputados_detalhe`` com ``id``, ``cpf`` e
            ``_source_url``.

    Returns:
        DataFrame ``politicos_aliases`` (fonte=camara, método ``cpf_exato``,
        confiança alta) com 0..n linhas; vazio (schema) quando a entrada é
        vazia ou ``cpf`` é todo nulo.
    """
    if deputados_detalhe.is_empty():
        return _aliases_vazio()
    cpf = pl.col("cpf").cast(pl.String)
    df = deputados_detalhe.filter(cpf.is_not_null() & (cpf.str.len_chars() > 0))
    if df.is_empty():
        return _aliases_vazio()
    return df.select(
        pl.lit(FONTE_CAMARA).alias("fonte"),
        pl.col("id").cast(pl.Int64).alias("id_natural"),
        _politico_id_camara(pl.col("id")).alias("politico_id"),
        pl.lit(METODO_CPF).alias("metodo"),
        pl.lit(CONF_ALTA).alias("confianca"),
        pl.col("_source_url"),
    )


def resolve_por_chaves_naturais(deputados: pl.DataFrame, senadores: pl.DataFrame) -> pl.DataFrame:
    """Aliases por chaves naturais diretas das duas casas.

    ``id_deputado``↔``deputados.id`` (fonte=camara) e ``codigo_senador``
    (``codigo``/``codSenador``, mesmo espaço de ids — fonte=senado). Aplica-se
    também o snapshot mais recente por entidade (maior legislatura).

    Args:
        deputados: Silver ``deputados`` com ``id``, ``idLegislatura``.
        senadores: Silver ``senadores`` com ``codigo``, ``segunda_legislatura``.

    Returns:
        DataFrame ``politicos_aliases`` (método ``chave_natural``, confiança
        alta); vazio (schema) quando ambos os lados são vazios.
    """
    camara = (
        deputados.sort("idLegislatura", descending=True)
        .unique(subset=["id"])
        .select(
            pl.lit(FONTE_CAMARA).alias("fonte"),
            pl.col("id").cast(pl.Int64).alias("id_natural"),
            _politico_id_camara(pl.col("id")).alias("politico_id"),
            pl.lit(METODO_CHAVE).alias("metodo"),
            pl.lit(CONF_ALTA).alias("confianca"),
            pl.col("_source_url"),
        )
    )
    senado = (
        senadores.sort("segunda_legislatura", descending=True)
        .unique(subset=["codigo"])
        .select(
            pl.lit(FONTE_SENADO).alias("fonte"),
            pl.col("codigo").cast(pl.Int64).alias("id_natural"),
            _politico_id_senado(pl.col("codigo")).alias("politico_id"),
            pl.lit(METODO_CHAVE).alias("metodo"),
            pl.lit(CONF_ALTA).alias("confianca"),
            pl.col("_source_url"),
        )
    )
    if camara.is_empty() and senado.is_empty():
        return _aliases_vazio()
    return pl.concat([camara, senado], how="vertical")


def resolve_fuzzy_camara_senado(
    deputados: pl.DataFrame,
    deputados_detalhe: pl.DataFrame,
    senadores: pl.DataFrame,
    senadores_detalhe: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Resolução fuzzy Câmara↔Senado (nome + DN + UF), auditável.

    Só realiza merge **não-ambíguo**: o nome normalizado deve identificar
    exatamente 1 deputado e 1 senador. Com UF casando e DN presente nos dois
    lados → confiança alta (``nome_normalizado_dn_uf``); sem DN (padrão atual,
    ``senadores_detalhe`` não ingerido) → média (``nome_normalizado_uf``).
    Nome com múltiplos candidatos de qualquer lado, UF divergente ou DN
    divergente vira ``resolucoes`` (confiança baixa, ``candidata_revisao``),
    sem merge.

    Args:
        deputados: Silver ``deputados`` (``id``, ``nome``, ``uf``).
        deputados_detalhe: Silver ``deputados_detalhe`` (``id``, ``dataNascimento``).
        senadores: Silver ``senadores`` (``codigo``, ``nome``, ``uf``).
        senadores_detalhe: Silver ``senadores_detalhe`` (``codigo``,
            ``data_nascimento``) quando ingerido; ``None`` degrada para nome+UF.

    Returns:
        Tupla ``(aliases, resolucoes)``. Aliases só com merges confirmados
        (fonte=senado, ``politico_id`` = âncora da Câmara); ambos os lados
        podem ser vazios (schema) quando não há merge.
    """
    dep = (
        deputados.sort("idLegislatura", descending=True)
        .unique(subset=["id"])
        .with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
        .select("id", "nome_norm", "uf", "_source_url")
    )
    dep = _com_assinatura_nascimento(dep, deputados_detalhe, "id", "dataNascimento")

    sen = (
        senadores.sort("segunda_legislatura", descending=True)
        .unique(subset=["codigo"])
        .with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
        .select("codigo", "nome_norm", "uf", "_source_url")
    )
    sen = _com_assinatura_nascimento(sen, senadores_detalhe, "codigo", "data_nascimento")

    dep_counts = dep.group_by("nome_norm").agg(pl.len().alias("n_dep"))
    sen_counts = sen.group_by("nome_norm").agg(pl.len().alias("n_sen"))

    pares = (
        dep.join(sen, on="nome_norm", how="inner", suffix="_sen")
        .join(dep_counts, on="nome_norm")
        .join(sen_counts, on="nome_norm")
    )
    if pares.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    unico = (pl.col("n_dep") == 1) & (pl.col("n_sen") == 1)
    uf_ok = (
        pl.col("uf").is_not_null()
        & pl.col("uf_sen").is_not_null()
        & (pl.col("uf") == pl.col("uf_sen"))
    )
    dn_presente = (
        pl.col("dataNascimento").is_not_null()
        & pl.col("dataNascimento_sen").is_not_null()
    )
    dn_ok = dn_presente & (pl.col("dataNascimento") == pl.col("dataNascimento_sen"))
    dn_divergente = dn_presente & ~(
        pl.col("dataNascimento") == pl.col("dataNascimento_sen")
    )

    pares = pares.with_columns(
        pl.when(unico & uf_ok & dn_ok)
        .then(pl.lit(CONF_ALTA))
        .when(unico & uf_ok & dn_divergente)
        .then(pl.lit(CONF_BAIXA))
        .when(unico & uf_ok)
        .then(pl.lit(CONF_MEDIA))
        .otherwise(pl.lit(CONF_BAIXA))
        .alias("confianca"),
        pl.when(unico)
        .then(
            pl.when(dn_ok)
            .then(pl.lit(METODO_FUZZY_DN))
            .otherwise(pl.lit(METODO_FUZZY_UF))
        )
        .otherwise(pl.lit(METODO_FUZZY_AMBIGUO))
        .alias("metodo"),
        pl.when(~unico)
        .then(pl.lit("nome ambíguo — múltiplos candidatos; revisão humana"))
        .when(~uf_ok)
        .then(pl.lit("UF divergente ou ausente — não confirmado; revisão humana"))
        .when(dn_divergente)
        .then(pl.lit("DN divergente entre Câmara e Senado — revisão humana"))
        .when(dn_ok)
        .then(pl.lit("merge confirmado (nome + DN + UF)"))
        .otherwise(pl.lit("merge confirmado (nome + UF; DN ausente)"))
        .alias("justificativa"),
    )

    aliases = pares.filter(pl.col("confianca") != CONF_BAIXA).select(
        pl.lit(FONTE_SENADO).alias("fonte"),
        pl.col("codigo").cast(pl.Int64).alias("id_natural"),
        _politico_id_camara(pl.col("id")).alias("politico_id"),
        pl.col("metodo"),
        pl.col("confianca"),
        pl.col("_source_url_sen").alias("_source_url"),
    )

    resolucoes = pares.select(
        pl.lit(FONTE_SENADO).alias("fonte_origem"),
        pl.col("codigo").cast(pl.Int64).alias("id_origem"),
        pl.lit(FONTE_CAMARA).alias("fonte_destino"),
        pl.col("id").cast(pl.Int64).alias("id_destino"),
        pl.col("metodo"),
        pl.col("confianca"),
        pl.col("justificativa"),
        pl.col("_source_url_sen").alias("_source_url"),
    )
    return aliases, resolucoes


def _com_assinatura_nascimento(
    df: pl.DataFrame,
    detalhe: pl.DataFrame | None,
    id_col: str,
    nasc_col: str,
) -> pl.DataFrame:
    """Anexa a data de nascimento ao DataFrame quando o detalhe está ingerido.

    Args:
        df: DataFrame base (já com ``id_col``).
        detalhe: DataFrame de detalhe com ``id_col`` e ``nasc_col``, ou ``None``.
        id_col: Nome da coluna de chave (``id`` ou ``codigo``).
        nasc_col: Nome da coluna de nascimento no detalhe.

    Returns:
        ``df`` com a coluna ``dataNascimento`` (String); quando o detalhe não
        existe, é vazio ou não tem a coluna, a coluna entra toda nula.
    """
    if (
        detalhe is None
        or detalhe.is_empty()
        or nasc_col not in detalhe.columns
    ):
        return df.with_columns(pl.lit(None, dtype=pl.String).alias("dataNascimento"))
    return df.join(
        detalhe.select(pl.col(id_col), pl.col(nasc_col).alias("dataNascimento")),
        on=id_col,
        how="left",
    )


def resolve_roster_servidor(
    servidores: pl.DataFrame,
    senadores: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Aliases ``senado_servidor`` (``sequencial``) para servidores do Senado.

    Casa o roster de servidores com os senadores por **nome normalizado**
    (o ``sequencial`` não é chave confiável entre roster e folha — pesquisa 09).
    Só merge não-ambíguo (nome → exatamente 1 servidor E 1 senador); confiança
    média (sem UF no roster). Ambíguo vira ``resolucoes`` (baixa).

    Args:
        servidores: Silver ``servidores`` (``sequencial``, ``nome``).
        senadores: Silver ``senadores`` (``codigo``, ``nome``).

    Returns:
        Tupla ``(aliases, resolucoes)``; aliases com fonte=senado_servidor e
        ``politico_id = pol_senado_{codigo}`` (reancorado depois pela Câmara
        quando aplicável).
    """
    if servidores.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    serv = (
        servidores.unique(subset=["sequencial"])
        .with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
        .select("sequencial", "nome_norm", "_source_url")
    )
    sen = (
        senadores.sort("segunda_legislatura", descending=True)
        .unique(subset=["codigo"])
        .with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
        .select("codigo", "nome_norm", "_source_url")
    )
    serv_counts = serv.group_by("nome_norm").agg(pl.len().alias("n_serv"))
    sen_counts = sen.group_by("nome_norm").agg(pl.len().alias("n_sen"))

    pares = (
        serv.join(sen, on="nome_norm", how="inner", suffix="_sen")
        .join(serv_counts, on="nome_norm")
        .join(sen_counts, on="nome_norm")
    )
    if pares.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    unico = (pl.col("n_serv") == 1) & (pl.col("n_sen") == 1)
    pares = pares.with_columns(
        pl.when(unico).then(pl.lit(CONF_MEDIA)).otherwise(pl.lit(CONF_BAIXA)).alias("confianca"),
        pl.when(unico).then(pl.lit(METODO_ROSTER)).otherwise(pl.lit(METODO_ROSTER_AMBIGUO)).alias("metodo"),
        pl.when(unico)
        .then(pl.lit("servidor casado com senador por nome (roster)"))
        .otherwise(pl.lit("nome ambíguo no roster — revisão humana"))
        .alias("justificativa"),
    )

    aliases = pares.filter(unico).select(
        pl.lit(FONTE_SERVIDOR).alias("fonte"),
        pl.col("sequencial").cast(pl.Int64).alias("id_natural"),
        _politico_id_senado(pl.col("codigo")).alias("politico_id"),
        pl.col("metodo"),
        pl.col("confianca"),
        pl.col("_source_url"),
    )
    resolucoes = pares.select(
        pl.lit(FONTE_SERVIDOR).alias("fonte_origem"),
        pl.col("sequencial").cast(pl.Int64).alias("id_origem"),
        pl.lit(FONTE_SENADO).alias("fonte_destino"),
        pl.col("codigo").cast(pl.Int64).alias("id_destino"),
        pl.col("metodo"),
        pl.col("confianca"),
        pl.col("justificativa"),
        pl.col("_source_url_sen").alias("_source_url"),
    )
    return aliases, resolucoes


def montar_ancoras(
    deputados: pl.DataFrame,
    deputados_detalhe: pl.DataFrame,
    senadores: pl.DataFrame,
    servidores: pl.DataFrame | None = None,
    senadores_detalhe: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Monta ``politicos`` + ``politicos_aliases`` + ``resolucoes`` completos.

    Combina as resoluções determinísticas e fuzzy, reancora os aliases de
    senador/servidor absorvidos por uma âncora da Câmara e deduplica aliases
    por ``(fonte, id_natural)`` com prioridade de método (CPF > fuzzy > chave
    > roster).

    Args:
        deputados: Silver ``deputados``.
        deputados_detalhe: Silver ``deputados_detalhe`` (pode ser vazio).
        senadores: Silver ``senadores``.
        servidores: Silver ``servidores`` (opcional; vazio/sem match → sem
            aliases de servidor).
        senadores_detalhe: Silver ``senadores_detalhe`` (opcional; melhora o
            fuzzy para alta confiança).

    Returns:
        Tupla ``(politicos, politicos_aliases, resolucoes)``; todas com o
        schema contratual, podendo ser vazias.
    """
    aliases_cpf = resolve_por_cpf(deputados_detalhe)
    aliases_chave = resolve_por_chaves_naturais(deputados, senadores)
    aliases_fuzzy, resolucoes_fuzzy = resolve_fuzzy_camara_senado(
        deputados, deputados_detalhe, senadores, senadores_detalhe
    )
    if servidores is not None and not servidores.is_empty():
        aliases_roster, resolucoes_roster = resolve_roster_servidor(servidores, senadores)
    else:
        aliases_roster, resolucoes_roster = _aliases_vazio(), _resolucoes_vazio()

    partes = [
        a for a in (aliases_cpf, aliases_chave, aliases_fuzzy, aliases_roster) if not a.is_empty()
    ]
    aliases = pl.concat(partes, how="vertical") if partes else _aliases_vazio()

    # Reancora senadores/servidores absorvidos pela Câmara para a âncora final.
    # Chave de reancoramento por fonte: senado → ``id_natural`` (o código);
    # senado_servidor → código extraído do próprio ``politico_id``.
    if not aliases.is_empty() and not aliases_fuzzy.is_empty():
        reancora = (
            aliases_fuzzy.filter(pl.col("fonte") == FONTE_SENADO)
            .select(
                pl.col("id_natural").cast(pl.String).alias("_codigo_key"),
                pl.col("politico_id"),
            )
            .unique(subset=["_codigo_key"])
        )
        if not reancora.is_empty():
            aliases = (
                aliases.with_columns(
                    pl.when(pl.col("fonte") == FONTE_SENADO)
                    .then(pl.col("id_natural").cast(pl.String))
                    .when(pl.col("fonte") == FONTE_SERVIDOR)
                    .then(pl.col("politico_id").str.extract(r"pol_senado_(\d+)"))
                    .otherwise(pl.lit(None, dtype=pl.String))
                    .alias("_codigo_key")
                )
                .join(reancora, on="_codigo_key", how="left")
                .with_columns(
                    pl.coalesce([pl.col("politico_id_right"), pl.col("politico_id")]).alias(
                        "politico_id"
                    )
                )
                .drop("_codigo_key", "politico_id_right")
            )

    if not aliases.is_empty():
        aliases = (
            aliases.with_columns(pl.col("metodo").replace_strict(_METODO_PRIORIDADE).alias("_prio"))
            .sort("_prio")
            .unique(subset=["fonte", "id_natural"], keep="first")
            .drop("_prio")
        )

    resolucoes = pl.concat([resolucoes_fuzzy, resolucoes_roster], how="vertical")
    if not resolucoes.is_empty():
        resolucoes = resolucoes.unique(
            subset=["fonte_origem", "id_origem", "fonte_destino", "id_destino"]
        )

    # ── Tabela politicos ────────────────────────────────────────────────────
    camara_people = (
        deputados.sort("idLegislatura", descending=True)
        .unique(subset=["id"])
        .select("id", "nome", "uf", "_source_url")
        .join(
            deputados_detalhe.select("id", "cpf", "dataNascimento", "nomeCivil", "ufNascimento")
            .unique(subset=["id"]),
            on="id",
            how="left",
        )
        .with_columns(
            _politico_id_camara(pl.col("id")).alias("politico_id"),
            pl.coalesce([pl.col("nomeCivil"), pl.col("nome")]).alias("nome_civil"),
            pl.col("dataNascimento").alias("data_nascimento"),
        )
        .select("politico_id", "nome_civil", "cpf", "data_nascimento", "uf", "_source_url")
    )

    # Só senadores que NÃO foram absorvidos pela Câmara são âncora própria.
    senado_final = (
        aliases.filter(pl.col("fonte") == FONTE_SENADO)
        .select("id_natural", "politico_id")
        .unique(subset=["id_natural"])
    )
    senado_people = (
        senadores.sort("segunda_legislatura", descending=True)
        .unique(subset=["codigo"])
        .select("codigo", "nome", "nome_completo", "uf", "_source_url")
        .join(senado_final, left_on="codigo", right_on="id_natural", how="left")
        .filter(
            pl.col("politico_id").is_not_null()
            & pl.col("politico_id").str.starts_with("pol_senado_")
        )
        .with_columns(
            pl.coalesce([pl.col("nome_completo"), pl.col("nome")]).alias("nome_civil"),
            pl.lit(None, dtype=pl.String).alias("cpf"),
            pl.lit(None, dtype=pl.String).alias("data_nascimento"),
        )
        .select("politico_id", "nome_civil", "cpf", "data_nascimento", "uf", "_source_url")
    )

    if camara_people.is_empty() and senado_people.is_empty():
        politicos = pl.DataFrame(schema=POLITICO_SCHEMA)
    else:
        politicos = pl.concat(
            [_politicos_conforme(camara_people), _politicos_conforme(senado_people)],
            how="vertical",
        )

    return politicos, aliases, resolucoes


def _politicos_conforme(df: pl.DataFrame) -> pl.DataFrame:
    """Garante o schema contratual de ``politicos`` (cast explícito por coluna).

    Os lados Câmara/Senado podem divergir em dtype quando a fonte tem coluna
    toda nula (ex.: ``cpf`` inferido como ``Null`` em vez de ``String``).

    Args:
        df: DataFrame com as colunas de ``politicos``.

    Returns:
        DataFrame com todas as colunas castadas para ``POLITICO_SCHEMA``.
    """
    return df.select(
        pl.col("politico_id").cast(pl.String),
        pl.col("nome_civil").cast(pl.String),
        pl.col("cpf").cast(pl.String),
        pl.col("data_nascimento").cast(pl.String),
        pl.col("uf").cast(pl.String),
        pl.col("_source_url").cast(pl.String),
    )
