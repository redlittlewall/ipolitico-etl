---
Status: completed
Type: AFK
---

# Issue 03 — Processos Legislativos do Senado

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de processos legislativos do Senado ponta-a-ponta:
`processos` (lista), `processos_detalhe` (detalhes por ID), `processos_emendas`,
`processos_documentos`.

**Nota:** `processos_relatorias` existe como DomainType no enum mas não tem
endpoint mapeado no PRD original — não implementar.

### Já existente (não recriar)
- `DomainType.PROCESSOS`, `PROCESSOS_DETALHE`, `PROCESSOS_EMENDAS`, `PROCESSOS_DOCUMENTOS` registrados
- `DomainSpec` para todos (watermark column, dependências, unique keys)
- `EarliestDates` para todos
- `FULL_PIPELINE` e `DOMAIN_UPSTREAM_REQUIREMENTS` configurados
- `SILVER_SCHEMA` para `processos` (10 campos: id, codigo_materia, identificacao, ementa, autoria, tipo_documento, data_apresentacao, situacao_atual, data_situacao, casa_identificadora, tramitando)
- `SenadoBaseExtractor` (classe base com `fetch_flat`, `flatten_response`, `_ensure_list`)

### O que implementar

#### Schemas Silver (4 domínios)
Adicionar em `src/ipolitico/core/schemas.py`:
- `SILVER_SCHEMAS[processos_detalhe]` — modelar a partir do endpoint `GET /processo/{id}`
- `SILVER_SCHEMAS[processos_emendas]` — modelar a partir do endpoint `GET /processo/emenda`
- `SILVER_SCHEMAS[processos_documentos]` — modelar a partir do endpoint `GET /processo/documento`

#### Extratores (em `extractors/senado/api/processos.py`)
Criar 4 classes, todas herdando de `SenadoBaseExtractor`:
- `ProcessosExtractor` — `GET /processo` com parâmetros `dataInicio`/`dataFim` (janela mensal). Data path: verificar no spec (provavelmente top-level array)
- `ProcessosDetalheExtractor` — `GET /processo/{id}`, 1 job por processo. Herdar entity_ids pattern igual `SenadoSenadoresDetalheExtractor`
- `ProcessosEmendasExtractor` — `GET /processo/emenda` com janela mensal
- `ProcessosDocumentosExtractor` — `GET /processo/documento` com janela mensal

#### Transformers (em `transformers/senado/processos_transformer.py`)
- Criar transformers que aplicam schemas Silver (normalização de nomes, tipagem)
- Podem ser transformers separados ou um só com lógica de dispatch

#### YAML
Adicionar em `configs/senado_pipeline.yaml` os 4 domínios com seus extratores e transformers

#### Testes
- `tests/extractors/senado/test_processos.py` — mock httpx/respx para cada extrator
- `tests/transformers/test_processos_transformer.py` — DataFrame conhecido → schema Silver

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --full-load --domains processos
python -m ipolitico --audit-coverage | grep -E "processos|emendas|documentos"
pytest -q tests/extractors/senado/test_processos.py tests/transformers/test_processos_transformer.py
```

## Acceptance criteria

- [ ] `SILVER_SCHEMAS` para `processos_detalhe`, `processos_emendas`, `processos_documentos` criados
- [ ] 4 extratores implementados em `extractors/senado/api/processos.py`
- [ ] Transformers criados em `transformers/senado/processos_transformer.py`
- [ ] `configs/senado_pipeline.yaml` com os 4 domínios mapeados
- [ ] `python -m ipolitico pipeline --source senado --full-load --domains processos` executa sem erros
- [ ] `--audit-coverage` mostra registros > 0 para cada domínio
- [ ] `pytest -q` passa em todos os testes novos e existentes

## Blocked by

None — infraestrutura base (Issue 01) e senadores (Issue 02) já estão completos.
