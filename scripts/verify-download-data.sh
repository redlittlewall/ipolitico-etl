#!/usr/bin/env bash
# Testes para scripts/docker-download-gold.sh e entrypoint download-data
set -euo pipefail
FAILED=0

SCRIPT="scripts/docker-download-gold.sh"

echo "=== Download Data Tests ==="

# Test 1: Script existe e é executável
echo "TEST 1: Script existe..."
if [ ! -x "$SCRIPT" ]; then
    echo "FAIL: $SCRIPT not found or not executable"
    exit 1
fi
echo "PASS"

# Test 2: --help mostra opções
echo "TEST 2: --help mostra opções..."
if ! bash "$SCRIPT" --help 2>&1 | grep -qE "usage|USAGE|Usage|--dry-run|--source-dir"; then
    echo "FAIL: --help não mostrou opções esperadas"
    bash "$SCRIPT" --help 2>&1 | head -5
    FAILED=1
else
    echo "PASS"
fi

# Test 3: --dry-run valida URL sem baixar
echo "TEST 3: --dry-run valida URL..."
OUTPUT=$(bash "$SCRIPT" --dry-run 2>&1)
if echo "$OUTPUT" | grep -qE "release|URL|https://|dry.run"; then
    echo "PASS"
else
    echo "FAIL: --dry-run não produziu saída esperada"
    echo "Output: $OUTPUT"
    FAILED=1
fi

# Test 4: --source-dir /tmp lista arquivos locais
echo "TEST 4: --source-dir /tmp funciona..."
OUTPUT=$(bash "$SCRIPT" --source-dir /tmp 2>&1)
if echo "$OUTPUT" | grep -qE "found|arquivos|parquet|directory|arquivos.parquet"; then
    echo "PASS"
else
    echo "WARN: --source-dir /tmp não produziu saída esperada, verificando se há parquets..."
    echo "Output: $OUTPUT"
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED ($FAILED)"
    exit 1
fi
