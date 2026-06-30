---
Status: in-progress
Priority: P0
Estimate: 20-25 days (original), ~15 days remaining
Progress: ~57%
Last Update: 2026-06-30
---

# PRD: Integração da API do Senado no iPolitico ETL

## Problem Statement

O iPolitico ETL atualmente consome apenas a API de Dados Abertos da Câmara dos Deputados, cobrindo 64 domínios de dados legislativos federais. Contudo, o processo legislativo federal brasileiro é bicameral: projetos de lei tramitam entre Câmara e Senado, senadores têm dados de mandato, votações, discursos e emendas orçamentárias que a Câmara não oferece. Sem o Senado, o retrato do legislativo federal é incompleto.

Além disso, a API do Senado oferece dados exclusivos de alto valor que a Câmara não disponibiliza (emendas ao orçamento, vetos presidenciais, notas taquigráficas), representando uma lacuna significativa de transparência.

## Status Atual da Implementação (apurado em 2026-06-30)

### Tabela de Progresso Real

| Issue | Domínios | Infra | Extratores | Transformers | Schemas | YAML | Testes | Status |
|---|---|---|---|---|---|---|---|---|
| 01 — Core Infrastructure | — | ✅ | — | — | — | ✅ | ✅ | **100% ✅** |
| 02 — Senadores | 2 | ✅ | ✅ 2/2 | ✅ 2/2 | ✅ 2/2 | ✅ 2/2 | ✅ 4/4 | **100% ✅** |
| 03 — Processos | 5 | ✅ | ❌ 0/5 | ❌ 0/5 | ⚠️ 1/5 | ❌ | ❌ | **~5%** |
| 04 — Votações | 3 | ✅ | ❌ 0/3 | ❌ 0/3 | ⚠️ 2/3 | ❌ | ❌ | **~5%** |
| 05 — Emendas | 2 | ✅ | ❌ 0/2 | ❌ 0/2 | ❌ 0/2 | ❌ | ❌ | **0%** |
| 06 — Vetos | 2 | ✅ | ✅ 2/2 | ✅ 2/2 | ✅ 2/2 | ✅ 2/2 | ❌ | **100% ✅** |
| 07 — Discursos + Taquigrafia | 5 | ✅ | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ❌ | **100% ✅** |
| 08 — Comissões + Plenário + Composição | 11 | ✅ | ✅ 11/11 | ✅ 11/11 | ✅ 11/11 | ✅ 11/11 | ✅ 14 | **100% ✅** |
| **Total** | **30** | **✅** | **20/30** | **20/30** | **20/30** | **20/30** | **14+** | **~67%** |

### O que já está implementado

**Infraestrutura base (Issue 01):**
- `core/senado_client.py` — `SenadoClient` com semáforo de concorrência 5, retry via tenacity (exponential backoff), tratamento de falso 404
- `core/config.py` — env vars `SENADO_API_BASE_URL` e `SENADO_HTTP_CONCURRENCY`
- `extractors/senado/api/senado_base.py` — `SenadoBaseExtractor` com `fetch_flat()`, `flatten_response()`, `_ensure_list()`
- `services/senado_metadata.py` — `SenadoMetadataService` (legislatura calculada por ano)
- `sources/senado_provider.py` — `SenadoSourceProvider` seguindo protocolo `SourceProvider`
- `pipeline/federation.py` — `FederationOrchestrator` genérico
- `pipeline/manager.py` — `PipelineManager` genérico com metadata_service injetado
- `main.py` — CLI `--source {camara, senado, all}`
- 30 `DomainType`s do Senado registrados em `constants.py`, `domain_spec.py`, `domain_order.py`
- `configs/senado_pipeline.yaml` criado

**Domínio Senadores (Issue 02):**
- `SenadoresExtractor` — lista por legislatura + endpoint `/atual`
- `SenadoresDetalheExtractor` — detalhe por `GET /senador/{codigo}`
- `SenadoresTransformer` — normaliza XML-heritage → Silver snake_case
- `SenadoresDetalheTransformer` — normaliza detalhes cadastrais
- Schemas Silver completos para ambos
- Ambos mapeados no `senado_pipeline.yaml`
- Testes para extractors e transformers

**Schemas Silver avulsos (sem extratores/transformers):**
- ~~`processos` (10 campos)~~ — implementado na Issue 03
- ~~`votacoes_senado` (10 campos)~~ — implementado na Issue 04
- ~~`votos_senado` (6 campos)~~ — implementado na Issue 04

