# iPolitico ETL — Linguagem Ubíqua

> Este documento define o vocabulário compartilhado do projeto iPolitico ETL. Todo
> código, configuração e discussão devem usar estes termos com o significado exato
> descrito aqui. Mantenha este arquivo atualizado conforme a arquitetura evolui.

---

## 1. Entidades e Domínios

### 1.1 Domínio (DomainType)

Cada *domínio* representa uma categoria de dados extraída da Câmara dos Deputados.
São os blocos de construção do ETL. A enumeração `DomainType` em
`core/constants.py` declara todos os domínios suportados.

**Domínios raiz** (extraídos diretamente da API, sem dependência de outro domínio):

| Domínio          | Descrição                                                    | Watermark           |
|------------------|--------------------------------------------------------------|---------------------|
| `deputados`      | Cadastro de deputados federais (nome, partido, UF, foto)     | — (dimensional)     |
| `proposicoes`    | Proposições legislativas (PLs, PECs, MPVs, etc.)            | `dataApresentacao`  |
| `votacoes`       | Votações nominais ocorridas no plenário e comissões          | `data`              |
| `votos`          | Registros individuais de voto de cada deputado em cada votação | — (fato)          |
| `orgaos`         | Órgãos da Câmara (comissões permanentes, temporárias, etc.) | — (dimensional)     |
| `partidos`       | Partidos políticos registrados                               | — (dimensional)     |
| `eventos`        | Eventos da agenda da Câmara (sessões, audiências, reuniões) | `dataHoraInicio`    |
| `blocos`         | Blocos parlamentares                                         | — (dimensional)     |
| `frentes`        | Frentes parlamentares                                        | — (dimensional)     |
| `grupos`         | Grupos parlamentares (Bancadas)                              | — (dimensional)     |
| `legislaturas`   | Legislaturas (ciclos de 4 anos)                              | — (dimensional)     |
| `referencias`    | Catálogos de referência (tipos de proposição, situação, etc.) | — (dimensional)   |
| `funcionarios`   | Servidores da Câmara (nome, cargo, lotação, snapshot)        | — (snapshot)        |
| `tecadCategorias`| Categorias do Tesauro TECAD (classificação temática)         | — (snapshot)        |
| `tecadTermos`    | Termos do Tesauro TECAD (vocabulário controlado)             | — (snapshot)        |

**Domínios de detalhe** (adicional de um domínio raiz, acessado via `/{id}`):

| Domínio              | Pai         | Descrição                           |
|----------------------|-------------|-------------------------------------|
| `deputados_detalhe`  | deputados   | CPF, nascimento, escolaridade       |
| `orgaos_detalhe`     | orgaos      | Sala, site, datas do órgão          |
| `eventos_detalhe`    | eventos     | Fases, pauta, deputados presentes   |
| `votacoes_detalhe`   | votacoes    | Proposições afetadas, efeitos       |
| `frentes_detalhe`    | frentes     | Email, telefone, coordenador        |
| `partidos_detalhe`   | partidos    | Nº eleitoral, logo, status          |
| `grupos_detalhe`     | grupos      | Ativo, último status                |
| `legislaturas_detalhe` | legislaturas | (mesmo schema que o raiz)         |

**Domínios aninhados** (filhos de um domínio raiz, acessados via `/{id}/{rota}`):

