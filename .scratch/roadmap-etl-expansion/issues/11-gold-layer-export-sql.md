---
Status: ready-for-agent
Date: 2026-06-04
Area: gold
Fase: 3.5
---

# Gold Layer Export SQL (DuckDB)

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Adicionar funcionalidade de exportar a camada Gold (Parquet consolidado e
deduplicado) para formato SQL relacional, utilizando DuckDB.

O `DataLakeOptimizer` atualmente já lê todos os Parquet da Silver, aplica
`ROW_NUMBER() OVER (PARTITION BY {pk} ORDER BY captured_at DESC)` e escreve
Gold como Parquet em `data/datalake/gold/{dominio}/`.

A nova funcionalidade adiciona uma flag `--export-gold {sqlite|duckdb}` na CLI
que:

1. Lê cada tabela Gold via DuckDB
2. Cria um banco SQL (SQLite ou DuckDB) com a estrutura relacional
3. Escreve cada domínio como tabela SQL

Para SQLite:
```python
duckdb.execute("ATTACH 'data/gold_export.db' AS gold_db (TYPE SQLITE)")
duckdb.execute("CREATE TABLE gold_db.deputados AS SELECT * FROM read_parquet('data/datalake/gold/deputados/*.parquet')")
```

Para DuckDB (formato .db nativo):
```python
duckdb.execute("ATTACH 'data/gold_export.duckdb' AS gold_db")
duckdb.execute("CREATE TABLE gold_db.deputados AS SELECT * FROM read_parquet(...)")
```

## Acceptance criteria

- [x] CLI ganha `--export-gold` com opções `sqlite` e `duckdb`
- [x] Exporta todos os domínios Gold para SQL
- [x] Schemas SQL refletem os tipos dos `SILVER_SCHEMAS` (via DuckDB `CREATE TABLE AS SELECT`)
- [x] Inclui índices nas colunas de chave primária (se SQLite)
- [x] Documentação no README sobre como usar a exportação SQL
- [x] Teste de integração (exporta SQLite temp + lê algumas linhas)

## Blocked by

None — independente. Pode ser implementada em paralelo com Fases 2 e 3.
