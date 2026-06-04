"""
Tempo de Tramitação de Proposições por Tipo e Autor.

Analisa o ciclo de vida das proposições na Câmara: quanto tempo
levam entre apresentação e última tramitação, quais tipos tramitam
mais rápido, e se o partido/autor influencia a velocidade.

Domínios utilizados: proposicoes, tramitacoes, autores, deputados,
                    proposicoes_detalhe
"""

from pathlib import Path

import polars as pl
from ipolitico.core.logger import setup_logger

logger = setup_logger()
DATALAKE_PATH = Path("data/datalake")


def _gold_path(table: str) -> Path:
    return DATALAKE_PATH / "gold" / table / f"{table}.parquet"


def main():
    paths = {
        "proposicoes": _gold_path("proposicoes"),
        "tramitacoes": _gold_path("tramitacoes"),
        "autores": _gold_path("autores"),
        "deputados": _gold_path("deputados"),
        "proposicoes_detalhe": _gold_path("proposicoes_detalhe"),
    }

    # Só proposicoes + tramitacoes são obrigatórios; autores/deputados/detalhe são opcionais
    required_missing = [
        k for k, p in paths.items() if k in ("proposicoes", "tramitacoes") and not p.exists()
    ]
    if required_missing:
        logger.warning(
            "Dados obrigatórios não encontrados: %s. Execute o ETL primeiro!",
            ", ".join(required_missing),
        )
        return

    try:
        lazy_prop = pl.scan_parquet(paths["proposicoes"])
        lazy_tram = pl.scan_parquet(paths["tramitacoes"])

        # Data de apresentação da proposição
        prop_base = lazy_prop.select(
            ["id", "siglaTipo", "numero", "ano", "ementa", "dataApresentacao"]
        )

        # Primeira e última tramitação de cada proposição
        tram_timeline = lazy_tram.group_by("id_proposicao").agg(
            [
                pl.col("dataHora").min().alias("primeira_tramitacao"),
                pl.col("dataHora").max().alias("ultima_tramitacao"),
                pl.len().alias("qtd_tramitacoes"),
                pl.col("descricaoSituacao").last().alias("situacao_atual"),
            ]
        )

        # Junta proposição + timeline
        ciclo = prop_base.join(tram_timeline, left_on="id", right_on="id_proposicao", how="inner")

        # Dias entre apresentação e última tramitação
        ciclo = ciclo.with_columns(
            (pl.col("ultima_tramitacao") - pl.col("dataApresentacao"))
            .dt.total_days()
            .alias("dias_tramitacao")
        )

        # Tempo médio por tipo de proposição
        logger.info("\n=== TEMPO MÉDIO DE TRAMITAÇÃO POR TIPO DE PROPOSIÇÃO ===")
        tempo_por_tipo = (
            ciclo.group_by("siglaTipo")
            .agg(
                [
                    pl.col("dias_tramitacao").mean().round(0).alias("media_dias"),
                    pl.col("dias_tramitacao").median().round(0).alias("mediana_dias"),
                    pl.col("dias_tramitacao").max().alias("max_dias"),
                    pl.col("dias_tramitacao").min().alias("min_dias"),
                    pl.len().alias("qtd_proposicoes"),
                ]
            )
            .sort("media_dias", descending=True)
        )
        print(tempo_por_tipo.collect())

        # Top 20 proposições mais longas
        logger.info("\n=== TOP 20 PROPOSIÇÕES COM MAIOR TEMPO DE TRAMITAÇÃO ===")
        top_longas = (
            ciclo.sort("dias_tramitacao", descending=True)
            .select(
                [
                    "siglaTipo",
                    "numero",
                    "ano",
                    pl.col("ementa").str.slice(0, 80),
                    "dias_tramitacao",
                    "qtd_tramitacoes",
                    "situacao_atual",
                ]
            )
            .limit(20)
        )
        with pl.Config(fmt_str_lengths=60):
            print(top_longas.collect())

        # Se autores e deputados existirem, cruza para top autores
        if paths["autores"].exists() and paths["deputados"].exists():
            lazy_autores = pl.scan_parquet(paths["autores"])

            # Top autores por nome
            autor_count = (
                lazy_autores.filter(pl.col("tipo") == "DEPUTADO")
                .group_by("nome")
                .agg(pl.len().alias("qtd_proposicoes"))
                .sort("qtd_proposicoes", descending=True)
                .limit(10)
            )

            logger.info("\n=== TOP 10 DEPUTADOS COM MAIS PROPOSIÇÕES (como autor) ===")
            print(autor_count.collect())

    except Exception as e:
        logger.error("Erro na análise de tramitação: %s", e)


if __name__ == "__main__":
    main()
