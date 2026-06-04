from pathlib import Path

import polars as pl
from ipolitico.core.logger import setup_logger

logger = setup_logger(__name__)
DATALAKE_PATH = Path("datalake")


def main():
    logger.info("Analisando o histórico de trocas partidárias no Data Lake...")

    path_deputados = DATALAKE_PATH / "deputados.parquet"
    path_historico = DATALAKE_PATH / "deputados_historico.parquet"

    if not path_historico.exists():
        logger.error("Arquivo deputados_historico.parquet não encontrado. O ETL rodou?")
        return

    try:
        lazy_deputados = pl.scan_parquet(path_deputados)
        lazy_historico = pl.scan_parquet(path_historico)

        # Agrupa pelo ID do deputado e conta quantas siglas de partidos ÚNICAS ele já teve
        df_trocas = (
            lazy_historico.filter(pl.col("siglaPartido").is_not_null())
            .group_by("id_deputado")
            .agg(
                pl.col("siglaPartido").n_unique().alias("qtd_partidos_diferentes"),
                pl.col("siglaPartido").unique().alias("lista_partidos"),
            )
            .filter(pl.col("qtd_partidos_diferentes") > 1)  # Só quem já trocou
            .join(lazy_deputados.select(["id", "nome"]), left_on="id_deputado", right_on="id")
            .sort("qtd_partidos_diferentes", descending=True)
            .limit(10)
            .collect()
        )

        if df_trocas.is_empty():
            logger.info("Nenhum deputado com troca partidária encontrado (ou base muito pequena).")
        else:
            logger.info("\n=== TOP 10 DEPUTADOS QUE MAIS TROCARAM DE PARTIDO ===")
            with pl.Config(fmt_str_lengths=100):
                print(df_trocas.select(["nome", "qtd_partidos_diferentes", "lista_partidos"]))

    except Exception as e:
        logger.error(f"Erro ao processar dados: {e}")


if __name__ == "__main__":
    main()