| Domínio                 | Pai          | Descrição                               |
|-------------------------|--------------|-----------------------------------------|
| `despesas`              | deputados    | Cota Parlamentar (CEAP) por deputado    |
| `profissoes`            | deputados    | Profissões declaradas (estático)        |
| `ocupacoes`             | deputados    | Ocupações declaradas (estático)         |
| `discursos`             | deputados    | Discursos no plenário (temporal)        |
| `tramitacoes`           | proposicoes  | Histórico de tramitação                 |
| `autores`               | proposicoes  | Autores da proposição                   |
| `relacionadas`          | proposicoes  | Proposições relacionadas                |
| `temas`                 | proposicoes  | Temas associados                        |
| `proposicoes_votacoes`  | proposicoes  | Votações de uma proposição              |
| `orientacoes`           | votacoes     | Orientação de voto dos partidos/blocos  |
| `orgaos_membros`        | orgaos       | Membros de um órgão                     |
| `orgaos_eventos`        | orgaos       | Eventos de um órgão                     |
| `orgaos_votacoes`       | orgaos       | Votações de um órgão                    |
| `eventos_deputados`     | eventos      | Deputados presentes em um evento        |
| `eventos_votacoes`      | eventos      | Votações ocorridas em um evento         |
| `eventos_pauta`         | eventos      | Pauta de um evento                      |
| `partidos_membros`      | partidos     | Membros de um partido                   |
| `partidos_lideres`      | partidos     | Líderes de um partido                   |
| `deputados_frentes`     | deputados    | Frentes de um deputado (estático)       |
| `deputados_orgaos`      | deputados    | Órgãos de um deputado (temporal)        |
| `deputados_eventos`     | deputados    | Eventos de um deputado (temporal)       |
| `deputados_historico`   | deputados    | Histórico de mandato (estático)         |
| `blocos_partidos`       | blocos       | Partidos que compõem um bloco           |
| `frentes_membros`       | frentes      | Membros de uma frente                   |
| `grupos_membros`        | grupos       | Membros de um grupo                     |
| `grupos_historico`      | grupos       | Histórico de um grupo                   |
| `legislaturas_lideres`  | legislaturas | Líderes de uma legislatura              |
| `legislaturas_mesa`     | legislaturas | Mesa diretora de uma legislatura        |

### 1.2 DomainSpec

Metadados declarativos por domínio, definidos em `core/domain_spec.py`:

- **watermark_column**: coluna usada como marca d'água para retomada incremental
  (ex: `"dataDocumento"` para despesas). `None` para domínios dimensionais.
- **earliest_iso**: data mais antiga da qual existem dados confiáveis. Evita loops
  infinitos (ex: deputados desde `"1826-04-29"`).
- **depends_on**: dependências de outros domínios (ex: `votos` depende de `votacoes`).
- **bulk_granularity**: granularidade do dump estático (`"year"` ou `"snapshot"`).

### 1.3 DomainSpec

No código: `DomainSpec` é um `dataclass(frozen=True)` que transporta esses metadados.

---

## 2. Arquitetura do Pipeline de Dados

### 2.1 Visão Geral (Fluxo de Dados)

```
CLI (main.py)
    │
    ▼
FederationOrchestrator ──► CamaraSourceProvider
    │                           │
    │                           ▼
    │                    PipelineManager (por domínio)
    │                     │          │
    │                     │          ├── WindowResolver (StateStore→janela)
    │                     │          ├── SourceRouter (API vs Bulk)
    │               state_store      ├── PipelineBuilder (YAML → classes)
    │               (BaseSink)       ├── CamaraJobPlanner (StateStore)
    │               save/flush       └── PipelineRunner (execução)
    │                     │                   │
    │                     │         ┌─────────┼─────────┐
    │                     ▼         ▼         ▼         ▼
    │               DataLake    Extractor  Transformer  Sink
    │               Repository  (I/O bruto) (regras) (persistência)
    │               (StateStore)   │                     │
    │               watermarks     ▼                     ▼
    │               + IDs     API / Bulk         DataLake (Parquet)
    │                                           bronze/  silver/  gold/
    │
    └── Opcional: DataLakeOptimizer (DuckDB) — bronze/silver → gold
```

### 2.2 Camada de Extração (I/O "Burra")

Cada extrator implementa a interface `BaseExtractor.extract(**kwargs) → pl.DataFrame`.

- **API extractors** (`extractors/camara/api/`): herdam de `CamaraBaseExtractor`,
  lidam com paginação infinita via `fetch_paginated()`.
- **Bulk extractors** (`extractors/camara/bulk/`): herdam de `BaseBulkExtractor`,
  baixam dumps ZIP/CSV, descompactam e retornam DataFrame bruto.
- **Princípio**: NENHUMA regra de negócio no extrator. Apenas I/O.

### 2.3 Camada de Transformação (Regras de Negócio)

Cada transformer implementa `BaseTransformer.transform(df, **kwargs) → pl.DataFrame`.

