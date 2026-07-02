from pathlib import Path

import polars as pl

from ipolitico.core.logger import setup_logger

logger = setup_logger(__name__)

# Ajuste este caminho conforme a pasta raiz configurada no seu DataLakeSink
DATALAKE_PATH = Path("datalake")


def main():
    logger.info("Acessando a Camada Bronze do Data Lake (Parquet)...")

    path_deputados = DATALAKE_PATH / "deputados.parquet"
    path_profissoes = DATALAKE_PATH / "deputados_profissoes.parquet"
    path_mandatos = DATALAKE_PATH / "deputados_mandatos_externos.parquet"

    if not path_profissoes.exists() or not path_deputados.exists():
        logger.warning("Faltam arquivos no Data Lake. Execute o ETL primeiro!")
        return

    try:
        # Usa SCAN (Lazy) para não estourar a RAM
        lazy_deputados = pl.scan_parquet(path_deputados)
        lazy_profissoes = pl.scan_parquet(path_profissoes)

        # O Polars só vai ler as colunas necessárias na hora do JOIN
        query_profissoes = (
            lazy_profissoes.join(lazy_deputados, left_on="id_deputado", right_on="id", how="inner")
            .group_by("titulo")
            .agg(pl.col("id_deputado").n_unique().alias("qtd_deputados"))
            .sort("qtd_deputados", descending=True)
            .limit(15)
        )

        # Collect() é o gatilho que executa a query otimizada
        df_profissoes = query_profissoes.collect()

        logger.info("\n=== TOP 15 PROFISSÕES MAIS COMUNS NA CÂMARA (Via Data Lake) ===")
        print(df_profissoes)

        if path_mandatos.exists():
            df_mandatos = (
                pl.scan_parquet(path_mandatos)
                .group_by("cargo")
                .agg(pl.len().alias("total"))
                .sort("total", descending=True)
                .limit(5)
                .collect()
            )
            logger.info("\n=== CARGOS ANTERIORES MAIS COMUNS (Mandatos Externos) ===")
            print(df_mandatos)

    except Exception as e:
        logger.error(f"Erro no processamento do Data Lake: {e}")


if __name__ == "__main__":
    main()
