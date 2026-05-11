from pathlib import Path

import polars as pl
from ipolitico.core.logger import setup_logger

logger = setup_logger()
PATH = Path("data/datalake/despesas.parquet")


def deduplicar():
    if not PATH.exists():
        return

    logger.info("Iniciando deduplicação massiva de despesas...")

    # 1. Carrega o arquivo
    df = pl.read_parquet(PATH)
    total_antes = len(df)

    # 2. Define a Chave de Unicidade Técnica
    # Se todos esses campos forem iguais, é o mesmo registro.
    unique_keys = [
        "id_deputado",
        "txtFornecedor",
        "dataDocumento",
        "vlrLiquido",
        "numDocumento",
        "txtDescricao",
    ]

    # 3. Executa a limpeza
    # keep='first' mantém apenas a primeira ocorrência
    df_limpo = df.unique(subset=unique_keys, keep="first")

    total_depois = len(df_limpo)
    removidos = total_antes - total_depois

    if removidos > 0:
        logger.info(f"✅ Sucesso! Removidos {removidos} registros duplicados.")
        # Sobrescreve o arquivo com a versão limpa
        df_limpo.write_parquet(PATH)
    else:
        logger.info("✅ O arquivo já estava limpo.")


if __name__ == "__main__":
    deduplicar()
