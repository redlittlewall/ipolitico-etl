---
Status: ready-for-agent
Date: 2026-06-04
Area: arquitetura
---

# PRD: iPolitico ETL — Roadmap de Expansão (Fases 0–4)

## Problem Statement

O ETL da Câmara dos Deputados do iPolitico já cobre 48 domínios de dados entre
rotas raiz, detalhe e aninhadas. Porém:

1. **Itens arquiteturais pendentes** — o Bulk CSV lê tudo como string (duas
   passagens de transformação), e o `BaseSink` acumula responsabilidades de
   escrita + consulta de estado (violação de SRP), além de carregar o legado
   do `SQLiteSink` que foi descontinuado como destino.

2. **Cobertura incompleta da API Câmara** — 4 rotas Swagger ainda não
   implementadas (blocos_detalhe, proposicoes_detalhe, eventos_orgaos,
   mandatos_externos) e apenas 5 dos 32 datasets bulk disponíveis estão
   registrados.

3. **Ausência de cobertura Bulk para domínios institucionais** — domínios como
   `eventos`, `frentes`, `orgaos` e seus filhos só têm rota API. Full loads
   históricos poderiam usar dumps CSV e seriam muito mais rápidos.

4. **Inexistência de suporte a outras fontes** — a arquitetura foi desenhada
   para suportar múltiplos providers (Câmara, Senado futuro), mas só o
   `CamaraSourceProvider` existe. O próximo passo natural é a API do Senado.

## Solution

Executar um roadmap em 5 fases que fecha pendências arquiteturais, expande a
cobertura da Câmara e prepara o terreno para novos providers:

- **Fase 0**: Commitar o Item 4 (remoção das subclasses Bulk rasas, já feita)
- **Fase 1**: Bulk CSV com schema_overrides + StateStore (separação de
  responsabilidade + remoção SQLiteSink)
- **Fase 2**: Swagger-to-code para rotas Câmara faltantes + expansão de
  cobertura Bulk para domínios institucionais
- **Fase 3**: Domínios Bulk-only (licitações, funcionários, tecad, etc.)
- **Fase 4**: Adapter para API do Senado

## User Stories

1. As a developer, I want the Bulk CSV reader to apply schema_overrides with
   locale BR support, so that the extractor outputs typed DataFrames instead of
   all-string, eliminating one pass of conversion in the transformer.

2. As a developer, I want a `StateStore` interface separated from `BaseSink`,
   so that `WindowResolver` and `CamaraJobPlanner` depend only on the state
   queries they need, not on a full Sink.

3. As a maintainer, I want the `SQLiteSink` removed from the codebase, so that
   there is no dead code or dead conditional branches in the PipelineBuilder.

4. As a developer, I want the `DataLakeRepository` to implement the new
   `StateStore` interface, so that there is a single class for reading state
   from the Data Lake.

5. As a data analyst, I want the `/blocos/{id}`, `/proposicoes/{id}`,
   `/eventos/{id}/orgaos` and `/deputados/{id}/mandatosExternos` endpoints
   implemented, so that all 78 documented Swagger routes of the Câmara are
   covered.

6. As a developer, I want a tool that reads the local Swagger file and
   generates the minimal glue code (DomainType entry, DomainSpec, YAML config
   entry, SILVER_SCHEMA entry) for a new endpoint, so that adding routes is
   fast and mechanical.

7. As a data engineer, I want Bulk dumps registered for all domains that have
   them (`eventos`, `frentes`, `grupos`, `legislaturas`, `orgaos` and their
   children), so that full load historical ingestions use the faster Bulk route
   instead of month-by-month API pagination.

8. As a developer, I want the URL patterns in `BULK_REGISTRY` to use generic
   templates (yearly or snapshot), so that adding new Bulk datasets requires
   only the dataset name and granularity, not a full URL for each entry.

9. As a data citizen, I want the Bulk-only domains (`licitacoes`,
   `funcionarios`, `tecadCategorias`, `tecadTermos`, `eventosPresencaDeputados`,
   `eventosRequerimentos`, `votacoesObjetos`, `votacoesProposicoes`) available
   as new domain types, so that I can analyze spending, staffing, and legislative
   agenda data from the Câmara.

