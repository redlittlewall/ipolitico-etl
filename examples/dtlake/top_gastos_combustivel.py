from pathlib import Path

import duckdb

# Ajuste conforme o seu diretório real. (Ex: "data/datalake")
DATALAKE_PATH = Path("datalake")


def main():
    parquet_file = DATALAKE_PATH / "despesas.parquet"
    if not parquet_file.exists():
        print(f"Erro: Arquivo não encontrado em {parquet_file}")
        return

    conn = duckdb.connect()

    # ARQUITETURA MEDALLION (Em Memória)
    # 1. Camada Prata: Filtramos e usamos DISTINCT para ignorar o "lixo" contábil idêntico
    # 2. Camada Ouro: Somamos os valores limpos no SELECT principal
    query = f"""
        WITH despesas_limpas AS (
            SELECT DISTINCT
                id_deputado,
                nomeFornecedor,
                dataDocumento,
                numDocumento,
                CAST(valorLiquido AS DOUBLE) as valor_real
            FROM '{parquet_file}'
            WHERE txtDescricao ILIKE '%COMBUSTÍVEIS%'
               OR txtDescricao ILIKE '%COMBUSTIVEL%'
        )
        SELECT
            nomeFornecedor as Fornecedor,
            SUM(valor_real) as total_raw
        FROM despesas_limpas
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10
    """

    # Trazemos os dados consolidados para o Pandas
    df = conn.execute(query).df()

    # Formatação Monetária Brasileira à prova de falhas
    # Converte 1234567.89 para 'R$ 1.234.567,89'
    df["Total Gasto"] = df["total_raw"].apply(
        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    # Removemos a coluna feia antes de imprimir
    df = df.drop(columns=["total_raw"])

    print("\n=== 🏆 TOP 10 FORNECEDORES DE COMBUSTÍVEL (DADOS LIMPOS) ===")
    try:
        print(df.to_markdown(index=False))
    except ImportError:
        print(df)  # Fallback caso o tabulate não esteja instalado


if __name__ == "__main__":
    main()
