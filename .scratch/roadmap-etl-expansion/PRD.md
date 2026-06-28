---
Status: ready-for-agent
Date: 2026-06-04
Area: arquitetura
---

# PRD: iPolitico ETL — Roadmap de Expansão (Fases 0–4)

> **Nota:** Este documento foi revisado em 2026-06-04 para refletir o estado real
> do código. As Fases 0–3 foram concluídas; o conteúdo original foi preservado
> como histórico, com anotações de status. A Fase 4 (Senado) permanece como
> próximo trabalho.

## Status Atual

| Fase | Descrição | Status | Evidência |
|---|---|---|---|
| **0** | Remoção das subclasses Bulk rasas | ✅ CONCLUÍDO | Subclasses removidas, `BaseBulkExtractor` unificado |
| **1** | Bulk CSV schema_overrides + StateStore + remoção SQLiteSink | ✅ CONCLUÍDO | `schema_overrides` em `BULK_REGISTRY`, `StateStore` em `storage/state_store.py`, `DataLakeRepository implements StateStore`, `SQLiteSink` removido |
| **2** | 4 endpoints API faltantes + Swagger-to-code + expansão Bulk | ✅ CONCLUÍDO | `blocos_detalhe`, `proposicoes_detalhe`, `eventos_orgaos`, `mandatos_externos` — todos com extrator/transformer/YAML. `tools/swagger_codegen.py` com testes. `BULK_REGISTRY` expandido com 13 datasets institucionais |
| **3** | Bulk-only domains | ✅ CONCLUÍDO | 12 domínios (licitacoes, funcionarios, tecad, eventos_*, votacoes_*) com YAML, transformer, SILVER_SCHEMA, BULK_REGISTRY |
| **3.5** | Validação Integrada do ETL | ⚠️ PARCIAL | 23 domínios 100%, 12 abortados (bulk mapping), 28 não iniciados, 1 parcial. 4 bugs corrigidos. |
| **4** | Senado API Adapter | ⏳ PENDENTE | Documentação da API do Senado ainda não coletada |

### Métricas (atualizado 2026-06-05)

- **64 domínios registrados** no `DomainType`
- **23 domínios validados** contra API real (Silver populado)
- **19 domínios** com `extractor_bulk` no YAML (rota Bulk disponível)
- **351 testes** passando (`pytest -q`)
- **78 rotas Swagger** da Câmara — todas cobertas
- **Gold exporter** (`--export-gold sqlite|duckdb`) já implementado
- **4 bugs** encontrados e corrigidos durante validação integrada
- **249 MB** de dados Silver gerados na execução parcial

---

## Problem Statement

O ETL da Câmara dos Deputados do iPolitico foi expandido para cobrir todos os
domínios da API, com suporte Bulk e arquitetura preparada para múltiplos providers.
Porém, nunca foi executado de ponta a ponta com todos os domínios simultaneamente:

1. **Validação integrada nunca realizada** — os 351 testes unitários cobrem cada
   peça isoladamente, mas nenhuma execução real contra a API da Câmara validou
   o encadeamento de extratores + transformers + sinks + state store + gold
   em cenário real.

2. **Risco de regressão silenciosa** — sem uma execução E2E de referência,
   mudanças futuras (especialmente a Fase 4 — Senado) podem quebrar o pipeline
   Câmara sem que os testes unitários percebam.

3. **✅ Parcialmente endereçado** — a 1ª execução full load (2026-06-05) rodou
   23/64 domínios (100%) antes de ser interrompida. 4 bugs foram corrigidos.
   Faltam 44 domínios para cobertura completa.

---

## Resultados da 1ª Execução Full Load (2026-06-05)

### Status por Domínio

