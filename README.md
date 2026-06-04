# iPolitico ETL

O **iPolitico** é um motor de Extração, Transformação e Carga (ETL) projetado para realizar a auditoria cívica dos dados do Poder Legislativo Brasileiro. O objetivo é mitigar a assimetria informacional entre eleitos e cidadãos através da construção de um Data Lake moderno, imutável e auditável.

## Arquitetura e Diferenciais

O projeto foi construído sob princípios de **Engenharia de Dados moderna**, focando em resiliência contra as instabilidades das APIs governamentais:

* **Arquitetura Híbrida (Bulk + API):** Consome arquivos massivos (Dumps ZIP/CSV) para cargas históricas em segundos, e utiliza a API REST paginada para atualizações diárias cirúrgicas.
* **OLTP & OLAP Sinks:** Permite salvar dados transacionais em `SQLite` para a gestão de estado/metadados, ou construir um Data Lake analítico em arquivos `.parquet` para agregações massivas via DuckDB.
* **Resiliência (Backoff & Throttling):** Motor assíncrono blindado contra timeouts (504), quedas de gateway (502) e limites de taxa (429), implementando *Exponential Backoff* e *Graceful Degradation*.
* **Processamento Colunar:** Utiliza [Polars](https://pola.rs/) para manipulação de dados na velocidade da luz (Rust-backed).

## Stack Tecnológica

- **Linguagem:** Python 3.12+
- **Processamento:** Polars (Rust-backed DataFrames)
- **Networking:** HTTPX (Async)
- **Qualidade:** Ruff (Linter/Formatter) & Pytest (TDD)
- **Banco de Dados:** SQLite (padrão) & Parquet (Data Lake)

## Como Instalar

1. Clone o repositório:
```bash
git clone [https://github.com/seu-usuario/ipolitico-etl.git](https://github.com/seu-usuario/ipolitico-etl.git)

cd ipolitico-etl
```

2. Crie e ative seu ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
```

3. Instale em modo editável:
```bash
pip install -e .
```

## Execução via CLI (Command Line Interface)

Parâmetros principais: `--strategy`, `--domains`, `--start-date`, `--end-date`, `--optimize`.
A origem (API vs Bulk) é escolhida pelo `SourceRouter`; o destino é o Data Lake (Parquet).

1. Incremental (janela explícita)

```bash
python -m ipolitico.main --strategy incremental \
  --domains deputados --start-date 2025-01-01 --end-date 2025-01-31
```

2. Full load multi-ano (Bulk automático em despesas/proposições/votações quando aplicável)

```bash
python -m ipolitico.main --strategy full_load \
  --domains despesas --start-date 2023-01-01 --end-date 2024-12-31
```

3. Ordem recomendada: `deputados` → `despesas` → `proposicoes` → `votacoes` → `votos` (votos exige IDs em silver/gold de votações no **mesmo período**). Opcional: `profissoes` / `ocupacoes` após `deputados`.

```bash
python -m ipolitico.main --strategy incremental \
  --domains proposicoes votacoes votos \
  --start-date 2025-01-01 --end-date 2025-01-31 --optimize
```

## Exportar Gold para SQL (SQLite / DuckDB)

A camada Gold (Parquet deduplicado) pode ser exportada para bancos SQL
relacionais via DuckDB. Útil para queries ad hoc, BI tools ou compartilhamento.

```bash
# Exportar para SQLite (data/gold_export.db)
python -m ipolitico.main --export-gold sqlite

# Exportar para DuckDB nativo (data/gold_export.duckdb)
python -m ipolitico.main --export-gold duckdb

# Combinado com otimização Gold (pipeline → optimize → export)
python -m ipolitico.main --strategy incremental --domains deputados \
  --start-date 2025-01-01 --end-date 2025-01-31 --optimize --export-gold sqlite
```

O exportador (`GoldExporter`) descobre automaticamente todos os domínios com
dados na camada Gold e cria uma tabela SQL para cada um. No formato SQLite,
índices são criados nas colunas de chave primária de cada tabela para
performance em consultas relacionais.

## Ordem sugerida (smoke local)

1. Instale dependências (`pip install -e .`).
2. Rode `bash examples/smoke_e2e.sh` (imports + `--help` sem rede).
3. Para ETL real contra a API, use janelas curtas e rode `deputados` antes de domínios dependentes (ex.: `votos` após `votacoes`).

## Testes

```bash
pytest -q
bash examples/smoke_e2e.sh
```

CI (GitHub Actions): `ruff check`, `ruff format --check`, `pytest` e smoke local em cada PR.

## Estimativa de tempo (API vs Bulk)

Script heurístico (usa `data/dbs/api_telemetry.db` se existir para calibrar latência):

```bash
python examples/estimate_camara_ingestion.py --scenario full-hybrid   # recomendado
python examples/estimate_camara_ingestion.py --scenario full-api      # pior caso (só HTTP)
```

Variáveis de tuning: `CAMARA_HTTP_CONCURRENCY` (padrão até 5), `MAX_CONCURRENT_REQUESTS` (workers do runner).

## Contribuição

Contribuições que visam a transparência pública são bem-vindas.

1. Faça um fork do projeto.

2. Crie uma branch para sua feature (git checkout -b feature/nova-api).

3. Certifique-se de que o ruff não aponta erros de estilo.

4. Abra um Pull Request.