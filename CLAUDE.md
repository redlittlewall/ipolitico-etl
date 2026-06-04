# CLAUDE.md — iPolitico ETL

> Regras de governança do agente. Leia antes de qualquer alteração no código.

## Filosofia do Projeto

- **Código aberto, cívico e auditável.** iPolitico é um ETL que mitiga assimetria
  informacional entre eleitos e cidadãos.
- **Performance local primeiro.** Dados políticos cabem na RAM de um notebook.
  Tudo feito para execução local rápida — sem dependência de clusters.
- **Resiliência contra APIs governamentais.** A API da Câmara tem instabilidades
  conhecidas (timeout, 502, 429). O código assume falha e se recupera.
- **Imutabilidade e auditabilidade.** Todo dado ingerido é append-only. Nada é
  sobrescrito. `captured_at` em todo registro.

## Regras Inegociáveis de Código

### Performance & Concorrência

- **Operações vetorizadas Polars sempre.** Nunca use loops Python explícitos para
  transformar DataFrames. Use `pl.col()`, `pl.when()`, `pl.selectors`.
- **Async puro (asyncio + httpx).** Nunca bloqueie o event loop com chamadas
  síncronas de rede. I/O de arquivo local pode usar `asyncio.to_thread`.
- **Backpressure.** A fila `df_queue` com `maxsize=10` no `PipelineRunner` protege
  contra OOM. Nunca remova ou aumente esse limite sem justificativa.

### Resiliência (Anti-DDOS)

- **Semáforo de concorrência global.** `CAMARA_HTTP_CONCURRENCY` (padrão: 5)
  protege a API da Câmara. Nunca faça requisições fora do semáforo.
- **Exponential Backoff (tenacity).** Todo worker de extração usa
  `@retry(wait=wait_exponential, stop=stop_after_attempt(5))`.
- **Falsos 404 são lista vazia.** A API retorna 404 para recursos sem dados —
  não para erros. Trate como `[]`, não como exceção.
- **Range header em downloads bulk.** Retome downloads interrompidos, não recomece
  do zero.

### DRY — Não Repita Camadas

- **Sempre inspecione `core/` antes de criar algo novo.** `DomainType`, `DomainSpec`,
  `SILVER_SCHEMAS`, `EarliestDates`, `ApiRoutes`, `ApiParams` — estão todos lá.
- **Sempre inspecione as classes base:**
  - `extractors/base.py` → `BaseExtractor`
  - `transformers/base.py` → `BaseTransformer`
  - `sinks/base.py` → `BaseSink`
  - `extractors/camara/api/camara_base.py` → `CamaraBaseExtractor`
  - `extractors/camara/bulk/base_bulk.py` → `BaseBulkExtractor`
- **Nunca replique lógica de resolução de janela, watermark ou dependência entre
  domínios.** Use `WindowResolver`, `EffectiveWindow` e `domain_order.py`.
- **Nunca crie um novo sink do zero.** Escolha entre `DataLakeSink` ou estenda
  a interface `BaseSink`.

### Docstrings Obrigatórias

Toda classe ou função **criada ou alterada** DEVE ter docstring padrão com:

1. **O que é/comportamento central** — Uma linha clara do propósito.
2. **Inputs/Args** — O que cada parâmetro significa e seu tipo.
3. **Outputs/Returns** — O que retorna (incluindo casos de borda: DataFrame vazio,
   None, lista vazia).

Formato (Google-style):
```python
def minha_funcao(param: str) -> pl.DataFrame:
    """
    Descrição concisa do que a função faz e seu comportamento central.

    Args:
        param: Descrição do parâmetro.

    Returns:
        Descrição do retorno, incluindo casos de borda.
    """
```

Se o código editado **não tiver docstring** ou a docstring estiver **desatualizada**
(assinatura, comportamento, tipos), **você deve corrigi-la** como parte da edição.

### Testes

- **Novos fluxos exigem testes unitários assíncronos no Pytest.**
- Use `pytest-asyncio` (modo `asyncio_mode = auto` já configurado).
- Teste cada camada isoladamente: extrator (mock `httpx`/`respx`), transformer
  (DataFrame conhecido), sink (arquivo temporário).
- Testes de integração smoke (`smoke_e2e.sh`) validam imports e CLI sem rede.
- `pytest -q` antes de qualquer commit.

### Padrões de Arquitetura (Clean Code + DDIA)

- **Command-Query Separation.** Funções que mutam estado não retornam valor;
  funções que consultam não mutam estado.
- **SRP (Single Responsibility).** Extratores só fazem I/O. Transformers são puros
  (sem I/O, sem estado). Sinks só persistem. Violação disso é bug.
- **Data contracts são versionados.** `SILVER_SCHEMAS` em `core/schemas.py` é o
  contrato da camada Silver. Mudar um schema exige compatibilidade retroativa
  (old code + old data + new code).
- **Idempotência.** Jobs são reexecutáveis sem dano. Sink append-only + dedup na
  Gold via `ROW_NUMBER OVER PARTITION BY`.
- **Happy path legível.** Tratamento de erro não esconde o fluxo principal.
  Use early return para casos de borda.

## Comportamento do Agente

1. **Antes de escrever código novo**, leia `CONTEXT.md` e verifique `core/`
   e as classes base para não duplicar lógica existente.
2. **Sempre adicione/atualize docstrings** em qualquer classe ou função tocada.
3. **Testes novos** acompanham código novo. Não commite sem `pytest -q` passando.
4. **Nunca aumente o semáforo de concorrência** sem justificativa documentada.
5. **Nunca substitua append-only por upsert na ingestão** — a dedup é responsabilidade
   da camada Gold (`DataLakeOptimizer`), não da ingestão.
6. **Mantenha este arquivo atualizado** conforme a arquitetura evolui.

## Agent skills

### Issue tracker

Issues and PRDs live as local markdown files under `.scratch/<feature-slug>/`.
See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default names (`needs-triage`,
`needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`).
See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` at the repo root.
See `docs/agents/domain.md`.

### Commit flow

After any `/tdd` cycle or manual implementation, use `/commit` to automate
staging, tests, pre-commit, conventional commit message, push, and optional PR.
See `.claude/skills/commit/SKILL.md`.
