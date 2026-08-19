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

- **Semáforo de concorrência global.** `CAMARA_HTTP_CONCURRENCY` (padrão: 10, testado empiricamente sem perda)
  protege a API da Câmara. Nunca faça requisições fora do semáforo.
- **Exponential Backoff (tenacity).** Todo worker de extração usa
  `@retry(wait=wait_exponential, stop=stop_after_attempt(5))`.
- **Backoff com teto + quarentena no `CamaraClient`.** O backoff exponencial
  (`2^attempt`) é limitado a `CAMARA_MAX_BACKOFF_S` (padrão 30s) e falhas 5xx
  **consecutivas** em um mesmo recurso o colocam em quarentena
  (`CAMARA_QUARANTINE_THRESHOLD`, padrão 3) — o recurso é pulado até o fim da
  execução (`ResourceQuarantinedError`). Nunca reintroduza backoff sem teto.
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

- **TDD obrigatório (red → green → refactor).** Escreva os testes antes do código.
  Testes novos acompanham código novo; não commite sem `pytest -q` passando.
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

1. **Antes de escrever código novo**, leia `CONTEXT.md` **seletivamente**: liste os
   headers com `grep -n '^## ' CONTEXT.md` e leia apenas a(s) seção(ões) relevante(s)
   ao que está sendo feito — nunca o arquivo inteiro. Verifique `core/` e as classes
   base para não duplicar lógica existente.
2. **Sempre adicione/atualize docstrings** em qualquer classe ou função tocada.
3. **TDD obrigatório:** escreva os testes antes do código (red → green → refactor).
   Testes novos acompanham código novo. Não commite sem `pytest -q` passando.
4. **Nunca aumente o semáforo de concorrência** sem justificativa documentada.
5. **Nunca substitua append-only por upsert na ingestão** — a dedup é responsabilidade
   da camada Gold (`DataLakeOptimizer`), não da ingestão.
6. **Mantenha este arquivo atualizado** conforme a arquitetura evolui.

## Custo de Contexto e Tokens

Cada token lido é reenviado ao modelo a cada turno da sessão — um único arquivo
grande lido 1× pode custar milhões de tokens ao longo da conversa. Regras para não
inflar o contexto:

- **Nunca `Read` arquivos brutos/dumps** (bloqueados em `settings.local.json`):
  `docs/camara_bulk.html`, `docs/camara_swagger.json`, `docs/swagger/*.json`,
  `uv.lock`, `data/**` (parquet, db, log). Para consultar a API use
  `python -m ipolitico.tools.swagger_codegen` ou `grep` no arquivo. Para inspecionar
  dados, escreva um script Polars/DuckDB que imprima só schema, head e uma amostra
  (padrão: scripts `validate_*.py` em `.scratch/`).
- **Prefira ler trechos, não arquivos inteiros.** Use `offset`/`limit` no Read e
  `grep` para localizar o que interessa. Arquivos > 20 KB raramente precisam de leitura
  integral.
- **Não despeje JSON/HTML/XML no contexto.** Processe via script e cite apenas o resultado.
- **Higiene de sessão.** Comece sessão nova por tarefa; quando o contexto acumular,
  use `/compact` ou `/clear` em vez de seguir empilhando.

## Skills

Skills são gerenciadas centralmente via **Facehugger** e linkadas como symlinks:

- Origem: `/home/red_guy/Documentos/Facehugger/skills/skills/`
- Atalhos: `.claude/skills/` (symlinks, não versionados)

Para adicionar/atualizar uma skill, edite o Facehugger — não crie skills locais aqui.

### Skills de engenharia disponíveis

- `/tdd` — Desenvolvimento orientado a testes (red-green-refactor)
- `/code-review` — Revisão de diff por correção e clareza
- `/security-review` — Revisão de segurança de mudanças pendentes
- `/simplify` — Refatoração de código para reduzir complexidade
- `/verify` — Verificação manual de mudanças executando o app
- `/diagnose` — Diagnóstico disciplinado de bugs e regressões
- `/grill-with-docs` — Desafio de plano contra o modelo de domínio existente
- `/improve-codebase-architecture` — Identificar oportunidades de melhoria arquitetural
- `/prototype` — Prototipação rápida
- `/triage` — Classificação de issues
- `/zoom-out` — Visão geral arquitetural
- `/to-issues` — Decompor planos em issues rastreáveis
- `/to-prd` — Converter contexto em PRD

### Skills de produtividade

- `/grill-me` — Stress-test de planos e designs

### Skills de suporte

- `/review` — Revisão de PRs no GitHub
- `/loop` — Execução recorrente de tarefas
- `/deep-research` — Pesquisa multi-fontes com verificação adversarial

### Skills legado (deprecated no Facehugger, mas disponíveis)

- `/qa` — Verificações pré-commit (pytest, pre-commit, debug leftovers)
- `/setup-pre-commit` — Configuração de pre-commit hooks
