---
Status: completed
Type: AFK
---

# Issue 08c — Composição (Blocos, Lideranças, Mesas)

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de composição política do Senado ponta-a-ponta:
`blocos_senado` (blocos parlamentares), `liderancas_senado` (lideranças),
`mesa_senado` (mesa diretora do Senado), `mesa_congresso` (mesa diretora
do Congresso Nacional).

Estes são dados estruturalmente simples ("rasos") e de volume muito pequeno
— cada endpoint retorna poucos registros (1 job cada). O transformer pode
ser compartilhado entre os 4 domínios.

### Endpoints mapeados

| Endpoint | DomainType | Jobs |
|---|---|---|
| `GET /composicao/lista/blocos` | `BLOCOS_SENADO` | 1 request |
| `GET /composicao/lideranca` | `LIDERANCAS_SENADO` | 1 request |
| `GET /composicao/mesaSF` | `MESA_SENADO` | 1 request |
| `GET /composicao/mesaCN` | `MESA_CONGRESSO` | 1 request |

### Já existente (não recriar)
- Todos os 4 `DomainType`s registrados
- `DomainSpec` para todos
- `EarliestDates` para todos
- `FULL_PIPELINE` configurado
- `SenadoBaseExtractor` (classe base)

### O que implementar

#### Schemas Silver (4 domínios)
- `SILVER_SCHEMAS[blocos_senado]` — modelar schema
- `SILVER_SCHEMAS[liderancas_senado]` — modelar schema
- `SILVER_SCHEMAS[mesa_senado]` — modelar schema
- `SILVER_SCHEMAS[mesa_congresso]` — modelar schema

#### Extratores (em `extractors/senado/api/composicao.py`)
- 4 classes, todas herdando de `SenadoBaseExtractor`
- Cada uma faz 1 request único (sem iteração)

#### Transformers (em `transformers/senado/institucional_transformer.py`)
- Pode compartilhar o mesmo transformer das Issues 08a/08b (dados rasos)

#### YAML
Adicionar em `configs/senado_pipeline.yaml` os 4 domínios

#### Testes
- `tests/extractors/senado/test_composicao.py` — mock httpx para cada extrator
- Testes de schema para transformer

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --full-load --domains blocos_senado,liderancas_senado,mesa_senado
python -m ipolitico --audit-coverage | grep -E "blocos_senado|liderancas_senado|mesa"
pytest -q tests/extractors/senado/test_composicao.py
```

## Acceptance criteria

- [ ] 4 schemas Silver criados
- [ ] 4 extratores implementados
- [ ] Transformer(s) implementados
- [ ] YAML com os 4 domínios
- [ ] `python -m ipolitico pipeline --source senado --full-load --domains blocos_senado,liderancas_senado,mesa_senado` executa sem erros
- [ ] `--audit-coverage` mostra registros > 0
- [ ] `pytest -q` passa

## Blocked by

None — infraestrutura base já completa.
