---
Status: ready-for-agent
Date: 2026-06-03
Area: arquitetura
---

# Melhorias de Arquitetura — iPolitico ETL

Análise baseada nos princípios de **Módulos Profundos** (Ousterhout),
**Clean Code** (Martin) e **DDIA** (Kleppmann). A revisão completa
está em `/tmp/architecture-review-1780500415.html`.

## Oportunidades Identificadas

### 1. [Forte] Small Files Problem no DataLakeSink

**Problema**: Cada `save()` gera 1 arquivo Parquet. Com 513 deputados ×
12 meses por domínio, a camada Silver acumula milhares de micro-arquivos.
O DuckDB `read_parquet('*.parquet')` degrada com 5k+ arquivos.

**Solução**: Buffer in-memory + flush consolidado (ex: 50 MB ou a cada
N DataFrames). `pl.concat()` no consumer antes de `write_parquet()`.

**Arquivos**:
- `sinks/datalake_sink.py`
- `pipeline/runner.py`

---

### 2. [Forte] `map_elements` no Hot Path dos Transformers ✅ CONCLUÍDO

**Problema**: 6 arquivos com `map_elements(lambda v: json.dumps(v))` —
força iteração Python linha a linha, anulando o paralelismo vetorizado
do Polars.

**Solução**: Substituir por expressões nativas Polars:
- Struct → `struct.json_encode()`
- List(Struct) → `format("[{}]", list.eval(element().struct.json_encode()).list.join(","))`
- Object → removido (nunca ocorre na prática com dados da API)

**Arquivos modificados**:
- `transformers/camara/votacoes_transformer.py` — removeu branch Object, Struct já era nativo
- `transformers/camara/institutional_transformer.py` — `ultimoStatus` com `struct.json_encode()`
- `transformers/camara/detalhe_transformer.py` — Struct + List(Struct) genérico
- `transformers/camara/evento_child_transformer.py` — Struct por nome + genérico
- `transformers/camara/discursos_transformer.py` — `faseEvento` com `struct.json_encode()`
- `transformers/camara/eventos_transformer.py` — `orgaos` List(Struct) com `list.eval()`

**Resultado**: 117/117 testes passando. `import json` removido de todos os arquivos.
Zero `map_elements` nos transformers.

---

### 3. [Forte] `PipelineManager.run_domain()` — Módulo Raso

**Problema**: 180 linhas + `CamaraJobPlanner` com 840 linhas de if-elif
(~30 ramos de domínio). A complexidade está na interface — para entender
um domínio, você precisa ler todos os ramos.

**Solução**: Extrair `unique_keys` e `sub_domain` para o `DomainSpec`.
Criar objetos de estratégia por tipo de domínio (root, child, nested,
detail). O if-elif vira `registry[domain_type].build(...)`.

**Arquivos**:
- `pipeline/manager.py`
- `pipeline/planners/camara_jobs.py`
- `core/domain_spec.py`

---

### 4. [Vale Explorar] Bulk Extractors — Classes Rasas ✅ CONCLUÍDO

**Problema**: 5 subclasses de `BaseBulkExtractor` com 5-10 linhas cada,
só definindo `domain_name`. Módulos rasos — interface ≈ implementação.

**Solução**: `BaseBulkExtractor.__init__` agora aceita `domain_name` como
parâmetro do construtor. As 5 subclasses foram deletadas. `PipelineBuilder`
injeta `domain_name` dinamicamente via `domain.value` do `PipelineManager`.
`CamaraExtractorFactory` instancia `BaseBulkExtractor` diretamente com
`domain_name=key`.

**Arquivos modificados**:
- `extractors/camara/bulk/base_bulk.py` — `__init__` aceita `domain_name`
- `extractors/camara/bulk/factory.py` — usa `BaseBulkExtractor` direto
- `pipeline/builder.py` — `build()` aceita `domain_name` kwarg
- `pipeline/manager.py` — passa `domain.value` na build
- `configs/camara_pipeline.yaml` — todos `extractor_bulk` → `BaseBulkExtractor`

**Arquivos deletados**:
- `extractors/camara/bulk/deputados_bulk.py`
- `extractors/camara/bulk/despesas_bulk.py`
- `extractors/camara/bulk/proposicoes_bulk.py`
- `extractors/camara/bulk/votacoes_bulk.py`

**Resultado**: 124/124 testes passando.

---

### 5. [Vale Explorar] Bulk CSV — Leitura sem Schema + Recast em Cadeia

**Problema**: `pl.read_csv(infer_schema_length=0)` traz tudo como string.
Depois o transformer faz conversão de moeda BR, datas, IDs. Dois passes
de transformação onde um bastaria.

**Solução**: `schema_overrides` no `BULK_REGISTRY`. `BaseBulkExtractor`
passa para `pl.read_csv(schema_overrides=...)`.

**Arquivos**:
- `extractors/camara/bulk/registry.py`
- `extractors/camara/bulk/base_bulk.py`
- `transformers/camara/despesas_transformer.py`
- `transformers/ceap_bulk.py`

---

### 6. [Especulativo] SQLiteSink — Duplo Papel

**Problema**: `BaseSink` acumula `save()` (escrita) + `get_watermark()`,
`get_existing_ids()` (leitura de estado). Viola SRP.

**Solução**: Extrair interface `StateStore`. `BaseSink` fica só com
`save()`. `WindowResolver` e `CamaraJobPlanner` recebem `StateStore`.

**Arquivos**:
- `sinks/base.py`
- `sinks/sqlite_sink.py`
- `sinks/datalake_sink.py`
- `pipeline/window_resolver.py`
- `storage/datalake_repository.py`