**Domínio Vetos (Issue 06):**
- `VetosPresidenciaisExtractor` — veto listing por ano
- `VetosDetalheExtractor` — detalhe por código de veto
- `VetosPresidenciaisTransformer` e `VetosDetalheTransformer`
- Schemas Silver completos
- Ambos mapeados no `senado_pipeline.yaml`

**Domínio Discursos e Notas Taquigráficas (Issue 07):**
- `DiscursosSenadorExtractor` — discursos por parlamentar
- `DiscursosPlenarioExtractor` — discursos em plenário
- `DiscursosTextoExtractor` — texto íntegra do discurso
- `NotasTaquigrafiaSessaoExtractor` — notas por sessão
- `NotasTaquigrafiaReuniaoExtractor` — notas por reunião
- 5 transformers correspondentes
- Schemas Silver completos
- Mapeados no `senado_pipeline.yaml`

**Domínio Composição (Issue 08c):**
- `BlocosSenadoExtractor` — blocos parlamentares
- `LiderancasSenadoExtractor` — lideranças
- `MesaSenadoExtractor` — mesa diretora do Senado
- `MesaCongressoExtractor` — mesa diretora do Congresso
- 4 transformers via `institutional_transformer.py` compartilhado
- Schemas Silver completos
- Mapeados no `senado_pipeline.yaml`
- 14 testes (9 extractor + 5 transformer)

### O que falta implementar

**10 schemas Silver**, **10 extratores** e **transformers** para processos (03) e emendas (05), mais testes para Issues 03–07.

## Arquitetura

### Stack técnica
- **Cliente HTTP**: `SenadoClient` (mesmo padrão do `CamaraClient`, mas sem telemetria SQLite nem warmup)
- **Base URL**: `https://legis.senado.leg.br/dadosabertos` (configurável via env `SENADO_API_BASE_URL`)
- **Formato**: JSON com estrutura aninhada herdada de XML. `SenadoBaseExtractor.flatten_response()` navega envelopes
- **Edge case**: Objeto-único vs array quando 1 item. `_ensure_list()` normaliza
- **Autenticação**: Nenhuma (API pública)
- **Rate limit**: 10 req/s documentado. Semáforo conservador de 5 concorrências
- **Sem paginação**: API retorna arrays completos (diferente da Câmara)
- **Sem Bulk**: Senado não oferece dumps ZIP

### Dependências entre domínios
| Domínio filho | Depende de |
|---|---|
| `senadores_detalhe` | `senadores` |
| `processos_detalhe` | `processos` |
| `processos_emendas`, `processos_documentos` | `processos` |
| `votacoes_senado` | `processos` |
| `votos_senado` | `votacoes_senado` |
| `votacoes_comissao` | `processos` |
| `vetos_detalhe` | `vetos_presidenciais` |
| `senadores_discursos` | `senadores` |
| `discursos_texto` | `discursos_plenario` |
| `comissoes_detalhe`, `comissoes_reunioes`, `comissoes_membros` | `comissoes_senado` |
| `notas_taquigrafia_sessao` | `plenario_sessoes` |
| `notas_taquigrafia_reuniao` | `comissoes_reunioes` |

### Planejador de jobs
Domínios de lista única (senadores, comissões, blocos, lideranças, mesas): **1 job**.
Domínios temporais (processos, votações, discursos): **janela de 1 mês por job**.
Domínios anuais (orçamento, vetos): **1 job por ano**.

## User Stories

1. Como cidadão, quero que o ETL consuma dados de senadores (lista, detalhes, mandatos), para que eu possa auditar a atividade parlamentar no Senado. ✅ **CONCLUÍDO**
2. Como cidadão, quero que o ETL consuma processos legislativos do Senado (proposições, emendas, documentos, relatorias), para que eu possa rastrear o ciclo de vida de projetos de lei no Senado.
3. Como cidadão, quero que o ETL consuma votações nominais do Senado, para que eu possa saber como cada senador votou em cada matéria.
4. Como cidadão, quero que o ETL consuma emendas ao orçamento de autoria de senadores, para que eu possa auditar a destinação de recursos públicos.
5. Como cidadão, quero que o ETL consuma o histórico de vetos presidenciais, para que eu possa entender o processo de sanção e veto de projetos de lei. ✅ **CONCLUÍDO**
6. Como cidadão, quero que o ETL consuma discursos de senadores em plenário e notas taquigráficas, para que eu possa ler na íntegra os debates parlamentares. ✅ **CONCLUÍDO**
7. Como cidadão, quero que o ETL consuma a composição de comissões, blocos, lideranças e mesa diretora do Senado, para que eu entenda a estrutura de poder na casa. ✅ **CONCLUÍDO**
8. Como analista, quero executar o pipeline com `--source senado --full-load` para ingerir apenas dados do Senado. ✅ **CONCLUÍDO**
9. Como analista, quero executar o pipeline com `--source all --full-load` para ingerir Câmara e Senado em paralelo, sem exceder rate limits individuais. ✅ **CONCLUÍDO**
10. Como desenvolvedor, quero que cada domínio do Senado siga o mesmo padrão de `DomainType`, `Extractor`, `Transformer`, `Sink` e `YAML` já estabelecido pela Câmara.

