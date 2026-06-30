---
Status: completed
Type: AFK
---

# Issue 08a — Comissões do Senado

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de comissões do Senado ponta-a-ponta:
`comissoes_senado` (lista de comissões), `comissoes_detalhe` (detalhes),
`comissoes_reunioes` (agenda de reuniões), `comissoes_membros`
(composição de membros).

Estes são dados estruturalmente simples ("rasos") — o transformer pode ser
compartilhado entre os 4 domínios, similar ao `InstitutionalTransformer`
da Câmara.

### Endpoints mapeados

| Endpoint | DomainType | Jobs |
|---|---|---|
| `GET /comissao/lista/{tipo}` | `COMISSOES_SENADO` | 1 por tipo |
| `GET /comissao/{codigo}` | `COMISSOES_DETALHE` | 1 por comissão |
| `GET /comissao/agenda/{inicio}/{fim}` | `COMISSOES_REUNIOES` | Período |
| Composição via `/composicao/comissao/{codigo}` | `COMISSOES_MEMBROS` | 1 por comissão |

### Já existente (não recriar)
- Todos os 4 `DomainType`s registrados
- `DomainSpec` para todos (com dependências: detalhe/reunioes/membros dependem de comissoes_senado)
- `EarliestDates` para todos
- `FULL_PIPELINE` e `DOMAIN_UPSTREAM_REQUIREMENTS` configurados
- `SenadoBaseExtractor` (classe base)

### O que implementar

#### Schemas Silver (4 domínios)
- `SILVER_SCHEMAS[comissoes_senado]` — modelar schema
- `SILVER_SCHEMAS[comissoes_detalhe]` — modelar schema
- `SILVER_SCHEMAS[comissoes_reunioes]` — modelar schema
- `SILVER_SCHEMAS[comissoes_membros]` — modelar schema

#### Extratores (em `extractors/senado/api/comissoes.py`)
- 4 classes, todas herdando de `SenadoBaseExtractor`

#### Transformers (em `transformers/senado/institucional_transformer.py`)
- 1 transformer compartilhado para dados rasos (mesmo padrão do `InstitutionalTransformer` da Câmara)

#### YAML
Adicionar em `configs/senado_pipeline.yaml` os 4 domínios

#### Testes
- `tests/extractors/senado/test_comissoes.py` — mock httpx para cada extrator
- `tests/transformers/test_senado_institucional_transformer.py` — DataFrame conhecido → schema

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --full-load --domains comissoes_senado
python -m ipolitico --audit-coverage | grep comissoes
pytest -q tests/extractors/senado/test_comissoes.py
```

## Acceptance criteria

- [ ] 4 schemas Silver criados
- [ ] 4 extratores implementados
- [ ] Transformer(s) implementados
- [ ] YAML com os 4 domínios
- [ ] `python -m ipolitico pipeline --source senado --full-load --domains comissoes_senado` executa sem erros
- [ ] `--audit-coverage` mostra registros > 0
- [ ] `pytest -q` passa

## Blocked by

None — infraestrutura base já completa.