- Entrada: dados brutos da API/Bulk.
- Saída: DataFrame tipado conforme `SILVER_SCHEMAS` em `core/schemas.py`.
- Responsabilidades: padronização de nomes de colunas, tipagem (Polars),
  conversão de moeda brasileira, filtros temporais (Bulk), eliminação de registros
  inválidos (ex: `codDocumento` nulo ou `valorLiquido = 0` em despesas).
- **Princípio**: Transformers são **puros** — sem I/O, sem estado, sem dependência
  de rede ou sistema de arquivos.

### 2.4 Camada de Destino (Sink)

Cada sink implementa `BaseSink.save(df, table_name, layer, unique_keys)`.

- **DataLakeSink**: salva em Parquet, append-only, com micro-batching por job
  (UUID + timestamp no nome do arquivo). Adiciona coluna de auditoria `captured_at`.

O estado persistido (watermarks e IDs existentes) é consultado via `StateStore`,
implementado pelo `DataLakeRepository`. Veja `storage/state_store.py`.

### 2.5 Camada de Orquestração

| Componente | Responsabilidade |
|---|---|
| `main.py` | CLI, parsing de args, montagem das peças |
| `FederationOrchestrator` | Orquestra múltiplos providers em paralelo (Câmara + Senado futuro) |
| `CamaraSourceProvider` | Adapter que executa pipeline Câmara |
| `PipelineManager` | Gerencia ciclo de vida por domínio (janela, fonte, jobs, execução) |
| `WindowResolver` | Resolve `start_date`/`end_date` a partir de watermark ou full load |
| `EffectiveWindow` | Aplica piso dominial e teto = hoje |
| `SourceRouter` | Decide API vs Bulk (full load multi-ano → Bulk) |
| `PipelineBuilder` | Config-driven: lê YAML e instancia classes via reflection |
| `CamaraJobPlanner` | Gera lista de jobs e mappers de kwargs |
| `PipelineRunner` | Motor assíncrono Producer-Consumer com backpressure |
| `DataLakeOptimizer` | Compacta Silver → Gold via DuckDB (ROW_NUMBER + PARTITION BY) |
| `GoldExporter` | Exporta Gold consolidada para SQLite ou DuckDB via `--export-gold` |
| `CamaraMetadataService` | Consultas à API para metadados (legislatura atual, datas) |
| `DataLakeRepository` | Leituras out-of-core no lake (Polars Lazy / DuckDB) |

---

## 3. Estratégias de Carga

### 3.1 Full Load

- Ignora watermarks, começa da `earliest_iso` do domínio.
- Para domínios com dump anual (despesas, proposicoes, votacoes) e janela
  > 1 ano civil: rota **Bulk** (ZIP/CSV).
- Para os demais: rota **API** (paginada, mês a mês).

### 3.2 Incremental

- Consulta watermark no DataLake (MAX da coluna de data).
- Retoma da última data processada + 1 dia.
- Sempre rota **API** (Bulk só em full load multi-ano).

### 3.3 Fonte: API vs Bulk

O `SourceRouter` decide:

| Condição | Rota |
|---|---|
| Incremental, janlea  ≤ 1 ano | API |
| Incremental, janela  > 1 ano | **Bulk** |
| Full load, domínio sem dump | API |
| Full load, dump anual, janela ≤ 1 ano | API |
| Full load, dump anual, janela > 1 ano | **Bulk** |

Nota: **Bulk** só para os domínios que o tem disponível, para os outros o consumo é via API.

**Bulk-only**: domínios como `funcionarios`, `tecadCategorias` e `tecadTermos` não
possuem rota na API REST. O `SourceRouter` sempre retorna BULK para estes
(`bulk_only=True` no `BULK_REGISTRY`), independentemente da estratégia.
---

## 4. Arquitetura Medallion (Bronze → Silver → Gold)

### 4.1 Bronze (não materializado)

Dados crus como retornados pela API/Bulk. Existe apenas como DataFrame
transitório dentro do `PipelineRunner` — nunca é persistido em disco.

### 4.2 Silver (micro-batches Parquet)

