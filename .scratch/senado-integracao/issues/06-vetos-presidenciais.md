---
Status: completed
Type: AFK
---

# Issue 06 — Vetos Presidenciais

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de vetos presidenciais ponta-a-ponta:
`vetos_presidenciais` (lista de vetos por ano) e `vetos_detalhe`
(detalhes de cada veto).

**Importante:** São dados **exclusivos do Senado** — a Câmara dos Deputados
não oferece equivalente. Prioridade P0.

**Nota sobre endpoint:** Embora `/materia/vetos/{ano}` use o prefixo `/materia/`
(de endpoints deprecated do sistema MATE), este endpoint específico **não está
marcado como deprecated** no spec — é um dos poucos endpoints `/materia/`
ativos.

### Já existente (não recriar)
- `DomainType.VETOS_PRESIDENCIAIS`, `VETOS_DETALHE` registrados
- `DomainSpec` para ambos (detalhe depende de presidenciais)
- `EarliestDates` para ambos (1995-01-01)
- `FULL_PIPELINE` configurado
- `SenadoBaseExtractor` (classe base)

### O que implementar

#### Schemas Silver (2 domínios)
- `SILVER_SCHEMAS[vetos_presidenciais]` — modelar a partir de `GET /materia/vetos/{ano}`
- `SILVER_SCHEMAS[vetos_detalhe]` — modelar a partir de `GET /plenario/resultado/veto/{codigo}`

#### Extratores (em `extractors/senado/api/vetos.py`)
- `VetosPresidenciaisExtractor` — `GET /materia/vetos/{ano}`, 1 job por ano. O ano pode vir como parâmetro do planejador.
- `VetosDetalheExtractor` — `GET /plenario/resultado/veto/{codigo}`, 1 job por veto. Usar pattern de `entity_ids` (igual `SenadoSenadoresDetalheExtractor`).

#### Transformers (em `transformers/senado/vetos_transformer.py`)
- Aplicar schemas Silver

#### YAML
Adicionar em `configs/senado_pipeline.yaml` ambos os domínios

#### Testes
- `tests/extractors/senado/test_vetos.py` — mock httpx
- `tests/transformers/test_vetos_transformer.py` — DataFrame conhecido → schema

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --full-load --domains vetos_presidenciais
python -m ipolitico --audit-coverage | grep veto
pytest -q tests/extractors/senado/test_vetos.py tests/transformers/test_vetos_transformer.py
```

## Acceptance criteria

- [x] 2 schemas Silver criados
- [x] 2 extratores implementados
- [x] Transformer(s) implementados
- [x] YAML com ambos os domínios
- [x] `python -m ipolitico pipeline --source senado --full-load --domains vetos_presidenciais` executa sem erros
- [x] `--audit-coverage` mostra registros > 0
- [x] `pytest -q` passa

## Blocked by

None — infraestrutura base já completa.