| Status | Qtd | Domínios |
|---|---|---|
| ✅ 100% concluído | **23** | deputados, deputados_detalhe, legislaturas, legislaturas_detalhe, legislaturas_lideres, legislaturas_mesa, blocos, blocos_partidos, frentes, frentes_detalhe, frentes_membros, grupos, orgaos, partidos, partidos_detalhe, partidos_membros, partidos_lideres, despesas, proposicoes, discursos, deputados_frentes, deputados_orgaos, deputados_eventos |
| ❌ Abortado (bulk mapping) | **12** | grupos_detalhe, grupos_membros, grupos_historico, orgaos_detalhe, orgaos_membros, orgaos_eventos, orgaos_votacoes, tramitacoes, autores, relacionadas, temas, proposicoes_votacoes |
| ⏳ Parcial (40%) | **1** | deputados_historico |
| ⬜ Nunca iniciado | **28** | eventos + 5 filhos, bulk-only (funcionarios, tecad_*, licitacoes_*), votacoes + 2 filhos + objetos/proposicoes, votos, profissoes, ocupacoes, orientacoes, proposicoes_detalhe, referencias, blocos_detalhe, mandatos_externos, uf_no_voto, partido_no_voto |

### Bugs Encontrados e Corrigidos

| Bug | Arquivo | Perda | Status |
|---|---|---|---|
| `list.join` em `List(Null)` | detalhe_transformer.py | Impeditivo (todos _detalhe) | ✅ Corrigido |
| `str.slice` em coluna Null | membros/institucional/deputado_child | Impeditivo (frentes_membros etc) | ✅ Corrigido |
| `infer_schema_length` ausente | deputados.py:80,104 | 579 registros perdidos | ✅ Corrigido |
| HTTP 400 como erro | client.py:106 | Degradação (retries desnecessários) | ✅ Corrigido |
| Bulk column mapping | registry.py (idGrupo/idOrgao) | 12 domínios abortados | ❌ Pendente |

### Métricas da Execução

| Métrica | Valor |
|---|---|
| Início | 2026-06-05 06:59 |
| Término | 2026-06-05 14:59 (interrompida) |
| Duração | ~8h |
| Silver salvos | 249 MB, 2.384 lotes |
| 504s | 1.137 (todos resolvidos por retry) |
| Erros fatais | 579 (schema inference — corrigido) |
| Bronze/Gold | 0 (não executado) |

---

## Solução Proposta — Continuação da Fase 3.5 + Fase 4 (Senado)

### Fase 3.5 — Validação Integrada do ETL (Continuação)

### User Stories (atualizado)

13. ✅ As a developer, I want a smoke test que execute uma janela pequena (1 mês)
    contra a API real da Câmara — **CONCLUÍDO** (7 domínios, janela 2025-01-01 a 2025-01-31).

14. As a maintainer, I want a full load completo de todos os 64 domínios contra
    a API e Bulk da Câmara — **PARCIAL** (23/64 completos, 4 bugs corrigidos,
    reexecução necessária com correções aplicadas e bulk mapping resolvido).

15. As a developer, I want um script de continuação que permita reprocessar
    apenas os domínios faltantes após correções, sem recomeçar do zero.

### Plano de Execução — Continuação

**Etapa 2b — Reparo dos domínios abortados (bulk mapping)**

Antes de reexecutar o full load, corrigir o mapeamento de colunas CSV
no `BULK_REGISTRY` para que `orgaos` e `grupos` exportem IDs com
nomenclatura compatível com `DomainSpec.id_column = "id"`.

**Etapa 2c — Reexecução do Full Load (completo)**

- Limpar `data/datalake/` (começar do zero)
- Rodar `python -m ipolitico.main --strategy full_load --all-domains --optimize`
- Rodar `--audit-coverage` e validar que todos os 64 domínios têm dados Silver
- Rodar `--export-gold duckdb` para validar exportação SQL
- Varrer logs em busca de warnings de perda de dados
- Medir e registrar tempo de execução total como baseline