- Escrito pelo `PipelineRunner` → `DataLakeSink`.
- Append-only: cada chamada de API gera um arquivo Parquet em
  `data/datalake/silver/{dominio}/lote_{timestamp}_{uuid}.parquet`.
- Schema tipado conforme `SILVER_SCHEMAS`.
- Coluna extra `captured_at` com timestamp de ingestão.

### 4.3 Gold (consolidado)

- Gerado pelo `DataLakeOptimizer` usando DuckDB.
- Lê todos os `*.parquet` da Silver, aplica `ROW_NUMBER() OVER (PARTITION BY {pk}
  ORDER BY captured_at DESC)` e escreve um único `{dominio}.parquet` em
  `data/datalake/gold/{dominio}/`.
- Compressão ZSTD.
- Ativado via flag `--optimize`.

---

## 5. Fluxo de Jobs, Backpressure e Resiliência

### 5.1 Producer-Consumer com Backpressure

O `PipelineRunner` implementa o padrão Producer-Consumer:

1. **Producer** (`workers`): N workers assíncronos retiram jobs de uma fila,
   chamam `extractor.extract()`, `transformer.transform()`, e colocam DataFrames
   em `df_queue`.
2. **Consumer** (1 task): retira DataFrames da `df_queue` e chama `sink.save()`.
3. **Backpressure**: `df_queue` tem `maxsize=10`. Se o sink for lento, a fila lota
   e os workers suspendem automaticamente as chamadas à API.

### 5.2 Resiliência do Cliente HTTP

`CamaraClient` implementa:

- **Exponential Backoff**: `2^attempt` segundos (2s, 4s, 8s...) em erros 429, 500,
  502, 503, 504 e erros de rede.
- **Retry**: até 10 tentativas (`max_retries`).
- **Semaphore**: limita concorrência a `CAMARA_HTTP_CONCURRENCY` (padrão: 5).
- **Falsos 404**: tratados como lista vazia (a API da Câmara retorna 404 para
  recursos sem dados, não para erros reais).
- **Resume de download**: suporte a `Range` header para retomar downloads
  interrompidos de arquivos bulk.

### 5.3 Retry de Extração (Tenacity)

O `worker` do `PipelineRunner` é decorado com `@tenacity.retry`:
- `wait_exponential(multiplier=1, min=2, max=16)`
- `stop_after_attempt(5)` — proteção extra além do retry do cliente.

---

## 6. Dependências e Ordem de Execução

A ordem canônica é definida em `FULL_CAMARA_PIPELINE` em `pipeline/domain_order.py`.
Dependências obrigatórias (`DOMAIN_UPSTREAM_REQUIREMENTS`) são injetadas
automaticamente via `expand_camara_domains_with_dependencies()`.

**Ordem recomendada** (usuário pode passar subconjuntos):

1. Domínios institucionais: `deputados`, `legislaturas`, `blocos`, `frentes`,
   `grupos`, `orgaos`, `partidos`
2. Despesas (dependente de deputados): `despesas`
3. Proposições e filhos: `proposicoes`, `tramitacoes`, `autores`, `relacionadas`,
   `temas`, `proposicoes_votacoes`
4. Discursos e filhos de deputado (dependente de deputados): `discursos`,
   `deputados_frentes`, `deputados_orgaos`, `deputados_eventos`,
   `deputados_historico`, `profissoes`, `ocupacoes`
5. Votações e votos: `votacoes`, `votos`, `orientacoes`
6. Eventos e filhos: `eventos`, `eventos_deputados`, `eventos_votacoes`,
   `eventos_pauta`
7. Catálogos: `referencias`

---

## 7. Bibliotecas Python e Padrões de Projeto

### 7.1 Dependências Principais

