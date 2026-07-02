---
Status: completed
Type: AFK
---

# Issue 02 — Senadores

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar o domínio `senadores` (lista de senadores em exercício) e `senadores_detalhe` (detalhes de cada senador) ponta-a-ponta.

### Fluxo esperado

1. Extrator `SenadoresExtractor` chama `GET /senador/lista/atual` → retorna array de senadores
2. Para cada senador, `SenadoresDetalheExtractor` chama `GET /senador/{codigo}`
3. Transformers normalizam PascalCase → snake_case, achatam estrutura XML-heritage
4. Dados são salvos em Silver via `DataLakeSink`

### Endpoints mapeados

| Endpoint | DomainType | Jobs | Data path |
|---|---|---|---|
| `GET /senador/lista/atual` | `SENADORES` | 1 request | `["ListaParlamentarEmExercicio", "Parlamentares", "Parlamentar"]` |
| `GET /senador/{codigo}` | `SENADORES_DETALHE` | 1 por senador | `["DetalheParlamentar", "Parlamentar"]` |

### Arquivos

- `extractors/senado/api/senadores.py` — `SenadoresExtractor`
- `extractors/senado/api/senadores_detalhe.py` — `SenadoresDetalheExtractor`
- `transformers/senado/senadores_transformer.py`
- `transformers/senado/senadores_detalhe_transformer.py`
- `configs/senado_pipeline.yaml` — ambos mapeados

### Testes

- `tests/extractors/senado/test_senadores.py` — 4 testes
- `tests/extractors/senado/test_senadores_detalhe.py` — 4 testes
- `tests/transformers/test_senado_senadores_transformer.py` — 6 testes
- `tests/transformers/test_senado_senadores_detalhe_transformer.py` — 5 testes

## Current Status (2026-06-30)

✅ **COMPLETA** — Todos os itens foram implementados e testados.

**Nada mais a fazer nesta issue.**

## Acceptance criteria

- [x] `python -m ipolitico pipeline --source senado --full-load --domains senadores` executa sem erros
- [x] Dados aparecem em `data/datalake/silver/senadores/` e `data/datalake/silver/senadores_detalhe/`
- [x] Schema Silver tem campos normalizados (snake_case)
- [x] `pytest -q` passa em todos os testes novos e existentes

## Blocked by

Issue 01 — Core Infrastructure
