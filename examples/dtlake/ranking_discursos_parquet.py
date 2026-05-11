from pathlib import Path

import polars as pl
from ipolitico.core.logger import setup_logger

logger = setup_logger()

DATALAKE_PATH = Path("datalake")


def main():
    logger.info("Explorando a tabela massiva de Discursos no Data Lake...")

    path_deputados = DATALAKE_PATH / "deputados.parquet"
    path_discursos = DATALAKE_PATH / "deputados_discursos.parquet"

    if not path_discursos.exists() or not path_deputados.exists():
        logger.warning("Arquivos Parquet não encontrados. O ETL temporal rodou?")
        return

    try:
        lazy_deputados = pl.scan_parquet(path_deputados)
        lazy_discursos = pl.scan_parquet(path_discursos)

        # Query 1: Quem falou mais vezes?
        # Note que não puxamos a coluna "transcricao" para a memória aqui!
        query_volume = (
            lazy_discursos.select(["id_deputado", "dataHoraInicio"])  # Projeção cirúrgica
            .join(
                lazy_deputados.select(["id", "nome"]),  # <-- REMOVIDO "siglaPartido"
                left_on="id_deputado",
                right_on="id",
            )
            .group_by("nome")  # <-- REMOVIDO "siglaPartido"
            .agg(pl.len().alias("total_discursos"))
            .sort("total_discursos", descending=True)
            .limit(10)
        )

        logger.info("\n=== TOP 10 DEPUTADOS MAIS DISCURSIVOS (Motor Parquet) ===")
        print(query_volume.collect())

        # Query 2: Amostragem de segurança (Validar se a transcrição não corrompeu)
        query_texto = (
            lazy_discursos.filter(pl.col("transcricao").is_not_null())
            .join(lazy_deputados.select(["id", "nome"]), left_on="id_deputado", right_on="id")
            .select(
                [
                    "nome",
                    "dataHoraInicio",
                    # Pega os primeiros 80 caracteres do texto e adiciona reticências
                    (pl.col("transcricao").str.slice(0, 80) + "...").alias("excerto"),
                ]
            )
            .sort("dataHoraInicio", descending=True)
            .limit(5)
        )

        logger.info("\n=== VERIFICAÇÃO DE INTEGRIDADE DAS TRANSCRIÇÕES ===")
        with pl.Config(fmt_str_lengths=100):
            print(query_texto.collect())

    except Exception as e:
        logger.error(f"Erro no processamento temporal: {e}")


if __name__ == "__main__":
    main()