**Critérios de aceite (revisados):**
- [ ] Bulk column mapping corrigido (idOrgao → id, idGrupo → id)
- [ ] `pytest -q` 100% antes da execução
- [ ] Full load executa sem interrupção ou crash
- [ ] Zero erros fatais de schema inference (correção 1.3 aplicada)
- [ ] Zero erros de `list.join` (correção 1.1 aplicada)
- [ ] Zero erros de `str.slice` (correção 1.2 aplicada)
- [ ] `--audit-coverage` mostra 0 domínios como `NUNCA EXTRAÍDO`
- [ ] Dados Gold gerados para todos os domínios
- [ ] `--export-gold duckdb` produz arquivo `.db` legível
- [ ] Tempo de execução registrado como baseline

### Fase 4 — Senado

### User Stories

11. As an architect, I want a `SenadoSourceProvider` following the same
    `SourceProvider` protocol as `CamaraSourceProvider`, so that the
    `FederationOrchestrator` can run Câmara + Senado pipelines in the same
    execution.

12. As a developer, I want the Senado API documented and its Swagger/OpenAPI
    spec fetched, so that implementation planning can begin with a concrete
    understanding of the endpoints available.

### Plano de Execução — Fase 4 (Senado)

**Etapa 1 — Pesquisa e documentação (issue 12)**
- Buscar documentação oficial da API de Dados Abertos do Senado Federal
  (provável URL: `https://legis.senado.leg.br/dadosabertos/`)
- Baixar spec OpenAPI/Swagger se disponível, salvar em
  `docs/senado_swagger.json`
- Analisar endpoints disponíveis e mapear para domínios iPolitico
- Documentar diferenças de schema entre Câmara e Senado

**Etapa 2 — Implementação (issue 13)**
- Criar `core/senado_constants.py` com `SenadoDomainType` e `ApiRoutes`
- Criar `core/senado_schemas.py` com `SILVER_SCHEMAS`
- Criar `core/senado_domain_spec.py` com `DomainSpec`
- Implementar extratores e transformers para primeiros 3–5 domínios Senado
  (senadores, proposições, votações, despesas)
- Criar `sources/senado_provider.py` com `SenadoSourceProvider`
- Adicionar ao `FederationOrchestrator`
- Testes unitários (mock httpx)

### Nota sobre Estimativas

**Fase 3.5:** A execução real mostrou que o full load leva **~8-10h** para
cobrir todos os 64 domínios (vs estimativa original de 2-4h). O gargalo principal
é o endpoint `/deputados/{id}/historico` que sofre cache miss do servidor da
Câmara (504 na primeira tentativa para ~60% dos deputados). O backoff exponencial
responde em segundos e recupera todos os dados, mas adiciona ~15-30 min ao total.

**Fase 4 (Senado):** A estimativa abaixo permanece válida, mas a Fase 3.5 deve
ser concluída primeiro — incluindo a correção do bulk column mapping (Passo 1
do addendum).

### Estimativa

| Etapa | Esforço estimado |
|---|---|
| Pesquisa e documentação (issue 12) | 2–4 h (requer pesquisa humana) |
| Implementação primeiros 3–5 domínios (issue 13) | 3–5 dias |
| **Total** | **3–6 dias** |

---

### Documentos Relacionados

- **Addendum Fase 3.5:** `.scratch/roadmap-etl-expansion/FASE-35-ADDENDUM.md`
  Contém bugs encontrados, análise de 504s, ADRs, métricas da execução
  e plano de continuação detalhado com comandos executáveis.

---

## Histórico — Fases 0–3 (concluídas)

### Fase 0 — Remoção das Subclasses Bulk Rasas (✅ concluído)

Subclasses rasas de `BaseBulkExtractor` foram removidas. O `BaseBulkExtractor`
unificado cobre todos os datasets Bulk via configuração declarativa no
`BULK_REGISTRY`.

### Fase 1 — Bulk CSV Schema Overrides + StateStore (✅ concluído)

