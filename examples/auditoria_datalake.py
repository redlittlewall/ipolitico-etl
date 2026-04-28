import duckdb


def executar_auditoria_profunda():
    print("=" * 70)
    print(" 🔎 AUDITORIA DE INTEGRIDADE E TIPAGEM - iPolitico")
    print("=" * 70)

    conn = duckdb.connect()

    # 1. VERIFICAÇÃO DE SCHEMAS (TIPOS DE DADOS)
    print("\n[1] Verificação de dtypes (Os dados são do tipo certo?):")
    tables = {"deputados": "datalake/deputados.parquet", "despesas": "datalake/despesas.parquet"}

    for name, path in tables.items():
        try:
            # Pegamos o schema direto do arquivo via DuckDB
            info = conn.execute(f"DESCRIBE SELECT * FROM '{path}'").df()
            print(f"\n📌 Tabela: {name}")
            # Filtramos as colunas mais críticas para conferir o tipo
            print(info[["column_name", "column_type"]])
        except Exception as e:
            print(f"Erro ao ler {path}: {e}")

    # 2. VALIDAÇÃO DE VALORES E FORMATAÇÃO (O fim do 'e+05')
    print("\n[2] Top 5 Maiores Gastadores (Valores formatados):")
    query = """
        SELECT
            nomeFornecedor,
            -- Formatamos para moeda brasileira na query para validação visual
            printf('R$ %.2f', SUM(CAST(valorLiquido AS DOUBLE))) AS total_formatado,
            -- Mantemos o valor real para ordenação correta
            SUM(CAST(valorLiquido AS DOUBLE)) AS valor_num
        FROM 'datalake/despesas.parquet'
        GROUP BY nomeFornecedor
        ORDER BY valor_num DESC
        LIMIT 5
    """
    try:
        df_ranking = conn.execute(query).df()
        # Removemos a coluna auxiliar de ordenação para o print ficar limpo
        print(df_ranking[["nomeFornecedor", "total_formatado"]])
    except Exception as e:
        print(f"Erro na query analítica: {e}")

    # 3. TESTE DE CONSISTÊNCIA DE DATAS
    print("\n[3] Range temporal detectado no Data Lake:")
    try:
        # Tenta extrair a menor e maior data para ver se o formato ISO-8601 está preservado
        range_datas = conn.execute("""
            SELECT
                MIN(dataDocumento) as primeira_despesa,
                MAX(dataDocumento) as ultima_despesa
            FROM 'datalake/despesas.parquet'
        """).df()
        print(range_datas)
    except Exception as e:
        print(f"Erro ao validar datas: {e}")


if __name__ == "__main__":
    executar_auditoria_profunda()
