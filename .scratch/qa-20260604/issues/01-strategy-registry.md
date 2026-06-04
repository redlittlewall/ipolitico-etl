---
Status: needs-triage
Date: 2026-06-04
Area: pipeline
Severity: medium
Source: code-review (angle B + angle G)
Type: tech-debt
---

# STRATEGY_REGISTRY sem entradas para domínios bulk-only snapshot

## Finding

Os 3 novos domínios bulk-only (`funcionarios`, `tecad_categorias`, `tecad_termos`)
não estão registrados em `STRATEGY_REGISTRY` em
`src/ipolitico/pipeline/planners/strategies.py`. A função `strategy_for()`
retorna `DefaultWindowStrategy()` como fallback, que emite jobs com
`start_date`/`end_date` que são silenciosamente descartados via `**kwargs`
no `BaseBulkExtractor.extract()`.

## Impact

**Funciona por acidente.** `BaseBulkExtractor.extract()` aceita `**kwargs` e
ignora `start_date`/`end_date` — mas se um dia `**kwargs` for removido (ex:
migração para parâmetros explícitos), os 3 domínios quebram com:

```
TypeError: extract() got unexpected keyword arguments 'start_date', 'end_date'
```

Além disso, `DefaultWindowStrategy.build()` particiona jobs por ano para outros
domínios — se a lógica mudar, snapshot domains podem receber N jobs duplicados.

## Suggested fix

Registrar os 3 domínios em `STRATEGY_REGISTRY` com uma estratégia snapshot-aware
(ou o `SnapshotWindowStrategy` já existente para outros domínios snapshot):

```python
DomainType.FUNCIONARIOS: SnapshotWindowStrategy,
DomainType.TECAD_CATEGORIAS: SnapshotWindowStrategy,
DomainType.TECAD_TERMOS: SnapshotWindowStrategy,
```

## Location

- `src/ipolitico/pipeline/planners/strategies.py:1066` — fim de STRATEGY_REGISTRY
- `src/ipolitico/extractors/camara/bulk/base_bulk.py:67` — `extract(**kwargs)` que engole os parâmetros
