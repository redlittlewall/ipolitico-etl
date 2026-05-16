#!/usr/bin/env bash
# Smoke local: sanity-check imports e ajuda da CLI (sem ingestão real).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT/src"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

"$PY" -c "import ipolitico.main; import ipolitico.pipeline.manager"
"$PY" -m ipolitico.main --help