10. As a user, I want the Gold layer to be exportable to SQL (SQLite / DuckDB),
    so that I can choose between Parquet and relational output depending on my
    analysis tools.

11. As an architect, I want a `SenadoSourceProvider` following the same
    `SourceProvider` protocol as `CamaraSourceProvider`, so that the
    `FederationOrchestrator` can run Câmara + Senado pipelines in the same
    execution.

12. As a developer, I want the Senado API documented and its Swagger/OpenAPI
    spec fetched, so that implementation planning can begin with a concrete
    understanding of the endpoints available.

## Implementation Decisions

### Fase 0 — Commit Bulk Subclass Removal (1–2h)

- Já implementado e testado (124/124 testes passando).
- Commitar as alterações no working tree (12 arquivos modificados).

### Fase 1 — Item 5 + Item 6 (3–5 dias)

**Item 5 — Bulk CSV Schema Overrides (Opção B: completos com locale BR)**

O `BULK_REGISTRY` ganha um campo `schema_overrides` por dataset:

```python
BULK_REGISTRY: dict[str, dict] = {
    "despesas": {
        ...
        "schema_overrides": {
            "ano": pl.Int32,
            "mes": pl.Int32,
            "numDeputadoID": pl.Int64,
            "vlrDocumento": pl.Utf8,        # moeda BR, vira Float64 no transformer
            "vlrLiquido": pl.Utf8,           # moeda BR, vira Float64 no transformer
            "numDocumento": pl.Int64,
            "codDocumento": pl.Int64,
            "codLote": pl.Int64,
            "codTipoDocumento": pl.Int64,
            "indTipoDocumento": pl.Utf8,
            "cnpjCpfFornecedor": pl.Utf8,
            "txtFornecedor": pl.Utf8,
            "txtDescricao": pl.Utf8,
            "txtDescricaoEspecificacao": pl.Utf8,
            "datDocumento": pl.Utf8,         # data ISO, transformer normaliza
        },
    },
    ...
}
```

O `BaseBulkExtractor.extract()` passa `schema_overrides` para `pl.read_csv()`:

```python
config = BULK_REGISTRY.get(self.domain_name)
overrides = config.get("schema_overrides", {})
df = pl.read_csv(..., schema_overrides=overrides)
```

A lógica de locale BR (moeda `1.234,56` → string → `str.replace(",", ".")` →
`cast(pl.Float64)`) continua no transformer mas é centralizada via helper.

**Item 6 — StateStore + Remoção SQLiteSink**

Nova interface em `storage/state_store.py`:

```python
class StateStore(ABC):
    """Responsabilidade única: consultar estado (watermark, IDs existentes)."""

    @abstractmethod
    async def get_watermark(self, domain: str) -> str | None: ...

    @abstractmethod
    async def get_existing_ids(
        self, domain: str, id_column: str = "id"
    ) -> set[str]: ...
```

O `DataLakeRepository` (em `storage/datalake_repository.py`) implementa
`StateStore`. O método `from_sink()` do `DataLakeRepository` é mantido.

`BaseSink` perde `get_watermark()` e `get_existing_ids()` — fica apenas com
`save()` e `flush()`.

`WindowResolver` e `CamaraJobPlanner` passam a receber `StateStore` em vez de
`BaseSink` no construtor.

`PipelineManager` injeta `self._lake` (que é `DataLakeRepository implements
StateStore`) nos resolvedores/planners.

`SQLiteSink` é removido. O enum `SinkType.SQLITE` é removido. O ramo
condicional no `PipelineBuilder.build()` é simplificado para sempre construir
`DataLakeSink`.

### Fase 2 — Swagger-to-Code + Bulk Expansion (4–7 dias)

**Rotas API faltantes (4 endpoints)**

