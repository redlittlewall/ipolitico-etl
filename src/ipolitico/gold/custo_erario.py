"""Builder Gold "custo ao erário" (issue 02) — view ``(politico_id, casa, mandato,
componente, mes)``.

Lê os Silver de despesa/folha/roster já ingeridos + os aliases Gold produzidos
pela issue 01 e escreve:

- ``custo_erario`` — linhas **somáveis** com método declarado
  (``exato`` | ``estimativa_documentada``), granularidade mensal por
  político/casa/mandato/componente.
- ``observacoes_metricas`` — metadado **não-somável**: benefícios indiretos
  não-mensurados (carro oficial, segurança, passagens) e fontes Silver não
  ingeridas (honestidade: fonte ausente → componente vazio + observação, nunca
  linha silenciosa).

Escrita **append-only**; dedup na Gold via ``DataLakeOptimizer`` (com
``pk_cols`` explícito no CLI).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import polars as pl

from ipolitico.core.config import LEGISLATURA_ATUAL
from ipolitico.core.constants import DomainType
from ipolitico.gold._datalake import escrever_gold, ler_gold, ler_silver
from ipolitico.gold.entidade_canonica import ALIASES_PK
from ipolitico.gold.resolutor import FONTE_CAMARA, FONTE_SENADO, normalizar_nome

# ── Contrato do componente (nomes estáveis, casa-agnósticos) ─────────────────
COMP_SALARIO = "salario"
COMP_ASSESSORES = "assessores"
COMP_CEAP = "ceap"
COMP_AUXILIO_MORADIA = "auxilio_moradia"

METODO_EXATO = "exato"
METODO_ESTIMATIVA = "estimativa_documentada"

# Ano de início da 57ª legislatura (2023–2026). ``mandato = 57 + (ano-2023)//4``
# é a heurística documentada da issue 02.
_ANO_LEGISLATURA_ATUAL = 2023

# Tabela de funções comissionadas (Secretariado Parlamentar SP-01…SP-25),
# proveniência: PDF oficial da Câmara, vigência 18/02/2026 (Lei nº 15.349/2026,
# DOU 18/02/2026), extraída por pypdf — ver
# ``.scratch/etapa-custo-erario/extrair_tabela_sp.py``.
TABELA_SP = {
    "SP01": 1710.83, "SP02": 1906.12, "SP03": 2101.45, "SP04": 2296.72,
    "SP05": 2492.06, "SP06": 2687.34, "SP07": 2882.65, "SP08": 3077.95,
    "SP09": 3273.26, "SP10": 3468.54, "SP11": 3663.85, "SP12": 4054.45,
    "SP13": 4445.03, "SP14": 4835.65, "SP15": 5226.24, "SP16": 5616.84,
    "SP17": 6202.74, "SP18": 6788.64, "SP19": 7374.54, "SP20": 7960.44,
    "SP21": 8546.34, "SP22": 9327.56, "SP23": 10108.74, "SP24": 11544.10,
    "SP25": 12979.45,
}

# Rubricas positivas que compõem o componente ``salario`` (exclui descontos —
# IR, previdência, faltas; ``auxilios`` vira o componente ``auxilio_moradia``;
# ``diarias`` e ``vantagens_indenizatorias`` ficam **fora do contrato** dos 4
# componentes, anotadas no relatório de cobertura — sem dupla contagem).
_RUBRICAS_SALARIO_SENADO = (
    "remuneracao_basica",
    "vantagens_pessoais",
    "funcao_comissionada",
    "gratificacao_natalina",
    "horas_extras",
    "outras_eventuais",
    "abono_permanencia",
)
_RUBRICAS_SALARIO_CAMARA = (
    "remuneracao_fixa",
    "vantagens_pessoais",
    "funcao_comissao",
    "gratificacao_natalina",
    "ferias",
    "outras_remuneracoes_eventuais",
    "abono_permanencia",
)

CUSTO_SCHEMA = {
    "politico_id": pl.String,
    "casa": pl.String,
    "mandato": pl.Int64,
    "componente": pl.String,
    "mes": pl.String,
    "valor_total": pl.Float64,
    "metodo": pl.String,
    "_source_url": pl.String,
}

OBS_SCHEMA = {
    "politico_id": pl.String,
    "casa": pl.String,
    "mes": pl.String,
    "chave": pl.String,
    "texto": pl.String,
    "_source_url": pl.String,
}

# Chaves de identidade das tabelas Gold (dedup + leitura deduplicada).
CUSTO_PK = ["politico_id", "casa", "mandato", "componente", "mes"]
OBS_PK = ["casa", "chave", "mes", "politico_id"]

# Proveniência das observações de método/escopo (contrato da issue 02).
_OBS_URL = "https://github.com/redlittlewall/ipolitico-etl/blob/main/.scratch/etapa-custo-erario/issues/02-gold-custo-ao-erario.md"


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers de expressão (Polars)
# ─────────────────────────────────────────────────────────────────────────────
def _soma_rubricas(colunas: tuple[str, ...]) -> pl.Expr:
    """Expressão com a soma das rubricas positivas (nulo vira 0.0).

    Args:
        colunas: Nomes das colunas de rubrica a somar (excluem descontos e
            ``auxilios`` por decisão de contrato — sem dupla contagem).

    Returns:
        Expressão Polars que soma as rubricas por linha, tratando nulos como 0.
    """
    expr = pl.lit(0.0)
    for nome in colunas:
        expr = expr + pl.col(nome).cast(pl.Float64).fill_null(0.0)
    return expr


def _mes_expr(ano: pl.Expr, mes: pl.Expr) -> pl.Expr:
    """Expressão ``YYYY-MM`` a partir de colunas ano/mês inteiras.

    Args:
        ano: Expressão da coluna de ano (``Int64``).
        mes: Expressão da coluna de mês (``Int64``).

    Returns:
        Expressão string com zero-padding (``2026-07``).
    """
    return ano.cast(pl.String).str.zfill(4) + "-" + mes.cast(pl.String).str.zfill(2)


def _mandato_expr(ano: pl.Expr) -> pl.Expr:
    """Legislatura estimada ``57 + (ano-2023)//4`` (heurística documentada).

    Args:
        ano: Expressão da coluna de ano (``Int64``).

    Returns:
        Expressão inteira com o nº da legislatura (ex.: 2026 → 57; 2027 → 58).
    """
    return pl.lit(LEGISLATURA_ATUAL) + ((ano - pl.lit(_ANO_LEGISLATURA_ATUAL)) // 4)


def _mandato_de_mes(mes: str) -> int:
    """Legislatura da referência ``YYYY-MM`` (heurística da issue 02).

    Args:
        mes: Referência no formato ``YYYY-MM``.

    Returns:
        Nº da legislatura (ex.: 2026-08 → 57; 2027-01 → 58).
    """
    ano = int(mes[:4])
    return LEGISLATURA_ATUAL + (ano - _ANO_LEGISLATURA_ATUAL) // 4


def _aliases_por_fonte(aliases: pl.DataFrame, fonte: str) -> pl.DataFrame:
    """Aliases de uma fonte no formato ``(id_natural, politico_id)``.

    Args:
        aliases: Gold ``politicos_aliases``.
        fonte: Namespace da fonte (``camara`` | ``senado``).

    Returns:
        DataFrame só com ``id_natural`` e ``politico_id`` da fonte; vazio
        (0 linhas, sem colunas adicionais) quando não há aliases da fonte.
    """
    return aliases.filter(pl.col("fonte") == fonte).select("id_natural", "politico_id")


def _agregar_custo(df: pl.DataFrame) -> pl.DataFrame:
    """Agrega a granularidade atômica para (politico, casa, mandato, componente, mes).

    Args:
        df: Linhas atômicas com as colunas de ``CUSTO_SCHEMA``.

    Returns:
        DataFrame agregado por mês (soma de ``valor_total``, maior
        ``_source_url``), ou vazio com o schema contratual.
    """
    if df.is_empty():
        return pl.DataFrame(schema=CUSTO_SCHEMA)
    return (
        df.group_by("politico_id", "casa", "mandato", "componente", "mes", "metodo")
        .agg(pl.sum("valor_total"), pl.col("_source_url").max())
        .select(
            "politico_id", "casa", "mandato", "componente", "mes",
            "valor_total", "metodo", "_source_url",
        )
    )


def _senadores_unicos(senadores: pl.DataFrame) -> pl.DataFrame:
    """Senadores únicos por código com nome normalizado (legislatura mais recente).

    Args:
        senadores: Silver ``senadores`` (pode ter múltiplas linhas por código,
            uma por legislatura).

    Returns:
        DataFrame com 1 linha por ``codigo`` (a de maior
        ``segunda_legislatura``), colunas ``codigo``, ``nome_norm``,
        ``_source_url``.
    """
    return (
        senadores.sort("segunda_legislatura", descending=True)
        .unique(subset=["codigo"])
        .with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
        .select("codigo", "nome_norm", "_source_url")
    )


def _so_nomes_unicos(df: pl.DataFrame, nome_col: str) -> pl.DataFrame:
    """Filtra ``df`` para nomes que ocorrem exatamente 1× (desambiguação).

    Args:
        df: DataFrame com uma coluna de nome normalizado.
        nome_col: Nome da coluna de nome normalizado.

    Returns:
        Linhas cujo nome é único (homônimos descartados).
    """
    contagem = df.group_by(nome_col).agg(pl.len().alias("n"))
    unicos = contagem.filter(pl.col("n") == 1).select(nome_col)
    return df.join(unicos, on=nome_col, how="inner")


def _remuneracoes_de_senadores(
    remuneracoes: pl.DataFrame,
    senadores: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Remunerações cujo nome casa (sem ambiguidade) com um senador → politico_id.

    Args:
        remuneracoes: Silver ``remuneracoes``.
        senadores: Silver ``senadores``.
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas de remuneração com ``politico_id`` resolvido; homônimos excluídos.
    """
    sen = _so_nomes_unicos(_senadores_unicos(senadores), "nome_norm")
    rem = remuneracoes.with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
    return (
        rem.join(sen, on="nome_norm", how="inner", suffix="_sen")
        .join(
            _aliases_por_fonte(aliases, FONTE_SENADO),
            left_on="codigo",
            right_on="id_natural",
            how="inner",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Mappers por componente/casa (funções puras, TDDável)
# ─────────────────────────────────────────────────────────────────────────────
def resolver_salario_senado(
    remuneracoes: pl.DataFrame,
    senadores: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``salario`` (casa senado): soma das rubricas positivas por mês.

    Valor = remuneração bruta mensal do senador, sem descontos (IR, previdência,
    faltas) e sem ``auxilios`` (vira ``auxilio_moradia``), ``diarias`` e
    ``vantagens_indenizatorias`` (fora do contrato dos 4 componentes).

    Args:
        remuneracoes: Silver ``remuneracoes`` (colunas ``nome``, ``ano``, ``mes``).
        senadores: Silver ``senadores`` (coluna ``codigo``/``nome``).
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA`` agregadas por (politico, mes); vazio se não há
        nome único ou aliases.
    """
    out = (
        _remuneracoes_de_senadores(remuneracoes, senadores, aliases)
        .with_columns(
            _soma_rubricas(_RUBRICAS_SALARIO_SENADO).alias("valor_total"),
            pl.lit("senado").alias("casa"),
            pl.lit(COMP_SALARIO).alias("componente"),
            pl.lit(METODO_EXATO).alias("metodo"),
            _mes_expr(pl.col("ano"), pl.col("mes")).alias("mes"),
            _mandato_expr(pl.col("ano")).alias("mandato"),
        )
    )
    return _agregar_custo(out)


def resolver_auxilio_moradia_senado(
    remuneracoes: pl.DataFrame,
    senadores: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``auxilio_moradia`` (casa senado): coluna ``auxilios`` > 0.

    O mesmo join por nome do ``salario``; só linhas com auxílio positivo entram,
    sem dupla contagem (o ``salario`` não soma ``auxilios``).

    Args:
        remuneracoes: Silver ``remuneracoes``.
        senadores: Silver ``senadores``.
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA``; vazio sem auxílios positivos ou nome único.
    """
    out = (
        _remuneracoes_de_senadores(remuneracoes, senadores, aliases)
        .filter(pl.col("auxilios").fill_null(0.0) > 0.0)
        .with_columns(
            pl.col("auxilios").fill_null(0.0).alias("valor_total"),
            pl.lit("senado").alias("casa"),
            pl.lit(COMP_AUXILIO_MORADIA).alias("componente"),
            pl.lit(METODO_EXATO).alias("metodo"),
            _mes_expr(pl.col("ano"), pl.col("mes")).alias("mes"),
            _mandato_expr(pl.col("ano")).alias("mandato"),
        )
    )
    return _agregar_custo(out)


def resolver_ceap_senado(
    despesas_ceaps: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``ceap`` (casa senado): soma do ``valorReembolsado`` por mês.

    ``codSenador`` vive no mesmo espaço de ids que ``senadores.codigo``
    (verificado na pesquisa 09: 82/82) → o alias ``senado`` da issue 01 resolve
    direto, sem join intermediário com o roster.

    Args:
        despesas_ceaps: Silver ``despesas_ceaps``.
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA``; vazio sem ``codSenador`` resolvível.
    """
    out = (
        despesas_ceaps.join(
            _aliases_por_fonte(aliases, FONTE_SENADO),
            left_on="codSenador",
            right_on="id_natural",
            how="inner",
        )
        .with_columns(
            pl.col("valorReembolsado").cast(pl.Float64).alias("valor_total"),
            pl.lit("senado").alias("casa"),
            pl.lit(COMP_CEAP).alias("componente"),
            pl.lit(METODO_EXATO).alias("metodo"),
            _mes_expr(pl.col("ano"), pl.col("mes")).alias("mes"),
            _mandato_expr(pl.col("ano")).alias("mandato"),
        )
    )
    return _agregar_custo(out)


def resolver_assessores_senado(
    remuneracoes: pl.DataFrame,
    servidores: pl.DataFrame,
    senadores: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``assessores`` (casa senado): remuneração dos servidores de
    gabinete atribuída ao senador chefe do gabinete (via ``lotacao_nome``),
    excluindo a remuneração do próprio senador.

    Vínculo assessor → gabinete por **nome** (o ``sequencial`` do roster não é
    chave confiável para ``remuneracoes`` — pesquisa 09). Nomes ambíguos
    (homônimos) no roster não são atribuídos.

    Args:
        remuneracoes: Silver ``remuneracoes``.
        servidores: Silver ``servidores`` (coluna ``lotacao_nome``).
        senadores: Silver ``senadores``.
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA``; vazio sem gabinete mapeado ou com ambiguidade.
    """
    sen = _so_nomes_unicos(_senadores_unicos(senadores), "nome_norm")
    serv = (
        servidores.unique(subset=["sequencial"])
        .with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
        .with_columns(
            normalizar_nome(pl.col("lotacao_nome").str.extract(r"do Senador (.+)$")).alias(
                "senador_norm"
            )
        )
        .filter(pl.col("senador_norm").is_not_null())
        .select("sequencial", "nome_norm", "senador_norm")
    )
    # gabinete → senador (nome do senador na lotação deve ser único)
    gab = (
        serv.join(sen, left_on="senador_norm", right_on="nome_norm", how="inner")
        .select("sequencial", "nome_norm", "senador_norm", "codigo")
    )
    serv_unicos = _so_nomes_unicos(
        servidores.unique(subset=["sequencial"]).with_columns(
            normalizar_nome(pl.col("nome")).alias("nome_norm")
        ),
        "nome_norm",
    )
    rem = remuneracoes.with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
    out = (
        rem.join(serv_unicos.select("sequencial", "nome_norm"), on="nome_norm", how="inner")
        .join(gab, on="sequencial", how="inner", suffix="_gab")
        .join(
            _aliases_por_fonte(aliases, FONTE_SENADO),
            left_on="codigo",
            right_on="id_natural",
            how="inner",
        )
        # a remuneração do próprio senador é ``salario``, não ``assessores``
        .filter(pl.col("nome_norm") != pl.col("senador_norm"))
        .with_columns(
            _soma_rubricas(_RUBRICAS_SALARIO_SENADO).alias("valor_total"),
            pl.lit("senado").alias("casa"),
            pl.lit(COMP_ASSESSORES).alias("componente"),
            pl.lit(METODO_EXATO).alias("metodo"),
            _mes_expr(pl.col("ano"), pl.col("mes")).alias("mes"),
            _mandato_expr(pl.col("ano")).alias("mandato"),
        )
    )
    return _agregar_custo(out)


def resolver_salario_camara(
    folha_pagamento: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``salario`` (casa camara): rubricas positivas do Parlamentar.

    Requer as colunas ``ano``/``mes`` na folha — **ausentes no contrato Silver
    atual** (``FOLHA_PAGAMENTO`` não as carrega); o builder só chama este mapper
    quando essas colunas existem, senão registra observação (ver
    ``_montar_observacoes``).

    Args:
        folha_pagamento: Silver ``folha_pagamento`` com ``ano``/``mes``.
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA``; vazio sem linhas ``Parlamentar``/aliases.
    """
    out = (
        folha_pagamento.filter(pl.col("grupo_funcional") == "Parlamentar")
        .with_columns(
            pl.col("cargo").str.extract(r"Deputado (\d+)").cast(pl.Int64).alias("id_deputado")
        )
        .filter(pl.col("id_deputado").is_not_null())
        .join(
            _aliases_por_fonte(aliases, FONTE_CAMARA),
            left_on="id_deputado",
            right_on="id_natural",
            how="inner",
        )
        .with_columns(
            _soma_rubricas(_RUBRICAS_SALARIO_CAMARA).alias("valor_total"),
            pl.lit("camara").alias("casa"),
            pl.lit(COMP_SALARIO).alias("componente"),
            pl.lit(METODO_EXATO).alias("metodo"),
            _mes_expr(pl.col("ano"), pl.col("mes")).alias("mes"),
            _mandato_expr(pl.col("ano")).alias("mandato"),
        )
    )
    return _agregar_custo(out)


def resolver_auxilio_moradia_camara(
    folha_pagamento: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``auxilio_moradia`` (casa camara): coluna ``auxilios`` > 0.

    Mesmo requisito de ``ano``/``mes`` da folha (ver ``resolver_salario_camara``).

    Args:
        folha_pagamento: Silver ``folha_pagamento`` com ``ano``/``mes``.
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA``; vazio sem auxílios positivos.
    """
    out = (
        folha_pagamento.filter(pl.col("grupo_funcional") == "Parlamentar")
        .with_columns(
            pl.col("cargo").str.extract(r"Deputado (\d+)").cast(pl.Int64).alias("id_deputado")
        )
        .filter(pl.col("id_deputado").is_not_null())
        .filter(pl.col("auxilios").fill_null(0.0) > 0.0)
        .join(
            _aliases_por_fonte(aliases, FONTE_CAMARA),
            left_on="id_deputado",
            right_on="id_natural",
            how="inner",
        )
        .with_columns(
            pl.col("auxilios").fill_null(0.0).alias("valor_total"),
            pl.lit("camara").alias("casa"),
            pl.lit(COMP_AUXILIO_MORADIA).alias("componente"),
            pl.lit(METODO_EXATO).alias("metodo"),
            _mes_expr(pl.col("ano"), pl.col("mes")).alias("mes"),
            _mandato_expr(pl.col("ano")).alias("mandato"),
        )
    )
    return _agregar_custo(out)


def resolver_ceap_camara(
    despesas: pl.DataFrame,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``ceap`` (casa camara): soma do ``valorLiquido`` por mês.

    Args:
        despesas: Silver ``despesas`` (colunas ``id_deputado``, ``ano``, ``mes``).
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA``; vazio sem ``id_deputado`` resolvível.
    """
    out = (
        despesas.join(
            _aliases_por_fonte(aliases, FONTE_CAMARA),
            left_on="id_deputado",
            right_on="id_natural",
            how="inner",
        )
        .with_columns(
            pl.col("valorLiquido").cast(pl.Float64).alias("valor_total"),
            pl.lit("camara").alias("casa"),
            pl.lit(COMP_CEAP).alias("componente"),
            pl.lit(METODO_EXATO).alias("metodo"),
            _mes_expr(pl.col("ano"), pl.col("mes")).alias("mes"),
            _mandato_expr(pl.col("ano")).alias("mandato"),
        )
    )
    return _agregar_custo(out)


def resolver_assessores_camara_estimativa(
    funcionarios: pl.DataFrame,
    deputados: pl.DataFrame,
    mes: str,
    aliases: pl.DataFrame,
) -> pl.DataFrame:
    """Componente ``assessores`` (casa camara): **estimativa documentada** por
    gabinete (roster + Tabela SP), sem garantia de exatidão.

    O roster dá o nome do deputado chefe do gabinete (``lotacao`` no formato
    ``GAB. {sala} - {NOME}``) e o nível ``SP{n}C`` de cada assessor; o valor é o
    da Tabela SP vigente (18/02/2026). ``mes`` é a referência da estimativa.
    Nomes de deputado ambíguos não são atribuídos.

    Args:
        funcionarios: Silver ``funcionarios`` (roster nomeado).
        deputados: Silver ``deputados`` (nome → id_deputado).
        mes: Referência ``YYYY-MM`` da estimativa (ex.: mês do snapshot).
        aliases: Gold ``politicos_aliases``.

    Returns:
        Linhas ``CUSTO_SCHEMA`` com ``metodo=estimativa_documentada``.
    """
    func = (
        funcionarios.with_columns(
            normalizar_nome(
                pl.col("lotacao").str.extract(r"GAB\.\s*\d+/\d+\s*-\s*(.+)$")
            ).alias("deputado_norm"),
            (pl.lit("SP") + pl.col("cargo").str.extract(r"SP(\d{1,2})").str.zfill(2)).alias(
                "nivel_sp"
            ),
        )
        .filter(pl.col("deputado_norm").is_not_null())
    )
    tabela = pl.DataFrame(
        {"nivel_sp": list(TABELA_SP), "valor_sp": list(TABELA_SP.values())}
    )
    dep = _so_nomes_unicos(
        deputados.sort("idLegislatura", descending=True)
        .unique(subset=["id"])
        .with_columns(normalizar_nome(pl.col("nome")).alias("nome_norm"))
        .select("id", "nome_norm"),
        "nome_norm",
    )
    out = (
        func.join(tabela, on="nivel_sp", how="inner")
        .join(dep, left_on="deputado_norm", right_on="nome_norm", how="inner")
        .join(
            _aliases_por_fonte(aliases, FONTE_CAMARA),
            left_on="id",
            right_on="id_natural",
            how="inner",
        )
        .with_columns(
            pl.col("valor_sp").alias("valor_total"),
            pl.lit("camara").alias("casa"),
            pl.lit(COMP_ASSESSORES).alias("componente"),
            pl.lit(METODO_ESTIMATIVA).alias("metodo"),
            pl.lit(mes).alias("mes"),
            pl.lit(_mandato_de_mes(mes)).alias("mandato"),
        )
    )
    return _agregar_custo(out)


# ─────────────────────────────────────────────────────────────────────────────
#  Builder
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class CoberturaCustoErario:
    """Relatório de cobertura do builder de custo ao erário (issue 02, acceptance).

    Attributes:
        total_linhas: Nº de linhas em ``custo_erario`` (por político/casa/mandato/
            componente/mês).
        total_por_componente: Linhas por componente
            (``salario``, ``assessores``, ``ceap``, ``auxilio_moradia``).
        total_por_casa: Linhas por casa (``camara``, ``senado``).
        total_observacoes: Nº de observações registradas em ``observacoes_metricas``.
    """

    total_linhas: int = 0
    total_por_componente: dict[str, int] = field(default_factory=dict)
    total_por_casa: dict[str, int] = field(default_factory=dict)
    total_observacoes: int = 0


def _alias_vazio() -> pl.DataFrame:
    """Aliases vazios com o schema mínimo usado nos mappers (sem erro de coluna)."""
    return pl.DataFrame(
        schema={"fonte": pl.String, "id_natural": pl.Int64, "politico_id": pl.String}
    )


def _mes_referencia(funcionarios: pl.DataFrame) -> str:
    """Mês ``YYYY-MM`` de referência da estimativa de gabinete (roster Câmara).

    O contrato de ``funcionarios`` não tem coluna de mês; usa-se o mês da
    nomeação mais recente do roster (composição atual). Sem nomeações válidas,
    usa-se o mês corrente — a estimativa é sempre ``estimativa_documentada``.

    Args:
        funcionarios: Silver ``funcionarios`` (coluna ``dataNomeacao``).

    Returns:
        Referência ``YYYY-MM`` da estimativa.
    """
    mais_recente = (
        funcionarios.filter(pl.col("dataNomeacao").is_not_null())
        .select(pl.col("dataNomeacao").str.slice(0, 7).max())
        .item()
    )
    if mais_recente is None:
        return datetime.now().strftime("%Y-%m")
    return mais_recente


class CustoErarioBuilder:
    """Constrói as tabelas Gold de custo ao erário a partir dos Silver + aliases.

    Args:
        base_dir: Diretório raiz do DataLake (padrão ``data/datalake``).
    """

    def __init__(self, base_dir: str = "data/datalake"):
        self.base_dir = base_dir

    def build(self) -> None:
        """Executa todos os mappers e persiste as tabelas Gold (command).

        Escreve ``custo_erario`` e ``observacoes_metricas`` em lotes
        append-only (nunca sobrescreve). Não responde: o relatório de
        cobertura é uma query separada, :meth:`cobertura`.

        Returns:
            ``None`` (Command-Query Separation — build persiste, não consulta).
        """
        aliases = ler_gold(self.base_dir, "politicos_aliases", chaves=ALIASES_PK)
        deputados = ler_silver(self.base_dir, DomainType.DEPUTADOS)
        folha = ler_silver(self.base_dir, DomainType.FOLHA_PAGAMENTO)
        funcionarios = ler_silver(self.base_dir, DomainType.FUNCIONARIOS)
        despesas = ler_silver(self.base_dir, DomainType.DESPESAS)
        senadores = ler_silver(self.base_dir, DomainType.SENADORES)
        remuneracoes = ler_silver(self.base_dir, DomainType.REMUNERACOES)
        servidores = ler_silver(self.base_dir, DomainType.SERVIDORES)
        despesas_ceaps = ler_silver(self.base_dir, DomainType.DESPESAS_CEAPS)

        if aliases.is_empty():
            aliases = _alias_vazio()

        custo = self._montar_custo(
            deputados, folha, funcionarios, despesas, senadores,
            remuneracoes, servidores, despesas_ceaps, aliases,
        )
        obs = self._montar_observacoes(
            aliases, deputados, folha, funcionarios, despesas, senadores,
            remuneracoes, servidores, despesas_ceaps,
        )

        escrever_gold(self.base_dir, "custo_erario", custo)
        escrever_gold(self.base_dir, "observacoes_metricas", obs)

    def cobertura(self) -> CoberturaCustoErario:
        """Relatório de cobertura da Gold persistida (query, sem mutação).

        Lê ``custo_erario`` e ``observacoes_metricas`` já deduplicados
        (último ``captured_at`` vence) e computa as métricas. Num ambiente
        limpo, rodar após :meth:`build` produz os mesmos números da execução.

        Returns:
            ``CoberturaCustoErario`` preenchida (zeros sem dados/aliases).
        """
        custo = ler_gold(self.base_dir, "custo_erario", chaves=CUSTO_PK)
        obs = ler_gold(self.base_dir, "observacoes_metricas", chaves=OBS_PK)
        return self._relatorio(custo, obs)

    # ------------------------------------------------------------------
    #  Métodos internos
    # ------------------------------------------------------------------

    def _montar_custo(
        self,
        deputados: pl.DataFrame,
        folha: pl.DataFrame,
        funcionarios: pl.DataFrame,
        despesas: pl.DataFrame,
        senadores: pl.DataFrame,
        remuneracoes: pl.DataFrame,
        servidores: pl.DataFrame,
        despesas_ceaps: pl.DataFrame,
        aliases: pl.DataFrame,
    ) -> pl.DataFrame:
        """Executa todos os mappers e concatena as linhas de ``custo_erario``.

        Fonte Silver ausente → componente vazio (sem exceção); a observação
        correspondente é registrada em ``_montar_observacoes``.

        Returns:
            DataFrame ``CUSTO_SCHEMA`` (vazio se nada resolveu).
        """
        frames: list[pl.DataFrame] = []
        if not senadores.is_empty() and not remuneracoes.is_empty():
            frames.append(resolver_salario_senado(remuneracoes, senadores, aliases))
            frames.append(resolver_auxilio_moradia_senado(remuneracoes, senadores, aliases))
        if not servidores.is_empty() and not remuneracoes.is_empty() and not senadores.is_empty():
            frames.append(resolver_assessores_senado(remuneracoes, servidores, senadores, aliases))
        if not despesas_ceaps.is_empty():
            frames.append(resolver_ceap_senado(despesas_ceaps, aliases))
        if not folha.is_empty():
            if "ano" in folha.columns and "mes" in folha.columns:
                frames.append(resolver_salario_camara(folha, aliases))
                frames.append(resolver_auxilio_moradia_camara(folha, aliases))
        if not funcionarios.is_empty() and not deputados.is_empty():
            frames.append(
                resolver_assessores_camara_estimativa(
                    funcionarios, deputados, _mes_referencia(funcionarios), aliases
                )
            )
        if not despesas.is_empty():
            frames.append(resolver_ceap_camara(despesas, aliases))
        if not frames:
            return pl.DataFrame(schema=CUSTO_SCHEMA)
        return pl.concat(frames, how="vertical")

    def _montar_observacoes(
        self,
        aliases: pl.DataFrame,
        deputados: pl.DataFrame,
        folha: pl.DataFrame,
        funcionarios: pl.DataFrame,
        despesas: pl.DataFrame,
        senadores: pl.DataFrame,
        remuneracoes: pl.DataFrame,
        servidores: pl.DataFrame,
        despesas_ceaps: pl.DataFrame,
    ) -> pl.DataFrame:
        """Monta ``observacoes_metricas``: fontes ausentes + escopo não-somável.

        Registra uma observação por domínio Silver não ingerido (componente com
        zero linhas, nunca silencioso) e os benefícios indiretos não-mensurados
        por casa (carro oficial, segurança, passagens — sem coluna de valor).

        Returns:
            DataFrame ``OBS_SCHEMA`` (sempre ≥ 2 linhas: benefícios por casa).
        """
        registros: list[dict[str, object]] = []
        dom_camara = {
            "deputados": deputados,
            "folha_pagamento": folha,
            "funcionarios": funcionarios,
            "despesas": despesas,
        }
        dom_senado = {
            "senadores": senadores,
            "remuneracoes": remuneracoes,
            "servidores": servidores,
            "despesas_ceaps": despesas_ceaps,
        }
        for dom, df in {**dom_camara, **dom_senado}.items():
            if df.is_empty():
                casa = "camara" if dom in dom_camara else "senado"
                registros.append(
                    {
                        "politico_id": None,
                        "casa": casa,
                        "mes": None,
                        "chave": f"fonte_nao_ingerida_{dom}",
                        "texto": (
                            f"Fonte Silver {dom} não ingerida nesta fatia — "
                            "componente(s) correspondente(s) com zero linhas."
                        ),
                        "_source_url": _OBS_URL,
                    }
                )
        if (
            not folha.is_empty()
            and ("ano" not in folha.columns or "mes" not in folha.columns)
        ):
            # Folha presente sem ano/mes no contrato: os mappers Câmara não têm
            # referência temporal e produzem zero linhas — registra observação
            # (o contrato Silver de FOLHA_PAGAMENTO ainda não as carrega).
            registros.append(
                {
                    "politico_id": None,
                    "casa": "camara",
                    "mes": None,
                    "chave": "folha_pagamento_sem_periodo",
                    "texto": (
                        "Silver folha_pagamento presente mas sem ano/mes no "
                        "contrato — salario/auxilio_moradia Câmara com zero linhas."
                    ),
                    "_source_url": _OBS_URL,
                }
            )
        if aliases.is_empty():
            registros.append(
                {
                    "politico_id": None,
                    "casa": None,
                    "mes": None,
                    "chave": "identidade_nao_resolvida",
                    "texto": (
                        "Gold politicos_aliases vazia — rode --build-entidade-canonica "
                        "antes; nenhuma linha foi atribuída a um político."
                    ),
                    "_source_url": _OBS_URL,
                }
            )
        for casa in ("camara", "senado"):
            registros.append(
                {
                    "politico_id": None,
                    "casa": casa,
                    "mes": None,
                    "chave": "beneficios_indiretos",
                    "texto": (
                        "Benefícios indiretos não-mensurados nesta métrica "
                        "(não-somáveis): carro oficial, segurança, passagens."
                    ),
                    "_source_url": _OBS_URL,
                }
            )
        return pl.DataFrame(registros, schema=OBS_SCHEMA)

    @staticmethod
    def _relatorio(
        custo: pl.DataFrame,
        obs: pl.DataFrame,
    ) -> CoberturaCustoErario:
        """Calcula o relatório de cobertura a partir das tabelas produzidas.

        Args:
            custo: Tabela ``custo_erario`` (pode ser vazia).
            obs: Tabela ``observacoes_metricas`` (sempre ≥ 2 linhas).

        Returns:
            ``CoberturaCustoErario`` preenchida.
        """
        por_componente: dict[str, int] = {}
        por_casa: dict[str, int] = {}
        if not custo.is_empty():
            agrupado = custo.group_by("componente").agg(pl.len().alias("n"))
            por_componente = {
                row["componente"]: row["n"] for row in agrupado.iter_rows(named=True)
            }
            por_casa = {
                row["casa"]: row["n"]
                for row in custo.group_by("casa").agg(pl.len().alias("n")).iter_rows(named=True)
            }
        return CoberturaCustoErario(
            total_linhas=custo.height,
            total_por_componente=por_componente,
            total_por_casa=por_casa,
            total_observacoes=obs.height,
        )
