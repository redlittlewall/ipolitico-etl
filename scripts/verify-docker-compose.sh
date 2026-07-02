#!/usr/bin/env bash
# Testes para docker-compose.yml — verifica build, entrypoint e comandos básicos
set -euo pipefail
FAILED=0

# Test 1: docker-compose.yml existe
echo "TEST 1: docker-compose.yml existe..."
if [ ! -f docker-compose.yml ]; then
    echo "FAIL: docker-compose.yml not found"
    exit 1
fi
echo "PASS"

# Test 2: docker compose build funciona
echo "TEST 2: docker compose build (perfil base)..."
if ! docker compose build 2>&1 | tail -5; then
    echo "FAIL: docker compose build failed"
    FAILED=1
else
    echo "PASS"
fi

# Test 3: --help retorna código 0
echo "TEST 3: docker compose run --rm etl --help..."
if ! docker compose run --rm etl --help > /dev/null 2>&1; then
    echo "FAIL: docker compose run --help failed"
    FAILED=1
else
    echo "PASS"
fi

# Test 4: --list-domains retorna lista de domínios
echo "TEST 4: docker compose run --rm etl --source camara --list-domains..."
OUTPUT=$(docker compose run --rm etl --source camara --list-domains 2>/dev/null)
if echo "$OUTPUT" | grep -q "deputados"; then
    echo "PASS"
else
    echo "FAIL: --list-domains did not list deputados"
    echo "Output: $OUTPUT"
    FAILED=1
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED ($FAILED)"
    exit 1
fi
