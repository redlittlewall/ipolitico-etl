<div align="center">

# 🏛️ iPolitico ETL

**Dados abertos da política brasileira — ao alcance de um comando.**

[![CI](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/ci.yml)
[![Pipeline](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/pipeline.yml/badge.svg)](https://github.com/redlittlewall/ipolitico-etl/actions/workflows/pipeline.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Data](https://img.shields.io/badge/data-7.3M_records-green)](https://github.com/redlittlewall/ipolitico-etl/releases/latest)
</div>

---

O **iPolitico** é um motor de Extração, Transformação e Carga (ETL) que consome a [API de Dados Abertos da Câmara dos Deputados](https://dadosabertos.camara.leg.br/swagger/api.html) e constrói um Data Lake moderno, imutável e auditável em formato **Parquet**.

**Missão:** Mitigar a assimetria informacional entre eleitos e cidadãos.

## 🔥 Quer só os dados? Baixe o Gold

Não quer rodar o ETL? Baixe o dataset completo pronto pra usar:

```bash
# Download do dataset Gold mais recente (~80 MB)
wget https://github.com/redlittlewall/ipolitico-etl/releases/latest/download/gold.tar.gz
tar xzf gold.tar.gz
# → pasta gold/ com 63 .parquet (7,3 milhões de registros)
```

| Conteúdo | Registros |
|---|---|
| Deputados (cadastro + histórico) | 11.169 |
| Despesas CEAP | 1,4 milhão |
| Proposições legislativas | 14.907 |
| Votações nominais | 27.393 |
| Votos individuais | 435.388 |
| Eventos na Câmara | 58.930 |
| Discursos em plenário | 34 |
| Partidos, Blocos, Frentes, Grupos | 1.721 |
| Licitações + contratos | 125.636 |
| Presença em eventos | 2,6 milhões |
| **Total (63 domínios)** | **~7,3 milhões** |

> Os dados são atualizados semanalmente via GitHub Actions.

## 🚀 Instalação

```bash
# Clone
git clone https://github.com/redlittlewall/ipolitico-etl.git
cd ipolitico-etl

# Instale
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Use!
ipolitico --list-domains
```

## 📋 Comandos

```bash
# Listar todos os domínios disponíveis
ipolitico --list-domains

# Auditar cobertura dos dados já baixados
ipolitico --audit-coverage

# Executar pipeline incremental (atualiza dados desde última execução)
ipolitico --strategy incremental --optimize

# FULL LOAD completo (baixa tudo do zero)
ipolitico --strategy full_load --optimize

# Apenas um domínio específico
ipolitico --strategy incremental --domains deputados --optimize

# Exportar Gold para SQLite
ipolitico --strategy incremental --optimize --export-gold sqlite
```

## 🏗️ Arquitetura

```
🏗️ API Dados Abertos (Câmara) ──┐
📦 CSVs/Dumps (Bulk) ───────────┤
                                 ▼
                        ┌─────────────────┐
                        │   Extratores    │ ← Async (httpx + asyncio)
                        │   Resiliência   │ ← Retry (tenacity), backoff
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  Transformers   │ ← Polars (vetorizado)
                        │  Schemas rígidos│ ← SILVER_SCHEMAS
                        └────────┬────────┘
                                 ▼
            ┌──────────────────────────────────┐
            │        SILVER (append-only)       │
            │  ~17M registros, ~750 parquets    │
            └────────────────┬─────────────────┘
                             ▼
            ┌──────────────────────────────────┐
            │        GOLD (deduplicado)         │
            │  ~7,3M registros, 1 parquet/dom.  │
            │  ← É O QUE DISPONIBILIZAMOS       │
            └──────────────────────────────────┘
```

### Stack Tecnológica

| Componente | Tecnologia | Motivo |
|---|---|---|
| **Linguagem** | Python 3.12+ | Acessível, comunidade grande |
| **Processamento** | [Polars](https://pola.rs/) | DataFrames vetorizados (Rust) |
| **Async HTTP** | [HTTPX](https://www.python-httpx.org/) | Requests assíncronas com timeouts |
| **Analytics** | [DuckDB](https://duckdb.org/) | OLAP embedded, SQL direto em Parquet |
| **Qualidade** | Ruff + Pytest | Linter rápido, TDD |

## 📊 Cobertura

Endpoints da API da Câmara: **78/78** (100%) ✅

| Categoria | Domínios | Exemplos |
|---|---|---|
| Entidades principais | 10 | deputados, proposicoes, votacoes, orgaos, partidos, eventos |
| Filhos (relacionamentos) | 41 | despesas, discursos, votos, tramitacoes, autores, membros |
| Detalhes | 13 | deputados_detalhe, orgaos_detalhe, proposicoes_detalhe |
| Dados massivos (Bulk CSV) | 13 | licitacoes, funcionarios, presenca, tecad |

> ℹ️ `partidos_lideres` (rota `/partidos/{id}/lideres`) é o único endpoint funcional da API que não possui dados — a API retorna `[]` para a maioria dos partidos. Extraímos os poucos registros existentes.

## 🤝 Como Contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Resumo:

1. Fork o projeto
2. Crie sua branch (`git checkout -b feat/minha-feature`)
3. Commit com `ruff check` + `pytest` passando
4. Abra um Pull Request

## 📜 Licença

MIT — veja [LICENSE](LICENSE).

## 🌟 Próximos Passos

- [ ] API do Senado Federal
- [ ] Portal da Transparência
- [ ] Export automático para SQLite/DuckDB
- [ ] Dados do TSE (eleições)
