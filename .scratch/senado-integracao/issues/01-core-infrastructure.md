---
Status: completed
Type: HITL
Completed: 2026-06-30
---

# Issue 01 — Core Infrastructure (Senado)

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

A branch nova `feat/senado-api` deve ser criada a partir de `feat/integration-test-and-examples`. Esta issue estabelece toda a infraestrutura base para o Senado rodar ao lado da Câmara. Nenhum domínio específico é implementado aqui — só os trilhos.

### O que fazer

1. **Criar branch:** `feat/senado-api` a partir de `feat/integration-test-and-examples`
2. **Renomear** `core/client.py` → `core/camara_client.py` (classe `CamaraClient` intacta). Atualizar todos os 13 imports.
3. **Adicionar env vars** em `core/config.py`: `SENADO_API_BASE_URL` e `SENADO_HTTP_CONCURRENCY=5`
4. **Criar `core/senado_client.py`**: classe `SenadoClient` com semáforo próprio (5), retry tenacity, método `fetch()`
5. **Criar `SenadoBaseExtractor`** em `extractors/senado/api/senado_base.py`:
   - Herda de `BaseExtractor`
   - `fetch_flat(endpoint, params)` — chamada única sem paginação
   - `flatten_response(data, data_path)` — desaninha envelope XML-heritage
   - `_ensure_list(item)` — normaliza objeto-único para lista
6. **Adicionar novos `DomainType`s** em `core/constants.py` (cabeçalhos, sem implementação):
   - `SENADORES`, `SENADORES_DETALHE`, `PROCESSOS`, `PROCESSOS_DETALHE`, `PROCESSOS_EMENDAS`, `PROCESSOS_DOCUMENTOS`
   - `VOTACOES_SENADO`, `VOTOS_SENADO`, `VOTACOES_COMISSAO`
   - `ORCAMENTO_EMENDAS`, `ORCAMENTO_OFICIOS`
   - `VETOS_PRESIDENCIAIS`, `VETOS_DETALHE`
   - `SENADORES_DISCURSOS`, `DISCURSOS_PLENARIO`, `DISCURSOS_TEXTO`
   - `NOTAS_TAQUIGRAFIA_SESSAO`, `NOTAS_TAQUIGRAFIA_REUNIAO`
   - `COMISSOES_SENADO`, `COMISSOES_DETALHE`, `COMISSOES_REUNIOES`, `COMISSOES_MEMBROS`
   - `PLENARIO_AGENDA`, `PLENARIO_RESULTADOS`, `PLENARIO_SESSOES`
   - `BLOCOS_SENADO`, `LIDERANCAS_SENADO`, `MESA_SENADO`, `MESA_CONGRESSO`
7. **Expandir `FULL_PIPELINE`** em `domain_order.py` — adicionar os novos domínios após os da Câmara
8. **Adicionar `DomainSpec`s** em `core/domain_spec.py` para cada novo domínio (earliest dates, dependências)
9. **Adicionar `DOMAIN_LABELS`** em `core/constants.py` para cada novo domínio
10. **Criar `configs/senado_pipeline.yaml`** com cabeçalho vazio (só `domain_configs: {}` — preenchido nas issues seguintes)
11. **Adicionar flag `--source {camara, senado, all}`** na CLI (`main.py`). Valor padrão: `all`
12. **Generalizar `FederationOrchestrator`** para aceitar lista genérica de `SourceProvider` (remover tipo `CamaraSourceProvider` hardcoded)
13. **Tornar `PipelineManager` genérico**: `CamaraJobPlanner` → `JobPlanner`, remover fallback `CamaraMetadataService` hardcoded, passar a injetar
14. **Criar `services/senado_metadata.py`**: `SenadoMetadataService` simplificado (versão básica sem consulta à API — retorna legislatura atual por ano)
15. **Criar `sources/senado_provider.py`**: `SenadoSourceProvider` seguindo o protocolo existente, carregando `senado_pipeline.yaml`
16. **Criar `tests/core/test_senado_client.py`**: teste mockado do `SenadoClient.fetch()`
17. **Criar `tests/extractors/senado/test_senado_base.py`**: teste de `flatten_response()` e `_ensure_list()`

## Current Status (2026-06-30)

✅ **COMPLETA** — Todos os itens foram implementados e testados.

### Confirmado:
- [x] `core/camara_client.py` — renomeado, imports atualizados
- [x] `core/senado_client.py` — semáforo 5, retry, fetch()
- [x] `extractors/senado/api/senado_base.py` — `fetch_flat`, `flatten_response`, `_ensure_list`
- [x] 30 `DomainType`s do Senado registrados em `constants.py`
- [x] `DomainSpec`, `EarliestDates`, `DOMAIN_LABELS` para todos
- [x] `FULL_PIPELINE` — Senado incluso após Câmara
- [x] `configs/senado_pipeline.yaml` — cabeçalho criado
- [x] CLI `--source {camara, senado, all}` em `main.py`
- [x] `FederationOrchestrator` genérico
- [x] `PipelineManager` genérico com `metadata_service` injetado
- [x] `services/senado_metadata.py`
- [x] `sources/senado_provider.py`
- [x] `tests/core/test_senado_client.py` — 4 testes
- [x] `tests/extractors/senado/test_senado_base.py` — 6 testes
- [x] `pytest -q` passando

**Nada mais a fazer nesta issue.**

## Acceptance criteria

- [ ] Branch `feat/senado-api` criada a partir de `feat/integration-test-and-examples`
- [ ] `core/client.py` renomeado para `core/camara_client.py` e todos os imports atualizados
- [ ] `pytest -q tests/core/` passa (incluindo testes existentes do CamaraClient)
- [ ] `SenadoClient` criado com semáforo 5 e retry
- [ ] `SenadoBaseExtractor` com `fetch_flat`, `flatten_response`, `_ensure_list`
- [ ] Novos `DomainType`s registrados em `DomainType`, `DOMAIN_SPECS`, `DOMAIN_LABELS`, `EARLIEST_DATE_MAP`, `FULL_PIPELINE`
- [ ] `python -m ipolitico pipeline --source senado --list-domains` mostra os novos domínios agrupados
- [ ] `python -m ipolitico pipeline --source all --list-domains` mostra Câmara + Senado
- [ ] `configs/senado_pipeline.yaml` existe com cabeçalho
- [ ] `pytest -q tests/extractors/senado/test_senado_base.py` passa
- [ ] Commit com mensagem convencional

## Blocked by

None — can start immediately
