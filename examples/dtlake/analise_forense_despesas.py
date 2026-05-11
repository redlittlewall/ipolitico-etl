from pathlib import Path

import duckdb
import pandas as pd

# Ajuste conforme o seu diretório real
DATALAKE_PATH = Path("datalake")


def main():
    parquet_file = DATALAKE_PATH / "despesas_old.parquet"
    if not parquet_file.exists():
        print(f"Erro: Arquivo não encontrado em {parquet_file}")
        return

    conn = duckdb.connect()

    # 1. Pegamos 3 Códigos de Documento (que não sejam vazios/zero) que se repetem
    # 2. Puxamos todas as linhas exatas desses documentos para inspecionar
    query = f"""
        WITH chaves_duplicadas AS (
            SELECT codDocumento, numParcela
            FROM '{parquet_file}'
            WHERE codDocumento IS NOT NULL
              AND CAST(codDocumento AS VARCHAR) != '0'
              AND CAST(codDocumento AS VARCHAR) != ''
            GROUP BY codDocumento, numParcela
            HAVING COUNT(*) > 1
            LIMIT 3
        )
        SELECT
            d.codDocumento,
            d.numParcela,
            d.dataDocumento,
            d.nomeFornecedor,
            d.txtDescricao,
            d.valorDocumento,
            d.vlrGlosa,
            d.valorLiquido
        FROM '{parquet_file}' d
        JOIN chaves_duplicadas cd
          ON d.codDocumento = cd.codDocumento
         AND d.numParcela = cd.numParcela
        ORDER BY d.codDocumento, d.valorLiquido DESC
    """

    df = conn.execute(query).df()

    print("\n=== 🔎 ESTUDO DE CASO: O JOGO DOS 7 ERROS NAS DUPLICATAS ===")
    print("O que muda entre as linhas do mesmo documento?\n")

    # Configurando o Pandas para não esconder colunas no print
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)

    try:
        print(df.to_markdown(index=False))
    except ImportError:
        print(df)


if __name__ == "__main__":
    main()
