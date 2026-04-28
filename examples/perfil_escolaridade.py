# Mostra a força da sua indexação e correlação
query = """
    SELECT escolaridade, COUNT(*) as qtd
    FROM '../datalake/deputados_detalhes.parquet'
    GROUP BY 1 ORDER BY 2 DESC
"""
