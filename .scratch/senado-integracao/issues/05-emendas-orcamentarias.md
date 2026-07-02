---
Status: completed
Type: AFK
---

# Issue 05 — Emendas Orçamentárias

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de orçamento do Senado ponta-a-ponta:
`orcamento_emendas` (emendas ao orçamento de autoria de senadores) e
`orcamento_oficios` (ofícios orçamentários).

**Importante:** São dados **exclusivos do Senado** — a Câmara dos Deputados
não oferece equivalente. Prioridade P0.

### Já existente (não recriar)
- `DomainType.ORCAMENTO_EMENDAS`, `ORCAMENTO_OFICIOS` registrados
- `DomainSpec` para ambos
- `EarliestDates` para ambos (2000-01-01)
- `FULL_PIPELINE` configurado
- `SenadoBaseExtractor` (classe base)

### O que implementar

#### Schemas Silver (2 domínios)
- `SILVER_SCHEMAS[orcamento_emendas]` — modelar schema a partir do endpoint `GET /orcamento/lista`
- `SILVER_SCHEMAS[orcamento_oficios]` — modelar schema a partir do endpoint `GET /orcamento/oficios`

#### Extratores (em `extractors/senado/api/orcamento.py`)
- `OrcamentoEmendasExtractor` — `GET /orcamento/lista`, 1 job por ano
- `OrcamentoOficiosExtractor` — `GET /orcamento/oficios`, 1 job por ano
- Data paths: verificar no spec da API

#### Transformers (em `transformers/senado/orcamento_transformer.py`)
- Aplicar schemas Silver (normalização de nomes, tipagem)

#### YAML
Adicionar em `configs/senado_pipeline.yaml` ambos os domínios

#### Testes
- `tests/extractors/senado/test_orcamento.py` — mock httpx
- `tests/transformers/test_orcamento_transformer.py` — DataFrame conhecido → schema

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --full-load --domains orcamento_emendas
python -m ipolitico --audit-coverage | grep orcamento
pytest -q tests/extractors/senado/test_orcamento.py tests/transformers/test_orcamento_transformer.py
```

## Acceptance criteria

- [x] 2 schemas Silver criados
- [x] 2 extratores implementados
- [x] Transformer(s) implementados
- [x] YAML com ambos os domínios
- [x] Estratégia anual registrada (AnnualWindowStrategy)
- [x] `pytest -q` passa (470 passed)

## Blocked by

None — infraestrutura base já completa.