| Biblioteca | Função |
|---|---|
| **Polars** | Processamento de dados colunar (Rust-backed). Leitura de CSV, Parquet; transformações; lazy evaluation. |
| **HTTPX** | Cliente HTTP assíncrono para consumir a API da Câmara. |
| **DuckDB** | Motor OLAP para compactação out-of-core (Silver → Gold). Executa `ROW_NUMBER OVER PARTITION BY` em datasets grandes sem carregar tudo em RAM. |
| **Tenacity** | Decorator de retry com exponential backoff para os workers de extração. |
| **PyYAML** | Leitura do arquivo de configuração `camara_pipeline.yaml`. |
| **python-dotenv** | Carregamento de variáveis de ambiente (.env). |
| **Pydantic** | (Instalado como dependência, mas não usado ativamente. Reservado para validação futura.) |
| **Ruff** | Linter e formatador (configurado em pyproject.toml). |
| **Pytest** | Framework de testes (modo asyncio automático). |

### 7.2 Padrões de Projeto Identificados

| Padrão | Onde | Descrição |
|---|---|---|
| **Strategy** | `sinks/base.py` | `BaseSink` é a interface; `DataLakeSink` é a implementação concreta. Trocável sem alterar o orquestrador. |
| **Template Method** | `extractors/base.py` e `transformers/base.py` | Classes base definem o contrato; classes filhas implementam a lógica específica. |
| **Builder** | `pipeline/builder.py` | `PipelineBuilder` constrói objetos complexos (Extractor + Transformer + Sink) a partir de configuração YAML. |
| **Factory Method** (Reflection) | `PipelineBuilder._import_class()` | Carrega classes dinamicamente a partir de strings (caminho completo) no YAML. Substitui fábricas engessadas. |
| **Producer-Consumer** | `pipeline/runner.py` | Workers produzem DataFrames; Consumer salva. Fila com backpressure (`maxsize=10`) evita OOM. |
| **Blackboard** | `pipeline/manager.py` + `planners/camara_jobs.py` | `PipelineManager` configura o contexto; `CamaraJobPlanner` gera jobs específicos do domínio. |
| **Config-Driven** | Todo o pipeline | YAML mapeia classes de extractor/transformer/sink. Sem hardcode de imports. |
| **Repository** | `storage/datalake_repository.py` | Abstrai consultas ao Data Lake (Polars Lazy + DuckDB). Centraliza lógica de leitura. |
| **Adapter** | `sources/camara_provider.py` | `CamaraSourceProvider` adapta o `PipelineManager` ao protocolo `SourceProvider`, permitindo futura adição de Senado. |
| **Singleton** (lightweight) | `core/config.py` | Configurações globais via constantes de módulo. |
| **Data Class** (Value Object) | `core/domain_spec.py`, `pipeline/builder.py` | `DomainSpec` e `PipelineComponents` são dataclasses congeladas (frozen=True), garantindo imutabilidade. |
| **Watermark Pattern** | `pipeline/window_resolver.py` | Persiste o último timestamp processado para retomada incremental. |
| **Medallion Architecture** | Bronze → Silver → Gold | Camadas de maturidade: bruto (transitório), tipado (append-only), consolidado (deduplicado). |

---

## 7.3 Testes

A suíte de testes usa **Pytest** com `pytest-asyncio` (modo `asyncio_mode = auto`).
Todos os testes de extratores usam `respx` para mockar respostas HTTP sem rede.

**Estrutura** (`tests/`):
- `tests/core/` — Testes de constantes, schemas, client
- `tests/extractors/camara/api/` — Testes de extratores (deputados, despesas,
  proposicoes, orgaos, partidos, eventos, blocos, frentes, grupos, legislaturas)
- `tests/extractors/camara/bulk/` — Testes de extratores bulk (CSV/ZIP)
- `tests/transformers/` — Testes de transformers (DataFrame conhecido, sem I/O)
- `tests/pipeline/` — Testes de orquestração (manager, runner, router, builder)
- `tests/sinks/` — Testes de sinks
- `tests/storage/` — Testes de state store e datalake repository
- `tests/tools/` — Testes de ferramentas (estimador)

**Novos testes nesta iteração (US6):**
- `tests/extractors/camara/api/test_orgaos_partidos_eventos.py` — testes com
  `@respx.mock` para blocos, frentes, grupos, legislaturas (cada um com
  mock da API + assertion de `.height == 1`)
- `tests/transformers/test_institutional_transformer.py` — testes para
  blocos (coluna `federacao` Boolean), frentes (colunas mínimas), grupos
  (`ultimoStatus` Struct → `json_encode`), legislaturas (`dataInicio`/`dataFim`
  truncadas para 10 chars)

