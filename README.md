<div align="center">

# iPolitico ETL

**Dados abertos da política brasileira — ao alcance de um comando.**

[![CI](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/ci.yml)
[![Pipeline](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/pipeline.yml/badge.svg)](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/pipeline.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Polars](https://img.shields.io/badge/Polars-1.0+-CD5C5C?logo=polars&logoColor=white)](https://pola.rs)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.0+-FFF000?logo=duckdb&logoColor=black)](https://duckdb.org)
[![HTTPX](https://img.shields.io/badge/HTTPX-async-0080FF)](https://www.python-httpx.org/)
[![Data](https://img.shields.io/badge/data-12M_records-green)](https://github.com/redlittlewall/ipolitico-etl/releases/latest)
[![GitHub last commit](https://img.shields.io/github/last-commit/redlittlewall/ipolitico-etl/main)](https://github.com/redlittlewall/ipolitico-etl/commits/main/)
</div>

---

O **iPolitico** é um motor ETL que baixa, organiza e disponibiliza dados abertos das duas casas do Congresso Nacional — [Câmara dos Deputados](https://dadosabertos.camara.leg.br/swagger/api.html) e [Senado Federal](https://legis.senado.leg.br/dadosabertos/). Tudo em Parquet, sem depender de banco externo.

**Pra quê?** Pra que qualquer pessoa — jornalista, pesquisador, desenvolvedor ou cidadão — possa analisar a atividade legislativa brasileira sem precisar caçar 96 endpoints de API diferentes.

## Caracteristicas

- **Cobertura completa**: 96 dominios das APIs da Camara e do Senado, mais dumps bulk.
- **Incremental por default**: baixa so o que mudou desde a ultima execucao.
- **Funciona offline**: dados em Parquet na maquina local, sem dependencia de banco.
- **Exporta para SQLite e DuckDB**: analise com SQL diretamente nos dados.
- **Resiliente**: retry com backoff, semaforo de concorrencia, tolerante a falhas de API.
- **Auditavel**: todo registro tem timestamp de captura e URL de origem.
- **Idempotente**: execucoes repetidas nao corrompem dados (append-only + dedup na Gold).
- **Civico e gratuito**: codigo aberto (MIT), sem servidor, sem custo.

## 🔥 Só quer os dados prontos?

Se você não precisa rodar o ETL, baixa o dataset completo:

```bash
wget https://github.com/redlittlewall/ipolitico-etl/releases/latest/download/gold.tar.gz
tar xzf gold.tar.gz
# → gold/ com 96 arquivos .parquet (~12 milhões de registros)
```

| Conteúdo | Fonte | Registros |
|---|---|---|
| **🇧🇷 Câmara dos Deputados** | | |
| Deputados (cadastro + histórico) | Câmara | 11.169 |
| Despesas CEAP | Câmara | 1,4 milhão |
| Proposições legislativas | Câmara | 14.907 |
| Votações nominais | Câmara | 27.393 |
| Votos individuais | Câmara | 435.388 |
| Eventos na Câmara | Câmara | 58.930 |
| Partidos, Blocos, Frentes, Grupos | Câmara | 1.721 |
| Licitações + contratos | Câmara | 125.636 |
| Presença em eventos | Câmara | 2,6 milhões |
| **🇧🇷 Senado Federal** | | |
| Senadores (cadastro + histórico) | Senado | 1.943 |
| Mandatos e filiações | Senado | 12.200 |
| Votações nominais em plenário | Senado | 3.100 |
| Votos individuais | Senado | 560.000 |
| Votações em comissões | Senado | 7.000 |
| Processos legislativos | Senado | 58.000 |
| Comissões e membros | Senado | 900 |
| Plenário (agenda, resultados, sessões) | Senado | 3.000 |
| Vetos presidenciais | Senado | 2.200 |
| Emendas e ofícios orçamentários | Senado | 18.000 |
| **Total (96 domínios)** | **Ambas** | **~12 milhões** |

> Dados atualizados semanalmente via GitHub Actions. Consulte o [CHANGELOG](CHANGELOG.md) para o historico de versoes.

## Instalacao rapida

```bash
pip install git+https://github.com/redlittlewall/ipolitico-etl.git

# Verifica se instalou
ipolitico --list-domains | head -10
```

Se preferir desenvolvimento, clone com venv:

```bash
git clone https://github.com/redlittlewall/ipolitico-etl.git
cd ipolitico-etl
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## 🐳 Docker (sem instalar Python)

Tudo que você precisa é o Docker. A imagem já vem com todas as dependências.

```bash
# Build local da imagem
docker build -t ipolitico-etl .

# Quickstart: lista os domínios disponíveis
docker run --rm ipolitico-etl --list-domains | head -10

# Baixa os dados incrementais (monta volume para persistir)
docker run --rm -v $(pwd)/data:/app/data ipolitico-etl --strategy incremental --optimize

# Ajuda completa
docker run --rm ipolitico-etl --help
```

> Futuramente: `docker pull ghcr.io/redlittlewall/ipolitico-etl:latest` quando a imagem for publicada automaticamente via CI.

### Comandos úteis

| Comando | O que faz |
|---|---|
| `docker run --rm ipolitico-etl --list-domains` | Lista todos os domínios disponíveis |
| `docker run --rm -v $(pwd)/data:/app/data ipolitico-etl --strategy full_load --optimize` | Baixa tudo do zero |
| `docker run --rm ipolitico-etl download-data --dry-run` | Mostra a URL da última release Gold sem baixar |
| `docker run --rm -v $(pwd)/data:/app/data ipolitico-etl download-data` | Baixa dados Gold prontos da última release |
| `docker run --rm ipolitico-etl python -c "import polars; print('OK')"` | Verifica dependências |
| `docker run --rm -v $(pwd)/data:/app/data ipolitico-etl python examples/dtlake/coesao_partidaria.py` | Roda uma análise específica |

### Perfil Analysis (Jupyter + matplotlib)

A imagem com perfil `analysis` inclui Jupyter Lab, matplotlib e seaborn para exploração interativa.

```bash
# Build com perfil analysis
docker build --build-arg PROFILE=analysis -t ipolitico-etl:analysis .

# Sobe Jupyter Lab
docker run --rm -p 8888:8888 -v $(pwd)/data:/app/data ipolitico-etl:analysis
```

### Docker Compose

O `docker-compose.yml` fornece conveniência para os dois perfis:

```bash
# Executa o ETL
docker compose run --rm etl --strategy incremental --optimize

# Sobe Jupyter Lab (porta 8888)
docker compose up -d analysis
# Acesse: http://localhost:8888

# Comandos avulsos (Python, scripts)
docker compose run --rm etl python examples/dtlake/coesao_partidaria.py

# Derruba tudo
docker compose down

# Derruba tudo inclusive volumes de dados
docker compose down --volumes
```

### Build local

```bash
# Perfil base (padrão, ~200MB)
docker build -t ipolitico-etl .

# Perfil analysis (~350MB)
docker build --build-arg PROFILE=analysis -t ipolitico-etl:analysis .
```

### Volumes

Monte `$(pwd)/data:/app/data` para persistir dados entre execuções:

```bash
# Linux/Mac
docker run --rm -v $(pwd)/data:/app/data ipolitico-etl --strategy incremental --optimize

# Windows (PowerShell)
docker run --rm -v ${PWD}/data:/app/data ipolitico-etl --strategy incremental --optimize

# Windows (CMD)
docker run --rm -v %cd%/data:/app/data ipolitico-etl --strategy incremental --optimize
```

### Workshop — comando único para começar

```bash
docker run --rm -v $(pwd)/data:/app/data ipolitico-etl --strategy full_load --optimize
```

Isso baixa e processa todos os 96 domínios (~12 milhões de registros). A primeira execução leva alguns minutos; execuções subsequentes (incremental) são segundos.

> **Nota**: O comando `download-data` depende de uma release Gold publicada. Até a primeira release completa, use `--source-dir` para testar com dados locais: `docker run --rm -v $(pwd)/gold:/app/gold ipolitico-etl download-data --source-dir /app/gold`.

## Como usar

```bash
# 1. Instala
git clone https://github.com/redlittlewall/ipolitico-etl.git
cd ipolitico-etl
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Explora os domínios disponíveis
ipolitico --list-domains

# 3. Baixa os dados (incremental = só novidades)
ipolitico --strategy incremental --optimize

# Ou baixa tudo do zero
ipolitico --strategy full_load --optimize

# Ou só um domínio específico
ipolitico --strategy incremental --domains deputados --optimize

# Exporta pra SQLite se preferir
ipolitico --strategy incremental --optimize --export-gold sqlite
```

## 🏗️ Como funciona

```
┌─ Câmara (API Dados Abertos) ──┐
├─ Senado (API Dados Abertos) ───┤
├─ CSVs/Dumps (Bulk) ────────────┤
│           ↓                     │
│  Extratores (async + retry)     │  ← httpx + tenacity
│           ↓                     │
│  Transformers (vetorizado)      │  ← Polars
│           ↓                     │
│  ┌─────────────────────────┐    │
│  │ SILVER (append-only)    │    │  ~20M registros brutos
│  └─────────┬───────────────┘    │
│            ↓                    │
│  ┌─────────────────────────┐    │
│  │ GOLD (deduplicado)      │    │  ← o que você baixa
│  │ ~12M registros, 1/dia   │    │
│  └─────────────────────────┘    │
└─────────────────────────────────┘
```

### Stack

| Pra quê | O que usa | Por quê |
|---|---|---|
| Processar dados | [Polars](https://pola.rs/) | Rápido, vetorizado, roda em qualquer máquina |
| Baixar APIs | [HTTPX](https://www.python-httpx.org/) | Async, com timeout e retry |
| Analisar | [DuckDB](https://duckdb.org/) | SQL direto nos Parquet sem servidor |
| Qualidade | Ruff + Pytest | Código limpo, testes que passam |

## 📊 Cobertura

| Fonte | Status |
|---|---|
| API da Câmara dos Deputados | **78/78** endpoints (100%) ✅ |
| API do Senado Federal | **32/32** domínios implementados ✅ |

| Categoria | Domínios | Exemplos |
|---|---|---|
| Entidades principais | 10 | deputados, proposicoes, votacoes, orgaos, partidos, eventos |
| Filhos (relacionamentos) | 41 | despesas, discursos, votos, tramitacoes, autores, membros |
| Detalhes | 13 | deputados_detalhe, orgaos_detalhe, proposicoes_detalhe |
| Dados massivos (Bulk CSV) | 13 | licitacoes, funcionarios, presenca, tecad |

> ℹ️ `partidos_lideres` é o único endpoint funcional da API que não retorna dados — a API devolve `[]` pra maioria dos partidos. Extraímos os poucos registros que existem.

## Como contribuir

1. Faca um fork do projeto.
2. Crie sua branch (`git checkout -b feat/minha-feature`).
3. Rode `ruff check .` e `pytest -q` antes de commitar.
4. Abra um Pull Request.

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes sobre arquitetura, convencoes de codigo e estrutura do projeto.

## Proximos Passos

- [x] API do Senado Federal
- [ ] Portal da Transparencia
- [x] Export automatico para SQLite e DuckDB
- [ ] Dados do TSE (eleicoes)

## Links

- [CHANGELOG](CHANGELOG.md) — historico de versoes
- [CONTRIBUTING.md](CONTRIBUTING.md) — guia de contribuicao
- [SECURITY.md](SECURITY.md) — politica de seguranca
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — codigo de conduta
- [LICENSE](LICENSE) — MIT License
