import duckdb

conn = duckdb.connect()
query = """
    SELECT nomeFornecedor, SUM(valorLiquido) as total
    FROM '../datalake/despesas.parquet'
    WHERE tipoDespesa LIKE '%COMBUSTÍVEIS%'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
"""
print(conn.execute(query).df())
