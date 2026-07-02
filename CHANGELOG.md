# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/),
e este projeto adere ao [Semantic Versioning](https://semver.org/).

## [0.3.0] — 2026-06-28

### Adicionado

- API do Senado Federal: 32 dominios implementados (senadores, mandatos,
  filiacoes, votacoes em plenario, votos, comissoes e membros, discursos,
  pautas, processos, emendas orcamentarias, vetos presidenciais e mais).
- Pipeline seletivo com `--domains` para filtrar dominios na execucao.
- Export para SQLite e DuckDB via `--export-gold`.
- Pre-aquecimento seletivo (warmup) para dominios com alta latencia na
  API da Camara.
- Suporte a concorrencia 10 na API da Camara (testado empiricamente).
- `--audit-coverage` para contagem de registros nas camadas Silver e Gold.
- `_source_url` em toda a camada Gold para auditabilidade.

### Corrigido

- 504 da API da Camara mitigado com warmup seletivo.
- Bulk cache compartilhado no BaseBulkExtractor eliminou downloads
  redundantes.
- Falsos 404 tratados como lista vazia (nao como excecao).
- Bug de null-id no DataLakeOptimizer.
- Watermark de deputados_historico, eventos_pauta e relacionadas.

### Alterado

- Concorrencia aumentada de 5 para 10 (justificado por testes).
- DataLakeSink substituiu BaseSink na ingestao.
- BaseBulkExtractor com cache compartilhado entre dominios.

## [0.2.0] — 2026-05-15

### Adicionado

- Fase 2: 5 dominios bulk (licitacoes, contratos, itens, pedidos, propostas).
- Cross-domain examples: 4 scripts de exemplo analitico multi-dominio.
- Camada Gold com deduplicacao via `ROW_NUMBER OVER PARTITION BY`.
- Smoke E2E test (`examples/smoke_e2e.sh`).
- CLI `--list-domains` com arvore hierarquica de dominios.

### Corrigido

- DomainType.strategies para resolucao de dependencia entre dominios.
- YAML de extractor_bulk com 8 dominios registrados.
- Sink nao forcava criacao do diretorio de destino.

## [0.1.0] — 2026-04-20

### Adicionado

- Versao inicial do ETL para API da Camara dos Deputados.
- 78 endpoints mapeados e implementados.
- Arquitetura medallion (Bronze/Silver/Gold) com append-only.
- Pipelines full_load e incremental com watermark.
- CI via GitHub Actions (Ruff + Pytest).
- CLI basica com `--strategy` e `--optimize`.
- Issue tracker local (`.scratch/`) e templates de issue/PR.

[0.3.0]: https://github.com/redlittlewall/ipolitico-etl/releases/tag/data-20260628
[0.2.0]: https://github.com/redlittlewall/ipolitico-etl/releases/tag/v1.0.0
[0.1.0]: https://github.com/redlittlewall/ipolitico-etl/commits/main
