"""
Composição Partidária das Comissões da Câmara.

Analisa a distribuição de assentos partidários nas comissões técnicas
e permanentes da Câmara dos Deputados. Revela concentração de poder
e quais partidos dominam cada comissão.

Domínios utilizados: orgaos_membros, orgaos, deputados, partidos
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
        "orgaos_membros": _gold_path("orgaos_membros"),
        "orgaos": _gold_path("orgaos"),
        "partidos": _gold_path("partidos"),
    }

    missing = [k for k, p in paths.items() if not p.exists()]
    if missing:
        logger.warning("Dados ausentes: %s. Execute o ETL primeiro!", ", ".join(missing))
        return

    try:
        lazy_membros = pl.scan_parquet(paths["orgaos_membros"])
        lazy_orgaos = pl.scan_parquet(paths["orgaos"])
        lazy_partidos = pl.scan_parquet(paths["partidos"])

        # Composição: órgão + partido do membro
        composicao = lazy_membros.join(
            lazy_orgaos.select(["id", "sigla", "nome", "tipoOrgao"]),
            left_on="id_orgao",
            right_on="id",
            how="inner",
        ).join(
            lazy_partidos.select(["sigla", "nome"]),
            left_on="siglaPartido",
            right_on="sigla",
            how="left",
        )

        # Assentos por partido em cada comissão
        assentos_partido = (
            composicao.group_by(["sigla", "siglaPartido"])
            .agg(
                pl.len().alias("assentos"),
                pl.col("nome_right").first().alias("nome_partido"),
                pl.col("nome").first().alias("nome_comissao"),
            )
            .sort(["sigla", "assentos"], descending=[False, True])
        )

        # Partido com mais assentos em cada comissão
        presidente_comissao = (
            assentos_partido.group_by("sigla")
            .agg(
                pl.first("siglaPartido").alias("partido_maioria"),
                pl.first("assentos").alias("assentos_maioria"),
                pl.first("nome_comissao").alias("nome_comissao"),
                pl.col("assentos").sum().alias("total_assentos"),
            )
            .with_columns(
                (pl.col("assentos_maioria") / pl.col("total_assentos") * 100)
                .round(1)
                .alias("dominancia_pct")
            )
        )

        logger.info("\n=== PARTIDO DOMINANTE EM CADA COMISSÃO ===")
        with pl.Config(fmt_str_lengths=100):
            print(presidente_comissao.collect())

        # Concentração geral: quantos partidos diferentes em cada comissão
        diversidade = (
            composicao.group_by(["sigla", "nome"])
            .agg(
                pl.col("siglaPartido").n_unique().alias("partidos_diferentes"),
                pl.len().alias("total_membros"),
            )
            .sort("partidos_diferentes", descending=True)
        )

        logger.info("\n=== COMISSÕES COM MAIOR DIVERSIDADE PARTIDÁRIA ===")
        with pl.Config(fmt_str_lengths=80):
            print(diversidade.collect())

    except Exception as e:
        logger.error("Erro na análise de comissões: %s", e)


if __name__ == "__main__":
    main()