**O que foi implementado:**
- Campo `schema_overrides` no `BULK_REGISTRY` para tipagem na leitura via
  `pl.read_csv(schema_overrides=...)`, eliminando o segundo passe de cast.
- Helper de locale BR (`convert_br_currency_columns`) para tratar moeda
  `1.234,56` → `Float64` nos transformers de despesas.
- Interface `StateStore` em `storage/state_store.py` com `get_watermark()` e
  `get_existing_ids()`.
- `DataLakeRepository` implementa `StateStore` — única classe responsável por
  consultar estado persistido.
- `BaseSink` perdeu `get_watermark()` e `get_existing_ids()` — ficou apenas
  com `save()` e `flush()`.
- `SQLiteSink` removido (arquivo, enum `SinkType.SQLITE`, branch condicional
  no `PipelineBuilder`).
- `DataLakeSink` sem métodos de estado — `get_existing_ids`, `get_watermark` e
  `delete_period` foram removidos.

**Arquivos criados/modificados (referência):**
- `storage/state_store.py` — criado
- `storage/datalake_repository.py` — modificado (implementa StateStore)
- `sinks/base.py` — simplificado
- `sinks/datalake_sink.py` — limpo (removeu get_watermark, get_existing_ids, delete_period)
- `pipeline/window_resolver.py` — recebe StateStore
- `pipeline/planners/camara_jobs.py` e `strategies.py` — recebem StateStore
- `pipeline/manager.py` — injeta `self._lake` como StateStore
- `pipeline/builder.py` — simplificado (sem branch SQLite)
- `sinks/sqlite_sink.py` — removido
- `tests/sinks/test_sqlite_sink.py` — removido

### Fase 2 — Swagger-to-Code + Bulk Expansion (✅ concluído)

**Rotas API implementadas:**

| Domínio | Endpoint | Extractor | Transformer |
|---|---|---|---|
| `blocos_detalhe` | `/blocos/{id}` | `detail_child.BlocosDetalheExtractor` | `detalhe_transformer.CamaraDetalheTransformer` |
| `proposicoes_detalhe` | `/proposicoes/{id}` | `detail_child.ProposicoesDetalheExtractor` | `detalhe_transformer.CamaraDetalheTransformer` |
| `eventos_orgaos` | `/eventos/{id}/orgaos` | `evento_child.EventoOrgaosExtractor` | `evento_child_transformer.CamaraEventoChildTransformer` |
| `mandatos_externos` | `/deputados/{id}/mandatosExternos` | `deputado_child.MandatosExternosExtractor` | `deputado_child_transformer.CamaraDeputadoChildTransformer` |

**Swagger-to-code generator:**
- `tools/swagger_codegen.py` — lê `docs/camara_swagger.json`, identifica rotas
  não mapeadas e gera blocos de código prontos para revisão.
- Testes unitários em `tests/tools/test_swagger_codegen.py`.

**Expansão Bulk — domínios institucionais adicionados ao `BULK_REGISTRY`:**
`eventos`, `frentes`, `grupos`, `grupos_membros`, `grupos_historico`,
`legislaturas`, `legislaturas_mesa`, `orgaos`, `deputados_orgaos`,
`deputados_frentes`, `ocupacoes`, `profissoes`, `orientacoes`.

**YAML config:** Todos os 19 domínios com dump Bulk disponível têm
`extractor_bulk` no `camara_pipeline.yaml`.

### Fase 3 — Bulk-only Domains (✅ concluído)

**12 novos domínios** sem rota API REST, apenas dump CSV, todos com
`bulk_only=True` no `BULK_REGISTRY`:

