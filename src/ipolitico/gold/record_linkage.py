"""Motor de Record Linkage e Resolução de Entidades Multi-Fonte (Issue 06).

Implementa algoritmos determinísticos e probabilísticos (Fellegi-Sunter) puramente
vetorizados em Polars para cruzamento entre parlamentares (Câmara, Senado), Executivo
(CGU/PEP) e a base eleitoral do TSE, resolvendo a identidade mestra (politico_id).
"""

from __future__ import annotations

import polars as pl

from ipolitico.core.metaphone_ptbr import metaphone_ptbr_expr

# Constantes de Métodos
METODO_CPF_EXATO = "cpf_exato"
METODO_CPF_MASCARADO = "cpf_mascarado_bloco"
METODO_METAPHONE_DN_UF = "metaphone_dn_uf"
METODO_METAPHONE_UF = "metaphone_uf"
METODO_HOMONIMO_AMBIGUO = "homonimo_ambiguo"

# Níveis de Confiança
CONF_ALTA = "alta"
CONF_MEDIA = "media"
CONF_BAIXA = "baixa"

# Schemas Contratuais
LINKAGE_ALIAS_SCHEMA = {
    "fonte": pl.String,
    "id_natural": pl.Int64,
    "politico_id": pl.String,
    "metodo": pl.String,
    "confianca": pl.String,
    "score": pl.Float64,
    "_source_url": pl.String,
}

AUDITORIA_RESOLUCAO_SCHEMA = {
    "fonte_origem": pl.String,
    "id_origem": pl.String,
    "fonte_destino": pl.String,
    "id_destino": pl.String,
    "metodo": pl.String,
    "confianca": pl.String,
    "score": pl.Float64,
    "justificativa": pl.String,
    "_source_url": pl.String,
}


def normalizar_cpf(expr: pl.Expr) -> pl.Expr:
    """Normaliza coluna de CPF removendo pontuação, sentinelas e formatando 11 dígitos.

    Args:
        expr: Expressão Polars contendo CPF bruto (com ou sem máscara).

    Returns:
        Expressão com CPF padronizado de 11 dígitos numéricos, ou nulo se inválido.
    """
    limpo = (
        expr.cast(pl.String)
        .str.replace_all(r"[^\d]", "")
        .str.strip_chars()
    )
    # Trata strings vazias ou tamanhos inválidos (sentinelas como -4 viram vazios)
    return (
        pl.when(limpo.str.len_chars() == 11)
        .then(limpo)
        .otherwise(pl.lit(None, dtype=pl.String))
    )


def _aliases_vazio() -> pl.DataFrame:
    """Retorna DataFrame de aliases vazio com schema contratual."""
    return pl.DataFrame(schema=LINKAGE_ALIAS_SCHEMA)


def _resolucoes_vazio() -> pl.DataFrame:
    """Retorna DataFrame de resoluções de auditoria vazio com schema contratual."""
    return pl.DataFrame(schema=AUDITORIA_RESOLUCAO_SCHEMA)