| Domínio | Endpoint | Extractor | Transformer |
|---|---|---|---|
| `blocos_detalhe` | `/blocos/{id}` | `detail_child` (existe) | `detalhe_transformer` (existe) |
| `proposicoes_detalhe` | `/proposicoes/{id}` | `detail_child` (existe) | `detalhe_transformer` (existe) |
| `eventos_orgaos` | `/eventos/{id}/orgaos` | novo `evento_child` variant | novo ou `evento_child_transformer` |
| `mandatos_externos` | `/deputados/{id}/mandatosExternos` | novo `deputado_child` variant | novo ou `deputado_child_transformer` |

Nota: Se os schemas retornados pela API forem idênticos aos de domínios já
existentes, os extratores/transformers genéricos reutilizam-se. Caso contrário,
criam-se classes filhas específicas (padrão já estabelecido no código).

**Swagger-to-code generator**

Criar script em `tools/swagger_codegen.py` que:

1. Lê `docs/camara_swagger.json`
2. Identifica rotas não mapeadas comparando com `DomainType` e YAML existente
3. Gera blocos de configuração YAML para cada rota faltante
4. Gera stubs de `Extractor`, `Transformer`, `SILVER_SCHEMA` e `DomainSpec`
5. Output: blocos de código prontos para copiar, não arquivos sobrescritos
   automaticamente (o desenvolvedor revisa antes de aplicar)

**Expansão Bulk**

O `BULK_REGISTRY` recebe entradas para todos os datasets do HTML da Câmara que
correspondem a domínios já implementados via API. Padrão de URL genérico:

- **Anuais**: `https://dadosabertos.camara.leg.br/arquivos/{dataset}/csv/{dataset}-{year}.csv`
- **Snapshot**: `https://dadosabertos.camara.leg.br/arquivos/{dataset}/csv/{dataset}.csv`

A estrutura do registry é simplificada para suportar templates:

```python
"eventos": {
    "url_template": "https://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-{year}.csv",
    "requires_year": True,
    "bulk_granularity": "year",
    "bulk_filter_date_column": "dataHoraInicio",
}
```

O `SourceRouter` já usa o `BULK_REGISTRY` para decidir Bulk vs API; com mais
domínios registrados, a decisão automática cobre mais casos.

Domínios a adicionar: `eventos`, `frentes`, `grupos`, `gruposMembros`,
`gruposHistorico`, `legislaturas`, `legislaturasMesas`, `orgaos`,
`orgaosDeputados`, `frentesDeputados`, `deputadosOcupacoes`,
`deputadosProfissoes`, `votacoesOrientacoes`.

### Fase 3 — Dominios Bulk-only (5–8 dias)

Novos domínios que **não têm rota na API REST**, apenas dump CSV:

| Dataset | Descrição | Granularidade |
|---|---|---|
| `funcionarios` | Servidores da Câmara | Snapshot |
| `licitacoes` | Licitações | Anual |
| `licitacoesContratos` | Contratos de licitação | Anual |
| `licitacoesItens` | Itens de licitação | Anual |
| `licitacoesPedidos` | Pedidos de licitação | Anual |
| `licitacoesPropostas` | Propostas de licitação | Anual |
| `tecadCategorias` | Categorias da pauta legislativa | Snapshot |
| `tecadTermos` | Termos da pauta legislativa | Snapshot |
| `eventosPresencaDeputados` | Presença de deputados em eventos | Anual |
| `eventosRequerimentos` | Requerimentos de eventos | Anual |
| `votacoesObjetos` | Objetos de votação | Anual |
| `votacoesProposicoes` | Proposições afetadas por votação | Anual |

Cada domínio requer:
- `DomainType` + `DomainSpec` em `core/constants.py` e `core/domain_spec.py`
- `SILVER_SCHEMA` em `core/schemas.py`
- Entrada em `BULK_REGISTRY`
- `Transformer` (ou reúso de genérico)
- Entrada no YAML (`configs/camara_pipeline.yaml`)
- Testes unitários

### Fase 4 — Senado API Adapter (pré-planejamento, 2–4 dias)

- Buscar documentação oficial da API de Dados Abertos do Senado Federal
- Criar spec local em `docs/senado_swagger.json` (quando disponível)
- Analisar endpoints e mapear para `DomainType` (novos ou compatíveis com Câmara)
- Criar `SenadoSourceProvider` seguindo protocolo `SourceProvider`
- Criar `core/senado_constants.py`, `core/senado_schemas.py`
- Implementar extratores e transformers para os primeiros domínios Senado
- Adicionar ao `FederationOrchestrator`

