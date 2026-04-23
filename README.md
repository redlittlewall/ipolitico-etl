# iPolitico ETL⚖️

O **iPolitico** é um motor de extração, transformação e carga (ETL) assíncrono projetado para realizar a auditoria cívica dos dados do Poder Legislativo Brasileiro. O objetivo é mitigar a assimetria informacional entre eleitos e cidadãos através de um Data Lake local robusto, imutável e auditável.

## Arquitetura e Diferenciais

O projeto foi construído sob princípios de **Engenharia de Dados moderna**, focando em resiliência contra as instabilidades das APIs governamentais:

* **Processamento de Alta Performance:** Utiliza [Polars](https://pola.rs/) e Apache Arrow para manipulação de dados em memória.
* **Resiliência (Backoff & Throttling):** Cliente HTTP assíncrono com defesas contra erros silenciosos (HTTP 200 com corpo vazio) e limites de taxa (429/503).
* **Carga Incremental:** Lógica de *Watermarking* que detecta o último registro no banco e sincroniza apenas os dados novos.

## Stack Tecnológica

- **Linguagem:** Python 3.12+
- **Processamento:** Polars (Rust-backed DataFrames)
- **Networking:** HTTPX (Async)
- **Qualidade:** Ruff (Linter/Formatter) & Pytest (TDD)
- **Banco de Dados:** SQLite (padrão) / Suporte extensível para DuckDB

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

## Execução

Para iniciar a sincronização completa (Deputados, Despesas, Proposições e Votações):
```bash
python -m ipolitico.main
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