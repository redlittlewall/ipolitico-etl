"""Análise Forense: Documentos Duplicados em Despesas.

Domínios utilizados: despesas (camada Gold)
"""

from pathlib import Path

import duckdb
import pandas as pd

DATALAKE_PATH = Path("data/datalake/gold")


def main():
    parquet_file = DATALAKE_PATH / "despesas" / "despesas.parquet"
    if not parquet_file.exists():
        print(f"Erro: Arquivo não encontrado em {parquet_file}")
        return

    conn = duckdb.connect()

    # Busca documentos que aparecem mais de uma vez com mesmo código+parcela
    query = f"""
        WITH chaves_duplicadas AS (
            SELECT codDocumento, parcela
            FROM '{parquet_file}'
            WHERE codDocumento IS NOT NULL
              AND CAST(codDocumento AS VARCHAR) != '0'
              AND CAST(codDocumento AS VARCHAR) != ''
            GROUP BY codDocumento, parcela
            HAVING COUNT(*) > 1
            LIMIT 3
        )
        SELECT
            d.codDocumento,
            d.parcela,
            d.dataDocumento,
            d.nomeFornecedor,
            d.tipoDespesa,
            d.valorDocumento,
            d.valorGlosa,
            d.valorLiquido
        FROM '{parquet_file}' d
        JOIN chaves_duplicadas cd
          ON d.codDocumento = cd.codDocumento
         AND d.parcela = cd.parcela
        ORDER BY d.codDocumento, d.valorLiquido DESC
    """

    df = conn.execute(query).df()

    print("\n=== 🔎 ESTUDO DE CASO: O JOGO DOS 7 ERROS NAS DUPLICATAS ===")
    print("O que muda entre as linhas do mesmo documento?\n")

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)

    try:
        print(df.to_markdown(index=False))
    except ImportError:
        print(df)


if __name__ == "__main__":
    main()