### Gold Layer Export SQL (Futuro, pós Fase 4)

- Utilizar DuckDB `ATTACH 'gold.db' AS gold_db` para criar schema relacional
- Exportar cada tabela Gold como tabela SQL
- CLI flag: `--export-gold sqlite|duckdb`

## Testing Decisions

### O que torna um bom teste

- Testa comportamento externo, não implementação interna
- Para extratores: mocka `httpx`/`respx`. Para bulk: mocka download para
  arquivo CSV local conhecido.
- Para `StateStore`: usa Data Lake temporário (tempdir com Parquet).
- Para transformers: DataFrame conhecido de entrada → DataFrame esperado de
  saída. Teste puro, sem I/O.

### Módulos a testar

| Fase | Módulo | Tipo de Teste | Prior Art |
|---|---|---|---|
| 1 | `storage/state_store.py` | Unitário (tempdir + Parquet) | `tests/storage/test_datalake_repository.py` |
| 1 | `sinks/datalake_sink.py` | Unitário (após remoção SQLite) | `tests/sinks/test_datalake_sink.py` |
| 1 | `pipeline/window_resolver.py` | Unitário com StateStore mock | `tests/pipeline/test_window_resolver.py` |
| 1 | `pipeline/builder.py` | Unitário (após remoção SQLite) | `tests/pipeline/test_builder.py` |
| 1 | `extractors/camara/bulk/base_bulk.py` | Unitário (schema_overrides) | `tests/extractors/camara/bulk/test_bulk_extractor.py` |
| 2 | `tools/swagger_codegen.py` | Unitário (Swagger fixture local) | Novo (primeiro script de geração) |
| 2 | Novos extratores/transformers | Unitário + mock httpx | Padrão existente em `tests/extractors/` e `tests/transformers/` |
| 3 | Novos domínios Bulk-only | Unitário + fixture CSV | `tests/extractors/camara/bulk/test_bulk_extractor.py` |

### Seams de teste

Para as rotas Bulk, o seam mais alto é o `PipelineRunner` com mock de
`BaseBulkExtractor` que retorna DataFrame conhecido de um CSV fixture local.

Para rotas API, o seam mais alto são os extratores individuais com `respx`
mockando a resposta JSON da Câmara.

## Out of Scope

- **Integração com outras fontes além de Câmara e Senado** (TSE, STF, etc.)
  ficam para uma fase futura não especificada.
- **UI/visualização** — este roadmap é 100% backend/ETL.
- **Deploy em nuvem** — performance local primeiro, sem dependência de cluster.
- **Autenticação ou rate limiting de terceiros** — APIs do legislativo são
  abertas sem autenticação.
- **Migração de dados existentes** — dados já ingeridos permanecem intactos.
  Novos domínios começam do zero.
- **Bulk para domínios Bulk-only que tenham overlap com API** — se um dataset
  bulk-only eventualmente ganhar endpoint REST, isso é custódia de uma fase
  futura.

## Further Notes

- A Fase 3 (Bulk-only) pode ser executada em paralelo com a Fase 2, pois os
  datasets são independentes dos domínios API existentes.
- A Fase 4 (Senado) depende de documentação externa a ser obtida — pode sofrer
  atraso se a API do Senado não estiver disponível ou documentada.
- A separação `StateStore` desacopla a leitura de estado da escrita de dados.
  Isso é pré-requisito para que novos providers (Senado) tenham seu próprio
  `StateStore` sem carregar um `BaseSink` completo.
- O formato CSV foi escolhido para Bulk porque Polars o lê nativamente com
  engine paralelizado, é mais compacto que JSON/XML, e não exige dependências
  extras. Os transformers já estão preparados para entrada CSV.
- A nomenclatura de domínio `mandatos_externos` (ao invés de `mandatosexternos`
  ou `mandatosExternos`) segue o padrão snake_case dos demais domínios no
  `DomainType`.
