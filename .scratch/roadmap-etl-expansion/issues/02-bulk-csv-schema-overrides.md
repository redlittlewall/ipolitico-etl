---
Status: ready-for-agent
Date: 2026-06-04
Area: arquitetura
Fase: 1
---

# Bulk CSV com schema_overrides + locale BR

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Adicionar `schema_overrides` no `BULK_REGISTRY` para que o
`BaseBulkExtractor.extract()` passe `schema_overrides=` para `pl.read_csv()`,
eliminando o segundo passe de conversão de tipos nos transformers.

Incluir suporte a locale BR: colunas de moeda brasileira (ex: `vlrLiquido` com
formato `1.234,56`) continuam como `pl.Utf8` no schema override e a conversão
para `Float64` (`str.replace(",", ".") → cast`) é centralizada num helper
reutilizável no transformer.

Aplicar para todos os 5 datasets do `BULK_REGISTRY` atuais: `deputados`,
`despesas`, `proposicoes`, `votacoes`, `votos`.

## Acceptance criteria

- [ ] `BULK_REGISTRY` tem campo `schema_overrides` para cada dataset existente
- [ ] `BaseBulkExtractor.extract()` aplica `schema_overrides` no `pl.read_csv()`
- [ ] Helper de locale BR (moeda `1.234,56` → `Float64`) é extraído e
      reutilizado nos transformers de Bulk
- [ ] Testes unitários do `BaseBulkExtractor` validam schema_overrides com CSV fixture
- [ ] Testes de transformers Bulk validam conversão de locale BR
- [ ] `pytest -q` passando (sem quebra de regressão)

## Blocked by

None — independente da issue 03.
