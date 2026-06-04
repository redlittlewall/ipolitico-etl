---
Status: resolved
Date: 2026-06-04
Area: tools
Severity: medium
Source: code-review (angle C)
Type: bug
---

# ingestion_estimate.py superestima downloads bulk para domínios snapshot

## Finding

A função `estimate_domain()` em `src/ipolitico/tools/ingestion_estimate.py`:
linha 111 calcula `years = _years_inclusive(start_iso, end_iso)` e linha 115
define `bulk_downloads = years` — assumindo que todo bulk download é
particionado por ano.

Para domínios snapshot (granularidade `"snapshot"`), apenas **1** download é
necessário independentemente da janela temporal. Exemplo:
- `funcionarios` com earliest=1826-04-29 e FULL_LOAD até 2026 → estima **201** downloads (deveria ser **1**)
- Domínios existentes também afetados: `frentes` (earliest=2003) → estima 24 downloads (deveria ser 1)

## Impact

A ferramenta de estimativa (`examples/estimate_camara_ingestion.py`) produz
números irreais para domínios snapshot, podendo enganar planejamento de
recursos. A flag `--domains=list(DomainType)` (padrão) inclui todos os
domínios, então o erro aparece em qualquer execução padrão.

## Suggested fix

Na função `estimate_domain()`, consultar `bulk_granularity` do domínio
(do `DomainSpec` ou `BULK_REGISTRY`) antes de assumir yearly:

```python
granularity = spec.bulk_granularity if spec else BULK_REGISTRY.get(domain.value, {}).get("bulk_granularity")
if use_bulk:
    bulk = 1 if granularity == "snapshot" else years
```

## Location

- `src/ipolitico/tools/ingestion_estimate.py:111-119`
