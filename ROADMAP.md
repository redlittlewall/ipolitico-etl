# Roadmap de Engenharia — iPolitico ETL

> **Propósito:** Roteiro evolutivo de arquitetura com base na revisão de módulos profundos
> (`.scratch/arquitetura-otimizacao/issues/01-melhorias-arquitetura-etl.md`).
>
> **Princípios:** Módulos Profundos (Ousterhout), CQS, SRP, DRY, desempenho vetorizado (Polars),
> resiliência anti-DDOS, idempotência, versionamento de contratos.

---

## Fase 1 — Estabilização Core e Otimização Local

**Objetivo:** Remover gargalos de performance e rasamento de módulo na base existente.
Tudo aqui pode ser feito sem mudar contratos externos (YAML, schemas, API).

| # | Tarefa | Issue | Esforço | Impacto |
|---|--------|-------|---------|---------|
| 1.1 | **Substituir `map_elements` por expressões Polars nativas** nos transformers de votações e grupos | C2 | ⏱️ 15 min | 🔥 Arquivos quentes: `votacoes_transformer.py`, `institutional_transformer.py`. Usar `pl.col(c).struct.json_encode()` para Struct e `pl.col(c).cast(pl.Utf8)` para Object. Paralelismo Rust recuperado. |
| 1.2 | **Refatorar `PipelineManager.run_domain()` + `CamaraJobPlanner`** com Strategy + Registry de tipos de domínio | C3 | 📅 2-3 dias | ⭐ Maior leverage. Extrair `unique_keys` e `sub_domain` para `DomainSpec`. Criar `RootStrategy`, `ChildStrategy`, `DetailStrategy`, `NestedStrategy`. O if-elif de ~30 ramos vira `registry[domain_type].build(...)`. |
| 1.3 | **Buffer + flush consolidado no DataLakeSink** | C1 | 📅 1 dia | 🗄️ 5k+ micro-arquivos → 1 arquivo por flush. `pl.concat()` no consumer, flush por tamanho (50 MB) ou tempo (5 min). DuckDB Gold não degrada. |
| 1.4 | **Eliminar subclasses rasas de Bulk Extractor** | C4 | ⏱️ 30 min | 🧹 4 classes de 5 linhas viram param config. `BaseBulkExtractor` recebe `domain_name` do YAML. |
| 1.5 | **Schema overrides na leitura bulk CSV** | C5 | 📅 Meio dia | ⚡ `pl.read_csv(schema_overrides=...)` no registry. Elimina recast em cadeia. Moeda BR, datas, IDs resolvidos na leitura. |
| 1.6 | **Extrair interface `StateStore` do `BaseSink`** | C6 | 📅 Meio dia | 🧱 SRP: sink escreve, state store lê watermark. `SQLiteStateStore` + `DataLakeStateStore` (2 adapters = seam real). |

### Critério de saída da Fase 1

- Pipeline de deputados, despesas, proposições e votações roda sem `map_elements`.
- Nenhum if-elif de domínio em `manager.py` ou `camara_jobs.py`.
- Execução completa de `despesas` gera no máximo dezenas de arquivos (não milhares).
- bulk extractors são instanciados por config, não por herança.
- `BaseSink` não tem métodos de leitura de estado.

---

## Fase 2 — Cobertura Total da Câmara dos Deputados

**Objetivo:** Mapear o Swagger (`docs/camara_swagger.json`) e implementar **todos** os endpoints
da API da Câmara que ainda não têm extrator/transformer, respeitando DRY e os padrões
definidos em `CLAUDE.md`.

### Situação atual

| Categoria | Domínios | Status |
|-----------|----------|--------|
| Root (entidades independentes) | `deputados`, `proposicoes`, `votacoes`, `orgaos`, `partidos`, `eventos`, `blocos`, `frentes`, `grupos`, `legislaturas` | ✅ 10/10 implementados |
| Bulk (ZIP/CSV dump) | `deputados`, `despesas`, `proposicoes`, `votacoes` | ✅ 4/4 implementados |
| Child (aninhados) | `votos`, `profissoes`, `ocupacoes`, `discursos`, `tramitacoes`, `autores`, `orientacoes`, `orgaos_membros`, `frentes_membros`, `relacionadas`, `temas`, `proposicoes_votacoes`, `deputados_frentes`, `deputados_orgaos`, `deputados_eventos`, `deputados_historico`, `eventos_deputados`, `eventos_votacoes`, `eventos_pauta`, `partidos_membros`, `partidos_lideres`, `blocos_partidos`, `orgaos_eventos`, `orgaos_votacoes`, `grupos_membros`, `grupos_historico`, `legislaturas_lideres`, `legislaturas_mesa` | ✅ 28/28 implementados |
| Detail (por ID) | `deputados_detalhe`, `orgaos_detalhe`, `eventos_detalhe`, `votacoes_detalhe`, `frentes_detalhe`, `partidos_detalhe`, `grupos_detalhe`, `legislaturas_detalhe` | ✅ 8/8 implementados |
| Referência (catálogos) | `referencias` | ✅ 1/1 implementado |

**Total: 47 domínios — 47/47 mapeados no YAML e no `DomainSpec`.**

> Status em 2026-06-03: cobertura de domínios está **completa**. O foco desta fase
> muda de "implementar o que falta" para **consolidar qualidade** e preencher lacunas
> funcionais.

### Tarefas

