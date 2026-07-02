"""
Análise de Coesão Partidária em Votações Nominais.

Cruza votos individuais, orientações partidárias, perfil de deputados
e informações dos partidos para medir a disciplina de voto em cada
legenda.

Domínios utilizados: votos, orientacoes, deputados, partidos, votacoes
"""

from pathlib import Path

import polars as pl

from ipolitico.core.logger import setup_logger

logger = setup_logger(__name__)
DATALAKE_PATH = Path("data/datalake")


def _gold_path(table: str) -> Path:
    """Retorna o caminho esperado do arquivo Parquet na camada Gold."""
    return DATALAKE_PATH / "gold" / table / f"{table}.parquet"


def main():
    paths = {
        "votos": _gold_path("votos"),
        "orientacoes": _gold_path("orientacoes"),
        "deputados": _gold_path("deputados"),
        "partidos": _gold_path("partidos"),
        "votacoes": _gold_path("votacoes"),
    }

    missing = [k for k, p in paths.items() if not p.exists()]
    if missing:
        logger.warning(
            "Dados não encontrados para: %s. Execute o ETL primeiro!", ", ".join(missing)
        )
        return

    try:
        lazy_votos = pl.scan_parquet(paths["votos"])
        lazy_orient = pl.scan_parquet(paths["orientacoes"])
        lazy_dep = pl.scan_parquet(paths["deputados"])
        lazy_partidos = pl.scan_parquet(paths["partidos"])
        lazy_votacoes = pl.scan_parquet(paths["votacoes"])

        # Junta votos com orientação partidária pela votação + partido
        coesao = (
            lazy_votos.join(
                lazy_orient,
                left_on=["votacao_id", "partido"],
                right_on=["votacao_id", "siglaPartidoBloco"],
                how="inner",
            )
            .join(
                lazy_votacoes.select(["id", "descricao", "data"]),
                left_on="votacao_id",
                right_on="id",
                how="left",
            )
            .with_columns(
                pl.when(pl.col("tipoVoto") == pl.col("orientacaoVoto"))
                .then(pl.lit(True))
                .otherwise(pl.lit(False))
                .fill_null(False)
                .alias("votou_com_partido")
            )
        )

        # Agrega por partido
        resumo_partidos = (
            coesao.group_by("partido")
            .agg(
                pl.len().alias("total_votos_partido"),
                pl.col("votou_com_partido").sum().alias("votos_alinhados_partido"),
            )
            .with_columns(
                (pl.col("votos_alinhados_partido") / pl.col("total_votos_partido") * 100)
                .round(1)
                .alias("coesao_pct")
            )
            .join(
                lazy_partidos.select(["sigla", "nome"]),
                left_on="partido",
                right_on="sigla",
                how="left",
            )
            .sort("coesao_pct")
        )

        logger.info("\n=== COESÃO PARTIDÁRIA (menor coesão primeiro) ===")
        with pl.Config(fmt_str_lengths=60):
            print(resumo_partidos.collect())

        # Deputados que mais votam contra a orientação do próprio partido
        df_rebeldes = (
            coesao.filter(pl.col("votou_com_partido") == False)  # noqa: E712
            .group_by(["id_deputado", "partido"])
            .agg(
                pl.col("votacao_id").n_unique().alias("votacoes_contra_partido"),
            )
            .join(
                lazy_dep.select(["id", "nome"]),
                left_on="id_deputado",
                right_on="id",
                how="left",
            )
            .sort("votacoes_contra_partido", descending=True)
            .limit(10)
        )

        logger.info("\n=== TOP 10 DEPUTADOS QUE MAIS VOTAM CONTRA O PRÓPRIO PARTIDO ===")
        print(df_rebeldes.collect())

        # Votações com maior discordância partidária
        df_dissent = (
            coesao.group_by(["votacao_id", "descricao", "data"])
            .agg(
                (pl.col("votou_com_partido").sum() / pl.len() * 100)
                .round(1)
                .alias("alinhamento_medio_pct"),
                pl.len().alias("total_votos"),
            )
            .filter(pl.col("alinhamento_medio_pct").is_not_null())
            .sort("alinhamento_medio_pct")
            .limit(10)
        )

        logger.info("\n=== VOTAÇÕES COM MAIOR DISCORDÂNCIA PARTIDÁRIA ===")
        with pl.Config(fmt_str_lengths=80):
            print(df_dissent.collect())

    except Exception as e:
        logger.error("Erro na análise de coesão partidária: %s", e)


if __name__ == "__main__":
    main()