## 8. Configuração e CLI

### 8.1 YAML de Pipeline (`configs/camara_pipeline.yaml`)

Mapeia cada domínio para suas classes. Domínios que participam de FULL_LOAD via Bulk
precisam de `extractor_bulk` (tanto os com dump anual quanto os snapshot):

```yaml
domain_configs:
  deputados:
    extractor: "ipolitico.extractors.camara.api.deputados.DeputadosExtractor"
    extractor_bulk: "ipolitico.extractors.camara.bulk.deputados_bulk.DeputadosBulkExtractor"
    transformer: "ipolitico.transformers.camara.deputados_transformer.CamaraDeputadosTransformer"
    sinks:
      datalake: "ipolitico.sinks.datalake_sink.DataLakeSink"
  orgaos:
    extractor: "ipolitico.extractors.camara.api.orgaos.OrgaosExtractor"
    extractor_bulk: "ipolitico.extractors.camara.bulk.base_bulk.BaseBulkExtractor"
    transformer: "ipolitico.transformers.camara.orgaos_transformer.CamaraOrgaosTransformer"
    sinks:
      datalake: "ipolitico.sinks.datalake_sink.DataLakeSink"
```

### 8.2 CLI (`python -m ipolitico.main`)

```bash
# Ingestão incremental (padrão)
python -m ipolitico.main \
  --strategy full_load \
  --domains deputados despesas proposicoes \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --optimize

# Listar árvore hierárquica de domínios
python -m ipolitico.main --list-domains

# Auditar cobertura Silver vs Gold
python -m ipolitico.main --audit-coverage

# Exportar Gold para SQLite
python -m ipolitico.main --export-gold sqlite

# Exportar Gold para DuckDB
python -m ipolitico.main --export-gold duckdb
```

### 8.3 DOMAIN_LABELS

O dicionário `DOMAIN_LABELS` em `core/constants.py` mapeia cada `DomainType` para
um label descritivo em português, usado pelo `--list-domains` e `--audit-coverage`.
Organizado em categorias (Entidades Principais, Referências, Carga Massiva).

### 8.4 `--list-domains` (US1)

Exibe a árvore hierárquica de todos os domínios com labels descritivos, seções
agrupadas (Entidades Principais, Referências, Carga Massiva) e indentação com
`├──`/`└──` para domínios filhos. Usa `DOMAIN_SPECS.depends_on` para determinar
parentesco e `FULL_CAMARA_PIPELINE` para ordenação canônica.

### 8.5 `--audit-coverage` (US4)

Varre `data/datalake/silver/` e `data/datalake/gold/`, conta registros por
domínio via DuckDB `read_parquet()`. Status possíveis: `OK`, `SILVER APENAS`,
`NUNCA EXTRAÍDO`, `DADOS VAZIOS`, `ERRO LEITURA`. Domínios bulk-only marcados
com `(B)`.

### 8.6 `--export-gold` (US2)

Exporta a camada Gold consolidada para banco SQL (SQLite ou DuckDB) após a
ingestão. Útil para análises ad-hoc com SQL e integração com BI tools.

---

## 9. Documentação da API Câmara (`/docs`)

O diretório `docs/` contém a especificação **Swagger (OpenAPI)** da API de Dados
Abertos da Câmara dos Deputados:

- **`docs/camara_swagger.json`** (~400 KB) — Schema completo da API v2, baixado
  diretamente do portal oficial (`dadosabertos.camara.leg.br`).

### 9.1 Como usar o Swagger local

1.  Abra `https://editor.swagger.io/` ou sua ferramenta OpenAPI favorita.
2.  Importe o arquivo `docs/camara_swagger.json`.
3.  Consulte a estrutura exata de cada endpoint: parâmetros esperados, tipos de
    retorno, schemas de objetos aninhados.

### 9.2 Utilidade no desenvolvimento de extratores

O Swagger é a **fonte da verdade** sobre os contratos da API. Sempre que um
extrator novo for criado ou um existente quebrar por mudança no payload:

