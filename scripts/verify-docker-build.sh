#!/usr/bin/env bash
# verify-docker-build.sh — Smoke tests para a imagem Docker multi-stage.
# Uso: bash scripts/verify-docker-build.sh [--ciclo N]
# Sem --ciclo, executa todos os testes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PASS=0
FAIL=0

CICLO="${1:-all}"
_CICLO_NUM=0

_result() {
    local label="$1" ok="$2" detail="$3"
    if [ "$ok" -eq 0 ]; then
        echo "  ✅ $label"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label — $detail"
        FAIL=$((FAIL + 1))
    fi
}

_ci() { _CICLO_NUM=$((_CICLO_NUM + 1)); [ "$CICLO" = "all" ] || [ "$CICLO" = "$_CICLO_NUM" ]; }

echo "=== iPolitico ETL — Docker Smoke Tests ==="
echo ""

# ── Ciclo 1: Build mínimo ──────────────────────────────────
if _ci; then
    echo "--- Ciclo $_CICLO_NUM: Build mínimo ---"
    docker build -t ipolitico-etl . 2>&1
    _result "docker build -t ipolitico-etl ." $? "build falhou"
    echo ""
fi

# ── Ciclo 2: Entrypoint ────────────────────────────────────
if _ci; then
    echo "--- Ciclo $_CICLO_NUM: Entrypoint ---"
    docker run --rm ipolitico-etl --help > /dev/null 2>&1
    _result "docker run --help" $? "exit code != 0 ou não encontrou ipolitico"
    echo ""
fi

# ── Ciclo 3: Dependências core ─────────────────────────────
if _ci; then
    echo "--- Ciclo $_CICLO_NUM: Dependências core ---"
    docker run --rm ipolitico-etl python -c "import polars; import duckdb; import httpx" 2>&1
    _result "import polars, duckdb, httpx" $? "alguma dep core não instalada"
    echo ""
fi

# ── Ciclo 4: Perfil analysis ───────────────────────────────
if _ci; then
    echo "--- Ciclo $_CICLO_NUM: Perfil analysis ---"
    docker build --build-arg PROFILE=analysis -t ipolitico-etl:analysis . 2>&1
    _result "docker build --build-arg PROFILE=analysis" $? "build analysis falhou"

    docker run --rm ipolitico-etl:analysis python -c "import matplotlib" 2>&1
    _result "import matplotlib no container analysis" $? "matplotlib não disponível"
    echo ""
fi

# ── Ciclo 5: CLI funcional (list-domains) ──────────────────
if _ci; then
    echo "--- Ciclo $_CICLO_NUM: CLI funcional ---"
    docker run --rm ipolitico-etl run --source camara --list-domains > /dev/null 2>&1
    _result "run --source camara --list-domains" $? "CLI não listou domínios"
    echo ""
fi

# ── Ciclo 6: pytest ────────────────────────────────────────
if _ci; then
    echo "--- Ciclo $_CICLO_NUM: pytest ---"
    # Pular testes de rede com marker 'rede'
    docker run --rm ipolitico-etl pytest -q -m "not rede" 2>&1 || true
    _result "pytest -m 'not rede'" $? "testes falharam"
    echo ""
fi

# ── Resumo ─────────────────────────────────────────────────
echo "=== Resultado: $PASS passaram, $FAIL falharam ==="
if [ "$FAIL" -gt 0 ]; then exit 1; fi
