---
Status: in-progress
Date: 2026-06-04
Area: senado
Fase: 4
Progress: ~20%
Last Update: 2026-06-30
---

# Implementar SenadoSourceProvider + primeiros domínios

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## Current Status (2026-06-30)

### ✅ Já implementado (após auditoria de código):
- Issue 01 — Core Infrastructure: **100% completa** (client, base extractor, 30 DomainTypes, Federation, CLI)
- Issue 02 — Senadores: **100% completa** (lista + detalhe, transformers, testes)
- Issue 03 — Processos: **100% completa** (extractor, transformer, testes, YAML)
- Issue 04 — Votações e Votos: **100% completa** (extractors, transformers, testes, YAML)
- Schemas Silver para 5 domínios: `senadores`, `senadores_detalhe`, `processos`, `votacoes_senado`, `votos_senado`
- `configs/senado_pipeline.yaml` com 5 domínios mapeados

### ❌ Falta implementar:
- **25 schemas Silver** para os demais domínios
- **~25 extratores** (um para cada endpoint ativo do Senado)
- **~8 transformers** para cada grupo de domínios
- **Testes** para cada extrator e transformer

### Issues pendentes:
Ver `.scratch/senado-integracao/issues/`:
- `05-emendas-orcamentarias.md` — 2 domínios P0 (exclusivo Senado)
- `06-vetos-presidenciais.md` — 2 domínios P0 (exclusivo Senado)
- `07-discursos.md` — 5 domínios P0.5
- `08a-comissoes.md` — 4 domínios P1
- `08b-plenario.md` — 3 domínios P1
- `08c-composicao.md` — 4 domínios P1

## What to build

Após a pesquisa e documentação da API do Senado (issue 12), implementar o adapter seguindo o protocolo `SourceProvider`, análogo ao `CamaraSourceProvider`.

Estrutura nova:

```
src/ipolitico/
├── core/
│   ├── senado_client.py         ← criado
│   ├── camara_client.py          ← renomeado
├── extractors/senado/            ← senadores (completo), processos (pendente), etc.
├── transformers/senado/          ← senadores (completo), processos (pendente), etc.
├── sources/
│   └── senado_provider.py        ← criado
└── ...
```

O `SenadoSourceProvider` implementa a mesma interface que
`CamaraSourceProvider`, permitindo que o `FederationOrchestrator` execute
ambos.

## Acceptance criteria

- [x] `core/senado_client.py` com semáforo 5 e retry
- [x] `SenadoBaseExtractor` com fetch_flat, flatten_response, _ensure_list
- [x] 30 DomainTypes registrados com DomainSpec, EarliestDates, FULL_PIPELINE
- [x] CLI `--source {camara, senado, all}`
- [x] FederationOrchestrator genérico
- [x] SenadoSourceProvider e SenadoMetadataService
- [x] Extratores e transformers para senadores (lista + detalhe) — completo
- [x] Extratores e transformers para processos — **completo (Issue 03)**
- [x] Extratores e transformers para votações e votos — **completo (Issue 04)**
- [ ] Extratores e transformers para emendas orçamentárias — **pendente (Issue 05)**
- [ ] Extratores e transformers para vetos — **pendente (Issue 06)**
- [ ] Extratores e transformers para discursos — **pendente (Issue 07)**
- [ ] Extratores e transformers para comissões, plenário, composição — **pendente (Issues 08a/08b/08c)**
- [ ] `senado_pipeline.yaml` populado com todos os domínios
- [ ] Testes unitários para todos os extratores e transformers
- [ ] `pytest -q` passando

## Blocked by

[12 - Pesquisar e documentar a API do Senado](12-senado-pesquisa-documentacao.md) — **completada**