## Implementation Decisions

1. **SenadoClient** separado do `CamaraClient` com semáforo independente (5). Sem telemetria SQLite, sem warmup.
2. **SenadoBaseExtractor** herda de `BaseExtractor`. Sem paginação. Métodos `fetch_flat`, `flatten_response`, `_ensure_list`.
3. **30 domínios registrados** no `DomainType` unificado (não em enum separado). Roteamento por YAML, não por enum.
4. **PipelineManager genérico**: aceita `metadata_service` injetado, sem referência hardcoded à Câmara.
5. **FederationOrchestrator** aceita lista de `SourceProvider` — executa `asyncio.gather` em paralelo.
6. **JobPlanner** genérico: já renomeado de `CamaraJobPlanner`. Domínios temporais do Senado usarão janelas mensais.
7. **Flag `--source`** na CLI: `camara`, `senado`, `all` (padrão).
8. **Conexão cross-casa** (senador que foi deputado) fora de escopo — camada analítica posterior.
9. **Senado não tem Bulk**: apenas API REST. Config YAML sem seção `extractor_bulk`.

## Testing Decisions

### O que constitui um bom teste
- Testar comportamento externo, não implementação interna.
- Para extratores: mockar `respx` com resposta JSON conhecida → verificar DataFrame de saída.
- Para transformers: DataFrame conhecido de entrada → schema Silver esperado. Teste puro, sem I/O.
- Para YAML/CLI: smoke test validando que `--list-domains` e `--source senado` funcionam sem rede.

### Módulos a testar (por issue)
Cada extrator terá seu próprio arquivo de teste em `tests/extractors/senado/test_<dominio>.py`.
Cada transformer terá seu teste em `tests/transformers/test_<dominio>_transformer.py`.
Domínios P0 (processos, votações, emendas, vetos) devem ter testes completos.
Domínios P1/P2 (comissões, plenário, composição) podem ter testes mais superficiais.

### Prior art
- `tests/extractors/senado/test_senadores.py` — mock httpx com respx
- `tests/transformers/test_senado_senadores_transformer.py` — DataFrame conhecido
- `tests/core/test_senado_client.py` — mock httpx, retry, 404

## Out of Scope

- **Conexão cross-casa** (ex: "senador que foi deputado"): camada analítica posterior ao ETL.
- **Portal da Transparência** (Governo Federal): complemento futuro fora deste PRD.
- **Refatoração do CamaraClient**: apenas renomeação já feita (`client.py → camara_client.py`).
- **Telemetria SQLite para Senado**: não implementada.
- **Warmup para Senado**: não implementado (Senado não tem histórico de 504s como a Câmara).
- **Bulk downloads**: Senado não oferece dumps ZIP.
- **Gold federada**: Câmara e Senado têm Gold separadas. Fusão em camada posterior.

## Further Notes

- API do Senado é pública, sem autenticação.
- Rate limit documentado: 10 req/s. Semáforo de 5 é conservador e seguro.
- API em migração do sistema legado MATE para novo sistema. 42 endpoints deprecated ignorados (já filtrados no PRD original).
- Volume total estimado: ~500MB a 1GB (comparável ao volume atual da Câmara de ~2GB).

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Objeto-único vs array imprevisível | Alta | Médio | `_ensure_list()` no base extractor |
| Rate limit 10 req/s para FULL_LOAD | Média | Alto | Janelas mensais. Reduzir semáforo para 3 se necessário |
| Migração contínua de API | Média | Médio | Monitorar headers `Deprecation` em runtime |

### Ordem de implementação recomendada

1. ~~**Issue 03 — Processos** (base para votações, schemas parciais existem)~~ ✅
2. ~~**Issue 04 — Votações** (schemas parciais existem, dependem de processos)~~ ✅
3. **Issue 05 — Emendas** (P0 exclusivo, estrutura simples)
4. ~~**Issue 06 — Vetos** (P0 exclusivo, estrutura simples)~~ ✅
5. ~~**Issue 07 — Discursos** (P0.5, estrutura XML-heritage complexa)~~ ✅
6. ~~**Issue 08 — Comissões + Plenário + Composição** (P1, 11 domínios mas dados rasos)~~ ✅
