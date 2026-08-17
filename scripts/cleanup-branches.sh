#!/usr/bin/env bash
set -euo pipefail

echo "=== 1. Delete local branch ==="
git branch -D feat/senado-integracao 2>&1 || echo "(already deleted locally)"

echo ""
echo "=== 2. Delete remote branch ==="
git push origin --delete feat/senado-integracao 2>&1 || echo "(already deleted remotely)"

echo ""
echo "=== 3. Create feat/docker-setup from feat/senado-api ==="
git checkout feat/senado-api
git checkout -b feat/docker-setup

echo ""
echo "=== 4. Push new branch ==="
git push origin feat/docker-setup

echo ""
echo "=== 5. Final branches ==="
git branch --list
