ARG PROFILE=base

FROM python:3.12-slim AS base
WORKDIR /app

# Copia apenas o necessário para instalar o pacote
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/ ./scripts/

# Instala o pacote com dependências dev (inclui pytest para testes)
RUN pip install --no-cache-dir -e ".[dev]"

FROM base AS analysis
RUN pip install --no-cache-dir jupyter matplotlib seaborn

# Re-declara ARG para uso no FROM final (Docker consome ARGs globais no primeiro FROM)
ARG PROFILE
FROM ${PROFILE} AS final
# Garante que o entrypoint exista para comandos avulsos
COPY --from=base /app /app
# Copia testes para execução dentro do container
COPY tests/ ./tests/
ENTRYPOINT ["scripts/docker-entrypoint.sh"]
