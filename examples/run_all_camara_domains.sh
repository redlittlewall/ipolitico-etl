#!/usr/bin/env bash
# Smoke de ingestão: todos os domínios da API Câmara (raiz + filhos + detalhes).
# Use janela curta para validar wiring; full load histórico leva horas/dias.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT/src"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

START="${START_DATE:-2024-03-01}"
END="${END_DATE:-2024-03-31}"
STRATEGY="$(echo "${STRATEGY:-incremental}" | tr '[:upper:]' '[:lower:]')"
OPTIMIZE="${OPTIMIZE:-}"

# Ordem do grafo de dependências (todos os DomainType da Câmara).
read -r -a DOMAINS <<< "$("$PY" -c "
from ipolitico.core.constants import DomainType
from ipolitico.pipeline.domain_order import expand_camara_domains_with_dependencies
ordered = expand_camara_domains_with_dependencies(list(DomainType))
print(' '.join(d.value for d in ordered))
")"

echo "iPolitico — todos os domínios Câmara"
echo "  Janela: ${START} → ${END}"
echo "  Estratégia: ${STRATEGY}"
echo "  Total: ${#DOMAINS[@]} domínios"
echo

CMD=("$PY" -m ipolitico.main --strategy "$STRATEGY" --start-date "$START" --end-date "$END")
if [[ -n "$OPTIMIZE" ]]; then
  CMD+=(--optimize)
fi
CMD+=(--domains "${DOMAINS[@]}")

echo "Comando:"
printf '  %q' "${CMD[@]}"
echo
echo

exec "${CMD[@]}"