1. Consulte o Swagger para verificar o schema esperado.
2. Compare com a saída real da API (via `CamaraClient.fetch()`).
3. Ajuste o transformer para refletir o schema correto em `SILVER_SCHEMAS`.

### 9.3 Por que ter uma cópia local

- **Disponibilidade offline**: a API da Câmara pode ficar instável; o Swagger
  local garante que o desenvolvimento não pare.
- **Imutabilidade**: ao fixar uma versão do Swagger, sabemos exatamente qual
  contrato estava vigente quando o código foi escrito. Se a Câmara atualizar a
  API, comparamos o novo Swagger com o local para identificar mudanças.

---

## 10. Exemplos e Scripts de Análise (`/examples`)

A pasta `examples/` serve como **guia de uso para a comunidade** e como
**ferramenta de validação de saídas** do ETL. Todos os scripts assumem que
o Data Lake já foi populado via `python -m ipolitico.main`.

### 10.1 Scripts de execução (shell)

| Script | Uso |
|---|---|
| `run_all_camara_domains.sh` | Executa todos os domínios em ordem de dependência. Aceita `START_DATE`, `END_DATE`, `STRATEGY` e `OPTIMIZE` como variáveis de ambiente. Útil para carga completa. |
| `smoke_e2e.sh` | Smoke test offline: verifica imports, `--help` da CLI e funcionamento do estimador. Roda em CI (GitHub Actions) sem depender de rede. |

### 10.2 Estimador de ingestão

| Script | Uso |
|---|---|
| `estimate_camara_ingestion.py` | Estima número de requisições HTTP e tempo de parede para uma ingestão. Cenários: `full-hybrid` (Bulk + API, recomendado), `full-api` (pior caso), `custom` (parâmetros manuais). Usa `api_telemetry.db` se existir para calibrar latência. |

### 10.3 Análises sobre o Data Lake (Parquet / DuckDB / Polars)

| Script | O que valida / analisa |
|---|---|
| `dtlake/validacao_gold.py` | Auditoria da camada Gold: tipagem, unicidade de chaves, integridade referencial, suspeitas cívicas (ex: valores zerados). |
| `dtlake/inventario_dados.py` | Gera inventário de todas as tabelas no Data Lake com contagem de registros, cargas e chaves duplicadas. |
| `dtlake/auditoria_integridade.py` | Verifica integridade referencial entre tabelas (ex: despesas → deputados, votos → votações). |
| `dtlake/auditoria_limites_temporais.py` | Valida limites mínimos e máximos de datas por domínio. |
| `dtlake/auditoria_profunda_global.py` | Auditoria abrangente: checa schemas, valores nulos e anomalias em todas as camadas. |
| `dtlake/auditar_legislaturas_salvas.py` | Verifica se todos os deputados de cada legislatura estão presentes. |
| `dtlake/check_duplicates.py` | Varre todas as tabelas em busca de duplicatas (violação de chave). |
| `dtlake/analise_forense_despesas.py` | Análise forense da CEAP: gastos atípicos, padrões suspeitos, maiores valores. |
| `dtlake/top_gastos_combustivel.py` | Ranking dos maiores gastos com combustível (subsídio à fiscalização cívica). |
| `dtlake/analise_profissoes_parquet.py` | Perfil profissional dos deputados a partir do Data Lake. |
| `dtlake/analise_troca_partidaria.py` | Detecta trocas de partido entre legislaturas. |
| `dtlake/ranking_discursos_parquet.py` | Ranking de deputados por quantidade de discursos. |

### 10.4 Análises sobre SQLite

| Script | O que valida / analisa |
|---|---|
| `sqlite/perfil_escolaridade.py` | Perfil de escolaridade dos deputados (via SQLite). |
| `sqlite/analise_profissoes.py` | Profissões mais comuns entre deputados (via SQLite). |
| `sqlite/ranking_discursos.py` | Ranking de discursos por deputado (via SQLite). |

---

## 11. Estrutura de Diretórios

