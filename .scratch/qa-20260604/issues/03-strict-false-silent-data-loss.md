---
Status: needs-triage
Date: 2026-06-04
Area: schemas
Severity: low
Source: code-review (angle G)
Type: tech-debt
---

# strict=False em _apply_contract silencia perda de dados sem logging

## Finding

A função `_apply_contract()` em `institutional_transformer.py` (linha 22) usa
`strict=False` em todos os casts de tipo. Se um valor for parsing como String
pelo CSV reader (porque `schema_overrides` não cobre aquela coluna) mas o
contrato SILVER_SCHEMA pede `pl.Int64`, o cast produz silenciosamente `None`.

Há dois níveis de silêncio:
1. `pl.read_csv(ignore_errors=True)` em `base_bulk.py:121` — linhas mal formatadas viram null
2. `cast(..., strict=False)` em `_apply_contract` — valores inparseáveis viram null

Sem logging em nenhum dos dois níveis, a perda de dados é invisível.

## Impact

**Cenário concreto**: se uma nova coluna numérica for adicionada ao
SILVER_SCHEMAS sem o correspondente `schema_overrides` no BULK_REGISTRY, o
CSV reader infere o tipo como String, e dados com formato não padronizado
(pontuação brasileira, prefixos) são silenciosamente anulados.

Para domínios bulk-only, isso afeta colunas de unique key (`codCategoria`,
`codTermo`, `codGrupo`), onde nulls comprometem a dedup na camada Gold.

## Suggested fix

Adicionar logging WARNING em `_apply_contract()` contando nulls após cast:

```python
null_count = df.select(pl.col(c).is_null().sum()).sum()
if null_count > 0:
    logger.warning("...")
```

## Location

- `src/ipolitico/transformers/camara/institutional_transformer.py:22`
- `src/ipolitico/extractors/camara/bulk/base_bulk.py:121`
