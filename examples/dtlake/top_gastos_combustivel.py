"""TOP 10 Fornecedores de Combustível — Camada Gold.

Domínios utilizados: despesas
"""

from pathlib import Path

import duckdb

DATALAKE_PATH = Path("data/datalake/gold")


def main():
    parquet_file = DATALAKE_PATH / "despesas" / "despesas.parquet"
    if not parquet_file.exists():
        print(f"Erro: Arquivo não encontrado em {parquet_file}")
        return

    conn = duckdb.connect()

    query = f"""
        SELECT
            nomeFornecedor as Fornecedor,
            SUM(CAST(valorLiquido AS DOUBLE)) as total_raw
        FROM '{parquet_file}'
        WHERE tipoDespesa ILIKE '%COMBUSTÍVEL%'
           OR nomeFornecedor ILIKE '%COMBUSTIVEL%'
           OR tipoDespesa ILIKE '%COMBUSTIVEL%'
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10
    """

    df = conn.execute(query).df()

    # Formatação Monetária Brasileira
    df["Total Gasto"] = df["total_raw"].apply(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    df = df.drop(columns=["total_raw"])

    print("\n=== 🏆 TOP 10 FORNECEDORES DE COMBUSTÍVEL (DADOS LIMPOS) ===")
    try:
        print(df.to_markdown(index=False))
    except ImportError:
        print(df)


if __name__ == "__main__":
    main()