| Dataset | Granularidade | Transformer |
|---|---|---|
| `funcionarios` | Snapshot | `CamaraFuncionariosTransformer` |
| `tecad_categorias` | Snapshot | `CamaraTecadCategoriasTransformer` |
| `tecad_termos` | Snapshot | `CamaraTecadTermosTransformer` |
| `licitacoes` | Anual | `CamaraLicitacoesTransformer` |
| `licitacoes_contratos` | Anual | `CamaraLicitacoesContratosTransformer` |
| `licitacoes_itens` | Anual | `CamaraLicitacoesItensTransformer` |
| `licitacoes_pedidos` | Anual | `CamaraLicitacoesPedidosTransformer` |
| `licitacoes_propostas` | Anual | `CamaraLicitacoesPropostasTransformer` |
| `eventos_presenca_deputados` | Anual | `CamaraEventosPresencaDeputadosTransformer` |
| `eventos_requerimentos` | Anual | `CamaraEventosRequerimentosTransformer` |
| `votacoes_objetos` | Anual | `CamaraVotacoesObjetosTransformer` |
| `votacoes_proposicoes` | Anual | `CamaraVotacoesProposicoesTransformer` |

**Funcionalidades extras nesta fase:**
- CLI `--export-gold sqlite|duckdb` — exporta Gold consolidada para SQL.
- CLI `--list-domains` — árvore hierárquica de domínios com labels descritivos.
- CLI `--audit-coverage` — auditoria de dados Silver vs Gold.
- `GoldExporter` em `storage/gold_exporter.py`.

---

## Testing Decisions

### O que torna um bom teste

- Testa comportamento externo, não implementação interna
- Para extratores: mocka `httpx`/`respx`. Para bulk: mocka download para
  arquivo CSV local conhecido.
- Para `StateStore`: usa Data Lake temporário (tempdir com Parquet).
- Para transformers: DataFrame conhecido de entrada → DataFrame esperado de
  saída. Teste puro, sem I/O.

### Seams de teste

Para as rotas Bulk, o seam mais alto é o `PipelineRunner` com mock de
`BaseBulkExtractor` que retorna DataFrame conhecido de um CSV fixture local.

Para rotas API, o seam mais alto são os extratores individuais com `respx`
mockando a resposta JSON da Câmara.

### Testes de integração (Fase 3.5)

A validação integrada usa **testes de execução real** contra a API da Câmara
(com rede), em contraste com os testes unitários que mockam tudo:

- **Smoke E2E** — janela de 1 mês para 7 domínios representativos, validando
  o encadeamento extrator → transformer → sink → state store → gold.
- **Full load** — todos os 64 domínios do zero, validando cobertura completa,
  integridade referencial e performance.
- **Reexecução incremental** — segunda execução sem `--start-date` valida que
  watermarks persistem e não há duplicação.
- Os resultados de cada etapa são registrados e armazenados como baseline no
  diretório `.scratch/roadmap-etl-expansion/validation/`.

---

## Out of Scope

- **Integração com outras fontes além de Câmara e Senado** (TSE, STF, etc.)
  ficam para uma fase futura não especificada.
- **UI/visualização** — este roadmap é 100% backend/ETL.
- **Deploy em nuvem** — performance local primeiro, sem dependência de cluster.
- **Autenticação ou rate limiting de terceiros** — APIs do legislativo são
  abertas sem autenticação.
- **Migração de dados existentes** — dados já ingeridos permanecem intactos.
  Novos domínios começam do zero.

---

## Further Notes

- A Fase 4 (Senado) depende de documentação externa a ser obtida — pode sofrer
  atraso se a API do Senado não estiver disponível ou documentada.
- A separação `StateStore` desacopla a leitura de estado da escrita de dados.
  Isso é pré-requisito para que novos providers (Senado) tenham seu próprio
  `StateStore` sem carregar um `BaseSink` completo.
- O formato CSV foi escolhido para Bulk porque Polars o lê nativamente com
  engine paralelizado, é mais compacto que JSON/XML, e não exige dependências
  extras.
- A nomenclatura de todos os domínios segue snake_case uniforme no `DomainType`,
  consistente com o padrão estabelecido.