| # | Tarefa | Esforço | Justificativa |
|---|--------|---------|---------------|
| 2.1 | **Auditar campos nulos em todos os transformers** — cada transformer deve emitir schemas consistentes mesmo quando a API retorna dados parciais | 📅 2 dias | Dados reais da Câmara têm omissões frequentes; colunas `null` quebram downstream no DuckDB Gold |
| 2.2 | **Criar testes de integração smoke para cada domínio** — um deputado, uma proposição, uma votação; validar schema de saída + checkpoint de watermark | 📅 3-4 dias | Sem testes, regressão silenciosa em domínios de baixa prioridade |
| 2.3 | **Documentar contratos de dados** — schema Parquet esperado em Silver para cada domínio, com dtypes e exemplos | 📅 1 dia | Necessário para consumidores Gold (analytics, dashboards) |
| 2.4 | **Implementar `GoldLayerBuilder`** — views materializadas no DuckDB que consolidam Silver → Gold com joins, agregações e janelas temporais | 📅 3-4 dias | Camada Gold é o produto final; hoje Silver existe mas não há rotina de consolidação |
| 2.5 | **Dashboard de monitoramento** — métricas de execução (domínios, watermarks, volume, latência) expostas via métricas leves (Prometheus ou SQLite + endpoint HTTP simples) | 📅 2 dias | Sem telemetria consolidada, debug de falhas parciais é manual |

### Critério de saída da Fase 2

- Teste smoke (`pytest -m smoke`) cobre todos os 47 domínios e passa.
- Silver tem schemas documentados e consistentes (nulos explícitos, sem colunas faltando).
- Gold Layer Builder roda como CLI (`ipolitico gold build`) e como stage do pipeline.
- Métricas de execução visíveis em endpoint ou relatório.

---

## Fase 3 — Federação e Expansão Multi-Fonte

**Objetivo:** Incorporar a API de Dados Abertos do Senado Federal em paralelo com a Câmara,
com barreira semântica rígida de concorrência para não sobrecarregar nenhum órgão.

### Arquitetura alvo

```
                    ┌─────────────────────┐
                    │  PipelineOrchestrator │
                    │  (coordena fontes)   │
                    └──────┬──────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
     ┌────────▼────────┐     ┌─────────▼────────┐
     │ CamaraOrchestrator    │ SenadoOrchestrator │
     │ (CAMARA_HTTP_CON=5)   │ (SENADO_HTTP_CON=3)│
     └────────┬────────┘     └─────────┬────────┘
              │                         │
     ┌────────▼────────┐     ┌─────────▼────────┐
     │  Camara API     │     │  Senado API      │
     │  (já existe)    │     │  (nova)          │
     └─────────────────┘     └──────────────────┘
```

### Tarefas

| # | Tarefa | Esforço | Dependências |
|---|--------|---------|--------------|
| 3.1 | **Mapear Swagger/API do Senado** — endpoints, rate limits, paginação, autenticação | 📅 1 dia | Nenhuma (pode correr em paralelo com Fase 2) |
| 3.2 | **Criar `BaseExtractor` para Senado** — reutilizar `BaseApiExtractor`, adaptar autenticação se necessário | 📅 1 dia | 3.1 |
| 3.3 | **Extratores/Transformers do Senado** — implementar seguindo o pattern da Câmara (root → child → detail) | 📅 5-7 dias | 3.2 |
| 3.4 | **Circuit Breaker + Rate Limiter multi-fonte** — semáforo dedicado por órgão, fallback com backoff se um dos dois estiver degradado | 📅 2 dias | 3.1, 3.2 |
| 3.5 | **Barreira semântica de federação** — `PipelineOrchestrator` decide qual fonte extrair para qual domínio unificado (ex: `senador` ↔ `deputado`) | 📅 2 dias | 3.3 |
| 3.6 | **Camada Gold federada** — consolidar Câmara + Senado em visões unificadas (gastos parlamentares, proposições, votações) | 📅 3 dias | 3.5, 2.4 |
| 3.7 | **Paralelismo intra-fonte** — workers paralelos por domínio dentro da mesma fonte, respeitando o semáforo do órgão | 📅 1 dia | 3.4 |

### Critério de saída da Fase 3

- Pipeline extrai dados do Senado em paralelo com a Câmara.
- `CircuitBreaker` isola falha de uma fonte sem afetar a outra.
- Gold consolidada tem visões federadas: `gastos_parlamentares` (deputados + senadores),
  `proposicoes` (PLs Câmara + PLS Senado).
- Throughput máximo seguro empírico documentado para cada órgão.

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Câmara altera schema da API sem aviso | Média | Alto | Testes smoke semanais + alerta de schema mismatch |
| Bulk dump ZIP corrompido | Baixa | Médio | Checksum SHA256 + retry com fallback para API |
| Rate limit do Senado mais restritivo | Alta | Médio | Circuit breaker por fonte; fila de replay |
| Crescimento não-linear de arquivos Silver | Alta | Médio | Buffer + flush (Fase 1.3) + purge periódico Bronze |

---

## Métricas de Acompanhamento

- **Cobertura de domínios:** 47/47 Câmara → N Senado (Fase 3)
- **Arquivos Silver por execução:** 5k+ → < 100 (Fase 1.3)
- **Linhas de if-elif removidas:** ~1.020 → 0 (Fase 1.2)
- **Tempo de execução full load:** baseline → -40% (Fase 1.1 + 1.5)
- **Testes:** 0 → smoke coverage 47 domínios (Fase 2.2)