```
ipolitico-etl/
├── configs/
│   └── camara_pipeline.yaml            # Mapeamento de classes por domínio
├── data/                               # Dados gerados em runtime
│   ├── datalake/                       # Data Lake (Parquet)
│   │   ├── bronze/                     # (não usado — camada transitória)
│   │   ├── silver/{dominio}/          # Micro-batches append-only
│   │   └── gold/{dominio}/            # Consolidado deduplicado
│   ├── dbs/
│   │   └── api_telemetry.db            # Telemetria de requisições
│   └── logs/
│       └── ipolitico_etl.log
├── docs/
│   └── camara_swagger.json             # Swagger/OpenAPI da API Câmara (~400 KB)
├── examples/                           # Scripts de execução, estimativa e auditoria
│   ├── estimate_camara_ingestion.py    # Estimador de requisições/tempo
│   ├── run_all_camara_domains.sh       # Script de carga completa
│   ├── smoke_e2e.sh                    # Smoke test offline (CI)
│   ├── dtlake/                         # Análises sobre o Data Lake (Parquet)
│   │   ├── validacao_gold.py, inventario_dados.py
│   │   ├── auditoria_integridade.py, auditoria_limites_temporais.py
│   │   ├── auditoria_profunda_global.py, auditar_legislaturas_salvas.py
│   │   ├── check_duplicates.py, analise_forense_despesas.py
│   │   ├── top_gastos_combustivel.py, analise_profissoes_parquet.py
│   │   ├── analise_troca_partidaria.py, ranking_discursos_parquet.py
│   │   └── ...
│   └── sqlite/                         # Análises sobre SQLite
│       ├── perfil_escolaridade.py
│       ├── analise_profissoes.py
│       └── ranking_discursos.py
├── src/
│   └── ipolitico/
│       ├── core/                       # Constantes, schemas, client, config
│       ├── extractors/                 # Extratores (API + Bulk)
│       │   └── camara/
│       │       ├── api/                # Extractors por endpoint
│       │       └── bulk/               # Dumps ZIP/CSV
│       ├── pipeline/                   # Orquestração
│       │   ├── planners/               # Geração de jobs
│       │   └── *.py                    # Manager, Runner, Router, etc.
│       ├── services/                   # Serviços auxiliares (metadata)
│       ├── sinks/                      # Destinos (DataLake, SQLite)
│       ├── sources/                    # Source providers (Câmara)
│       ├── storage/                    # DataLakeRepository, StateStore
│       ├── tools/                      # Ferramentas (estimador)
│       └── transformers/              # Transformadores
│           └── camara/                 # Transformers por domínio
├── tests/
│   ├── core/
│   ├── extractors/
│   ├── pipeline/
│   ├── sinks/
│   ├── storage/
│   ├── tools/
│   └── transformers/
├── pyproject.toml
├── README.md
└── CONTEXT.md                          # ← Este arquivo
```

---

## 12. Glossário Rápido

| Termo | Definição |
|---|---|
| **Domínio** | Categoria de dados da Câmara (ex: deputados, despesas) |
| **Domínio raiz** | Recurso principal da API (`/deputados`, `/proposicoes`) |
| **Domínio aninhado** | Filho de um domínio raiz (`/deputados/{id}/despesas`) |
| **Domínio de detalhe** | Metadados adicionais (`/deputados/{id}`) |
| **Job** | Unidade mínima de trabalho (ex: um par deputado×ano) |
| **Watermark** | Último timestamp processado para retomada incremental |
| **Bulk** | Dump estático (ZIP/CSV) para carga histórica |
| **Sink** | Destino de persistência (DataLake Parquet ou SQLite) |
| **Extractor** | Componente de I/O que busca dados da origem |
| **Transformer** | Componente puro de regras de negócio |
| **Medallion** | Arquitetura em camadas: Bronze (bruto) → Silver (tipado) → Gold (consolidado) |
| **Backpressure** | Mecanismo que trava workers se o sink não consegue acompanhar |
| **CEAP** | Cota para Exercício da Atividade Parlamentar ("cotão") |
| **Federation** | Orquestração de múltiplas fontes (Câmara + Senado futuro) |
| **Swagger / OpenAPI** | Especificação padronizada dos endpoints da API Câmara |
| **Smoke test** | Teste rápido de validação de imports e CLI (sem rede) |
