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
O orquestrador é totalmente parametrizável. Você pode escolher a origem dos dados (--source), o destino (--sink), a estratégia (--strategy) e os limites temporais.

1. Atualização Diária (Incremental via API)

Ideal para rodar via cron todos os dias. Lê a última data do banco e puxa apenas o que falta:
```bash
python -m ipolitico.main --source api --sink sqlite --strategy incremental
```

2. Criação do Data Lake Histórico (Bulk Load)

Ideal para criar o banco analítico inicial. Baixa os "Dumps" CSV do governo e converte para Parquet particionado:
```bash
python -m ipolitico.main --source bulk --sink datalake --strategy full_load --start-date 2023-01-01 --end-date 2023-12-31
```

## Testes
Garantimos a integridade do pipeline através de testes de integração com mocks de API:
```bash
pytest
```

## Contribuição

Contribuições que visam a transparência pública são bem-vindas.

1. Faça um fork do projeto.

2. Crie uma branch para sua feature (git checkout -b feature/nova-api).

3. Certifique-se de que o ruff não aponta erros de estilo.

4. Abra um Pull Request.