def vincular_por_cpf(
    df_fonte: pl.DataFrame,
    df_tse: pl.DataFrame,
    fonte: str,
    col_id_fonte: str,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Vincula registros entre uma fonte externa e o TSE usando CPF íntegro.

    Args:
        df_fonte: DataFrame da fonte de origem com identificador e CPF.
        df_tse: DataFrame do TSE com sq_candidato e CPF.
        fonte: Nome do sistema de origem (ex: 'camara', 'senado', 'cgu_pep').
        col_id_fonte: Nome da coluna de identificador na fonte de origem.

    Returns:
        Tupla com (aliases, resolucoes) contendo os vínculos de confiança alta (score 1.0).
    """
    if df_fonte.is_empty() or df_tse.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    f = df_fonte.with_columns(normalizar_cpf(pl.col("cpf")).alias("cpf_norm")).filter(
        pl.col("cpf_norm").is_not_null()
    )
    t = df_tse.with_columns(normalizar_cpf(pl.col("cpf")).alias("cpf_norm")).filter(
        pl.col("cpf_norm").is_not_null()
    )

    if f.is_empty() or t.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    pares = f.join(t, on="cpf_norm", how="inner", suffix="_tse")
    if pares.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    aliases = (
        pares.select(
            pl.lit(fonte).alias("fonte"),
            pl.col(col_id_fonte).cast(pl.Int64).alias("id_natural"),
            pl.format("pol_cpf_{}", pl.col("cpf_norm")).alias("politico_id"),
            pl.lit(METODO_CPF_EXATO).alias("metodo"),
            pl.lit(CONF_ALTA).alias("confianca"),
            pl.lit(1.0).alias("score"),
            pl.col("_source_url"),
        )
        .unique(subset=["fonte", "id_natural"])
    )

    resolucoes = (
        pares.select(
            pl.lit(fonte).alias("fonte_origem"),
            pl.col(col_id_fonte).cast(pl.String).alias("id_origem"),
            pl.lit("tse").alias("fonte_destino"),
            pl.col("sq_candidato").cast(pl.String).alias("id_destino"),
            pl.lit(METODO_CPF_EXATO).alias("metodo"),
            pl.lit(CONF_ALTA).alias("confianca"),
            pl.lit(1.0).alias("score"),
            pl.lit("merge determinístico por CPF íntegro (11 dígitos)").alias("justificativa"),
            pl.col("_source_url"),
        )
        .unique(subset=["fonte_origem", "id_origem", "fonte_destino", "id_destino"])
    )

    return aliases, resolucoes


def vincular_por_cpf_mascarado(
    df_fonte: pl.DataFrame,
    df_tse: pl.DataFrame,
    fonte: str,
    col_id_fonte: str,
    col_cpf_mascarado: str,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Vincula registros com CPF mascarado (***.123.456-**) usando bloco de data e UF.

    Extrai os 6 dígitos centrais do CPF mascarado e cruza com a base TSE
    condicionado ao casamento exato de Data de Nascimento e UF.

    Args:
        df_fonte: DataFrame com identificador, CPF mascarado, data_nascimento e uf.
        df_tse: DataFrame do TSE com sq_candidato, CPF completo, data_nascimento e uf.
        fonte: Nome da fonte de dados (ex: 'cgu_pep', 'cgu_servidores').
        col_id_fonte: Nome da coluna de identificador na fonte.
        col_cpf_mascarado: Nome da coluna com o CPF mascarado.

    Returns:
        Tupla com (aliases, resolucoes). Merges só ocorrem quando não há ambiguidade.
    """
    if df_fonte.is_empty() or df_tse.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    # Extrai os 6 dígitos centrais do mascarado (remove tudo que não for dígito)
    f = (
        df_fonte.with_columns(
            pl.col(col_cpf_mascarado)
            .cast(pl.String)
            .str.replace_all(r"[^\d]", "")
            .alias("bloco_cpf_6")
        )
        .filter(pl.col("bloco_cpf_6").str.len_chars() == 6)
    )

    # Extrai os 6 dígitos centrais (posições 4 a 9 do CPF de 11 dígitos, ex: slice(3, 6))
    t = (
        df_tse.with_columns(
            normalizar_cpf(pl.col("cpf")).alias("cpf_norm"),
        )
        .filter(pl.col("cpf_norm").is_not_null())
        .with_columns(
            pl.col("cpf_norm").str.slice(3, 6).alias("bloco_cpf_6"),
        )
    )

    if f.is_empty() or t.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    join_cols = ["bloco_cpf_6", "data_nascimento", "uf"]
    pares = f.join(t, on=join_cols, how="inner", suffix="_tse")
    if pares.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    # Verifica unicidade
    f_counts = f.group_by(join_cols).agg(pl.len().alias("n_fonte"))
    t_counts = t.group_by(join_cols).agg(pl.len().alias("n_tse"))

    pares = pares.join(f_counts, on=join_cols).join(t_counts, on=join_cols)
    unico = (pl.col("n_fonte") == 1) & (pl.col("n_tse") == 1)

    pares = pares.with_columns(
        pl.when(unico).then(pl.lit(CONF_ALTA)).otherwise(pl.lit(CONF_BAIXA)).alias("confianca"),
        pl.when(unico)
        .then(pl.lit(METODO_CPF_MASCARADO))
        .otherwise(pl.lit(METODO_HOMONIMO_AMBIGUO))
        .alias("metodo"),
        pl.when(unico).then(pl.lit(0.95)).otherwise(pl.lit(0.40)).alias("score"),
        pl.when(unico)
        .then(pl.lit("merge determinístico por 6 dígitos centrais de CPF + DN + UF"))
        .otherwise(pl.lit("colisão de bloco de CPF mascarado — revisão humana necessária"))
        .alias("justificativa"),
    )

    aliases = (
        pares.filter(pl.col("confianca") != CONF_BAIXA)
        .select(
            pl.lit(fonte).alias("fonte"),
            pl.col(col_id_fonte).cast(pl.Int64).alias("id_natural"),
            pl.format("pol_cpf_{}", pl.col("cpf_norm")).alias("politico_id"),
            pl.col("metodo"),
            pl.col("confianca"),
            pl.col("score"),
            pl.col("_source_url"),
        )
        .unique(subset=["fonte", "id_natural"])
    )

    resolucoes = (
        pares.select(
            pl.lit(fonte).alias("fonte_origem"),
            pl.col(col_id_fonte).cast(pl.String).alias("id_origem"),
            pl.lit("tse").alias("fonte_destino"),
            pl.col("sq_candidato").cast(pl.String).alias("id_destino"),
            pl.col("metodo"),
            pl.col("confianca"),
            pl.col("score"),
            pl.col("justificativa"),
            pl.col("_source_url"),
        )
        .unique(subset=["fonte_origem", "id_origem", "fonte_destino", "id_destino"])
    )

    return aliases, resolucoes


def vincular_por_metaphone_dn_uf(
    df_fonte: pl.DataFrame,
    df_tse: pl.DataFrame,
    fonte: str,
    col_id_fonte: str,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Vincula registros usando similaridade fonética (Metaphone PT-BR), DN e UF.

    Utilizado quando o CPF está ausente (ex: candidaturas do TSE em 2024).
    Garante bloqueio fonético estrito e não realiza merges de homônimos ambíguos.

    Args:
        df_fonte: DataFrame com identificador, nome, data_nascimento e uf.
        df_tse: DataFrame do TSE com sq_candidato, nome, data_nascimento e uf.
        fonte: Identificador da fonte de origem.
        col_id_fonte: Coluna com id natural da fonte.

    Returns:
        Tupla com (aliases, resolucoes). Ambiguidade vira baixa confiança sem merge.
    """
    if df_fonte.is_empty() or df_tse.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    f = (
        df_fonte.with_columns(metaphone_ptbr_expr(pl.col("nome")).alias("meta_nome"))
        .filter(pl.col("meta_nome").is_not_null() & (pl.col("meta_nome") != ""))
    )
    t = (
        df_tse.with_columns(metaphone_ptbr_expr(pl.col("nome")).alias("meta_nome"))
        .filter(pl.col("meta_nome").is_not_null() & (pl.col("meta_nome") != ""))
    )

    if f.is_empty() or t.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    pares = f.join(t, on="meta_nome", how="inner", suffix="_tse")
    if pares.is_empty():
        return _aliases_vazio(), _resolucoes_vazio()

    # Contagens no bloco fonético para detectar homônimos
    f_counts = f.group_by("meta_nome").agg(pl.len().alias("n_fonte"))
    t_counts = t.group_by("meta_nome").agg(pl.len().alias("n_tse"))

    pares = pares.join(f_counts, on="meta_nome").join(t_counts, on="meta_nome")

    unico = (pl.col("n_fonte") == 1) & (pl.col("n_tse") == 1)
    uf_ok = (
        pl.col("uf").is_not_null()
        & pl.col("uf_tse").is_not_null()
        & (pl.col("uf") == pl.col("uf_tse"))
    )
    dn_presente = (
        pl.col("data_nascimento").is_not_null()
        & pl.col("data_nascimento_tse").is_not_null()
    )
    dn_ok = dn_presente & (pl.col("data_nascimento") == pl.col("data_nascimento_tse"))
    dn_divergente = dn_presente & (pl.col("data_nascimento") != pl.col("data_nascimento_tse"))

    pares = pares.with_columns(
        pl.when(unico & uf_ok & dn_ok)
        .then(pl.lit(CONF_ALTA))
        .when(unico & uf_ok & ~dn_presente)
        .then(pl.lit(CONF_MEDIA))
        .otherwise(pl.lit(CONF_BAIXA))
        .alias("confianca"),
        pl.when(unico & uf_ok & dn_ok)
        .then(pl.lit(METODO_METAPHONE_DN_UF))
        .when(unico & uf_ok & ~dn_presente)
        .then(pl.lit(METODO_METAPHONE_UF))
        .otherwise(pl.lit(METODO_HOMONIMO_AMBIGUO))
        .alias("metodo"),
        pl.when(unico & uf_ok & dn_ok)
        .then(pl.lit(0.90))
        .when(unico & uf_ok & ~dn_presente)
        .then(pl.lit(0.75))
        .otherwise(pl.lit(0.30))
        .alias("score"),
        pl.when(~unico)
        .then(pl.lit("nome ambíguo — múltiplos candidatos homônimos no bloco fonético"))
        .when(dn_divergente)
        .then(pl.lit("data de nascimento divergente entre as fontes"))
        .when(~uf_ok)
        .then(pl.lit("UF divergente entre as fontes"))
        .when(dn_ok)
        .then(pl.lit("merge probabilístico confirmado (Metaphone PT-BR + DN + UF)"))
        .otherwise(pl.lit("merge probabilístico moderado (Metaphone PT-BR + UF; DN ausente)"))
        .alias("justificativa"),
    )

    # Âncora: usa CPF se presente no TSE, senão sq_candidato do TSE
    has_cpf_tse = "cpf" in pares.columns
    if has_cpf_tse:
        anchor_expr = (
            pl.when(pl.col("cpf").is_not_null() & (pl.col("cpf") != ""))
            .then(pl.format("pol_cpf_{}", pl.col("cpf")))
            .otherwise(pl.format("pol_tse_{}", pl.col("sq_candidato")))
        )
    else:
        anchor_expr = pl.format("pol_tse_{}", pl.col("sq_candidato"))

    aliases = (
        pares.filter(pl.col("confianca") != CONF_BAIXA)
        .select(
            pl.lit(fonte).alias("fonte"),
            pl.col(col_id_fonte).cast(pl.Int64).alias("id_natural"),
            anchor_expr.alias("politico_id"),
            pl.col("metodo"),
            pl.col("confianca"),
            pl.col("score"),
            pl.col("_source_url"),
        )
        .unique(subset=["fonte", "id_natural"])
    )

    resolucoes = (
        pares.select(
            pl.lit(fonte).alias("fonte_origem"),
            pl.col(col_id_fonte).cast(pl.String).alias("id_origem"),
            pl.lit("tse").alias("fonte_destino"),
            pl.col("sq_candidato").cast(pl.String).alias("id_destino"),
            pl.col("metodo"),
            pl.col("confianca"),
            pl.col("score"),
            pl.col("justificativa"),
            pl.col("_source_url"),
        )
        .unique(subset=["fonte_origem", "id_origem", "fonte_destino", "id_destino"])
    )

    return aliases, resolucoes
