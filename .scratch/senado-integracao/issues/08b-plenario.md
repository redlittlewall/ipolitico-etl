---
Status: completed
Type: AFK
---

# Issue 08b — Plenário do Senado

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de plenário do Senado ponta-a-ponta:
`plenario_agenda` (agenda do dia), `plenario_resultados` (resultados
de votações em plenário), `plenario_sessoes` (sessões legislativas).

Estes são dados estruturalmente simples ("rasos") — o transformer pode ser
compartilhado entre os 3 domínios.

### Endpoints mapeados

| Endpoint | DomainType | Jobs |
|---|---|---|
| `GET /plenario/agenda/dia/{data}` | `PLENARIO_AGENDA` | 1 por dia |
| `GET /plenario/resultado/{data}` | `PLENARIO_RESULTADOS` | 1 por dia |
| `GET /plenario/legislatura/{data}` | `PLENARIO_SESSOES` | 1 por data |

### Já existente (não recriar)
- Todos os 3 `DomainType`s registrados
- `DomainSpec` para todos
- `EarliestDates` para todos
- `FULL_PIPELINE` configurado
- `SenadoBaseExtractor` (classe base)

### O que implementar

#### Schemas Silver (3 domínios)
- `SILVER_SCHEMAS[plenario_agenda]` — modelar schema
- `SILVER_SCHEMAS[plenario_resultados]` — modelar schema
- `SILVER_SCHEMAS[plenario_sessoes]` — modelar schema

#### Extratores (em `extractors/senado/api/plenario.py`)
- 3 classes, todas herdando de `SenadoBaseExtractor`

#### Transformers (em `transformers/senado/institucional_transformer.py`)
- Pode compartilhar o mesmo transformer da Issue 08a (dados rasos)

#### YAML
Adicionar em `configs/senado_pipeline.yaml` os 3 domínios

#### Testes
- `tests/extractors/senado/test_plenario.py` — mock httpx
- Testes de schema para transformer

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --full-load --domains plenario_agenda,plenario_resultados,plenario_sessoes
python -m ipolitico --audit-coverage | grep plenario
pytest -q tests/extractors/senado/test_plenario.py
```

## Acceptance criteria

- [x] 3 schemas Silver criados
- [x] 3 extratores implementados
- [x] Transformer(s) implementados
- [x] YAML com os 3 domínios
- [x] `python -m ipolitico pipeline --source senado --full-load --domains plenario_agenda,plenario_resultados,plenario_sessoes` executa sem erros
- [x] `--audit-coverage` mostra registros > 0
- [x] `pytest -q` passa

## Blocked by

None — infraestrutura base já completa.
