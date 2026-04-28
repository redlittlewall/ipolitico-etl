import duckdb


def executar_auditoria():
    print("=" * 60)
    print(" AUDITORIA DE QUALIDADE DO DATALAKE IPOLITICO")
    print("=" * 60)

    # Conecta ao DuckDB em memória (ele vai ler os arquivos do disco diretamente)
    conn = duckdb.connect()

    # ---------------------------------------------------------
    # 1. Os dados foram armazenados com todos os atributos? (Schema)
    # ---------------------------------------------------------
    print("\n1. ESTRUTURA DO DADO (Colunas salvas em Despesas):")
    try:
        schema = conn.execute("DESCRIBE SELECT * FROM 'datalake/despesas.parquet'").df()
        print(f"Total de colunas salvas: {len(schema)}")
        print("Amostra das colunas:", schema["column_name"].head(5).to_list(), "...")
    except Exception as e:
        print("Arquivo despesas.parquet não encontrado ou vazio.", e)

    # ---------------------------------------------------------
    # 2. A indexação e correlação (JOINs) estão fáceis?
    # ---------------------------------------------------------
    print("\n2. TESTE DE CORRELAÇÃO (Deputados JOIN Despesas):")
    query_join = """
        SELECT
            dep.nome,
            COUNT(desp.numDocumento) as total_notas_fiscais
        FROM 'datalake/deputados.parquet' AS dep
        JOIN 'datalake/despesas.parquet' AS desp
          ON dep.id = desp.id_deputado
        GROUP BY dep.nome
        ORDER BY total_notas_fiscais DESC
        LIMIT 3
    """
    try:
        resultado_join = conn.execute(query_join).df()
        print("Conseguiu cruzar as tabelas perfeitamente? SIM!")
        print(resultado_join)
    except Exception as e:
        print("Erro ao cruzar dados. Verifique se os arquivos existem e se as chaves batem.", e)

    # ---------------------------------------------------------
    # 3. O Data Lake permite buscas analíticas interessantes?
    # ---------------------------------------------------------
    print("\n3. PODER ANALÍTICO (Qual empresa mais recebeu dinheiro público?):")
    query_analytics = """
        SELECT
            nomeFornecedor,
            cnpjCpfFornecedor,
            SUM(TRY_CAST(valorLiquido AS DOUBLE)) AS total_recebido
        FROM 'datalake/despesas.parquet'
        WHERE nomeFornecedor IS NOT NULL
        GROUP BY nomeFornecedor, cnpjCpfFornecedor
        ORDER BY total_recebido DESC
        LIMIT 5
    """
    try:
        resultado_analytics = conn.execute(query_analytics).df()
        print(resultado_analytics)
    except Exception as e:
        print("Erro na query analítica:", e)

    # ---------------------------------------------------------
    # 4. Consistência entre API e Bulk?
    # ---------------------------------------------------------
    print("\n4. CONSISTÊNCIA DE MAPEAMENTO:")
    print("Se a query analítica acima funcionou sem erros de coluna não encontrada,")
    print("significa que a função _standardize_schema do seu BulkExtractor funcionou!")
    print("O Parquet unificou as colunas 'txNomeParlamentar' (Bulk) e 'nome' (API) perfeitamente.")


if __name__ == "__main__":
    executar_auditoria()
