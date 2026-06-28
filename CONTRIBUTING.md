# Contribuindo com o iPolitico ETL

Obrigado por considerar contribuir com o **iPolitico**! Este projeto tem como objetivo mitigar a assimetria informacional entre eleitos e cidadãos, e toda ajuda é bem-vinda.

## Código de Conduta

Este projeto adota um [Código de Conduta](CODE_OF_CONDUCT.md). Ao participar, espera-se que você mantenha um ambiente respeitoso e colaborativo.

## Como Contribuir

### 1. Reportando Bugs

Use o template de [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml). Inclua:

- Descrição clara do problema
- Passos para reproduzir
- Comportamento esperado vs observado
- Logs de execução (se aplicável)
- Versão do Python e SO

### 2. Solicitando Funcionalidades

Abra uma [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml). Explique:

- Qual problema você quer resolver
- Como você imagina a solução
- Alternativas consideradas

### 3. Pull Requests

1. **Faça um fork** do repositório
2. **Crie uma branch** descritiva:
   ```bash
   git checkout -b feat/nova-fonte-dados
   git checkout -b fix/correcao-watermark
   ```
3. **Desenvolva com TDD** — escreva o teste antes do código
4. **Mantenha a arquitetura**:
   - Extratores só fazem I/O (não transformam)
   - Transformers são puros (sem I/O, sem estado)
   - Sinks só persistem dados
5. **Rode as verificações locais**:
   ```bash
   ruff check src tests
   ruff format --check src tests
   pytest -q
   bash examples/smoke_e2e.sh
   ```
6. **Abra o Pull Request** usando o template disponível

### 4. Convenções de Código

- **Docstrings Google-style** em toda função/classes criada ou alterada
- **Domínios novos** exigem `DomainType`, `DomainSpec`, entry no YAML e teste
- **Testes assíncronos** com `pytest-asyncio` (modo `auto` configurado)
- **Operações vetorizadas Polars** — nunca loops Python em DataFrames
- **Async puro** (asyncio + httpx) — não bloqueie o event loop

### 5. Estrutura do Projeto

```
src/ipolitico/
├── core/              # Constantes, schemas, contratos
├── extractors/        # I/O com APIs e arquivos
│   └── camara/
│       ├── api/       # Extratores REST (paginados, filhos, detalhes)
│       └── bulk/      # Extratores de dumps CSV
├── transformers/      # Transformação pura (Polars)
├── sinks/             # Persistência (DataLake, SQLite)
├── pipeline/          # Orquestração (builder, runner, planners)
└── storage/           # Repositórios de leitura, state store
```

## Precisa de Ajuda?

Abra uma [Discussion](https://github.com/redlittlewall/ipolitico-etl/discussions) ou uma Issue com a tag `question`.
