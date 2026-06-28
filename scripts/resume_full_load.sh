#!/usr/bin/env bash
# Resumo: Retoma execução ETL interrompida, otimiza Gold e roda domínios faltantes
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"

SILVER_ONLY_DOMAINS=(
    proposicoes tramitacoes autores relacionadas temas votacoes
)

MISSING_DOMAINS=(
    proposicoes_votacoes discursos orgaos_votacoes partidos_lideres
    votacoes_detalhe votos orientacoes referencias proposicoes_detalhe
)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  iPolitico ETL — Retomada de Execução                       ║"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')                               ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ─────────────────────────────────────────────────────────────
# Passo 1: Otimizar Silver → Gold para domínios já completos
# ─────────────────────────────────────────────────────────────
echo ""
echo "▸ Passo 1/3 — Otimizando Silver → Gold para 6 domínios..."
START_OPTIMIZE=$(date +%s)

python3 -c "
import asyncio
import time
from ipolitico.pipeline.optimizer import DataLakeOptimizer

domains = ${SILVER_ONLY_DOMAINS[@]/#/\"}
domains = [d for d in ['proposicoes', 'tramitacoes', 'autores', 'relacionadas', 'temas', 'votacoes']]

start = time.perf_counter()
for domain in domains:
    ts = time.perf_counter()
    print(f'  → Otimizando {domain}...', end=' ', flush=True)
    try:
        DataLakeOptimizer().compact_and_deduplicate(domain)
        print(f'OK ({time.perf_counter()-ts:.1f}s)')
    except Exception as e:
        print(f'ERRO: {e}')

total = time.perf_counter() - start
print(f'  Gold otimizada em {total:.1f}s')
print(f'OPTIMIZE_TIME={total:.0f}')
" 2>&1 | tee /tmp/optimize_log.txt

OPTIMIZE_TIME=$(grep 'OPTIMIZE_TIME=' /tmp/optimize_log.txt | tail -1 | cut -d= -f2)
echo "  ✔ Passo 1 concluído em ${OPTIMIZE_TIME}s"
echo ""

# ─────────────────────────────────────────────────────────────
# Passo 2: Executar ETL para domínios faltantes
# ─────────────────────────────────────────────────────────────
echo "▸ Passo 2/3 — Extraindo domínios nunca extraídos..."
START_EXTRACT=$(date +%s)

python3 -m ipolitico.main \
    --strategy FULL_LOAD \
    --domains proposicoes_votacoes discursos orgaos_votacoes partidos_lideres \
    --domains votacoes_detalhe votos orientacoes referencias proposicoes_detalhe 2>&1 | \
    tee /tmp/extract_log.txt

EXTRACT_EXIT=${PIPESTATUS[0]}
EXTRACT_TIME=$(($(date +%s) - START_EXTRACT))

if [ $EXTRACT_EXIT -ne 0 ]; then
    echo "  ⚠ ETL retornou código $EXTRACT_EXIT — alguns domínios podem ter falhado"
fi
echo "  ✔ Passo 2 concluído em ${EXTRACT_TIME}s"
echo ""

# ─────────────────────────────────────────────────────────────
# Passo 3: Otimizar Gold para os novos domínios
# ─────────────────────────────────────────────────────────────
echo "▸ Passo 3/3 — Otimizando Gold para novos domínios..."
START_OPTIMIZE2=$(date +%s)

python3 -c "
import time
from ipolitico.pipeline.optimizer import DataLakeOptimizer

new_domains = ['proposicoes_votacoes', 'discursos', 'orgaos_votacoes', 'partidos_lideres',
               'votacoes_detalhe', 'votos', 'orientacoes', 'referencias', 'proposicoes_detalhe']

start = time.perf_counter()
for domain in new_domains:
    ts = time.perf_counter()
    print(f'  → Otimizando {domain}...', end=' ', flush=True)
    try:
        DataLakeOptimizer().compact_and_deduplicate(domain)
        print(f'OK ({time.perf_counter()-ts:.1f}s)')
    except Exception as e:
        print(f'ERRO: {e}')

total = time.perf_counter() - start
print(f'  Gold otimizada em {total:.1f}s')
print(f'OPTIMIZE2_TIME={total:.0f}')
"

OPTIMIZE2_TIME=$(($(date +%s) - START_OPTIMIZE2))
echo "  ✔ Passo 3 concluído em ${OPTIMIZE2_TIME}s"

# ─────────────────────────────────────────────────────────────
# Resumo Final
# ─────────────────────────────────────────────────────────────
TOTAL_TIME=$((OPTIMIZE_TIME + EXTRACT_TIME + OPTIMIZE2_TIME))
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  RESUMO DA RETOMADA                                         ║"
echo "║  Otimizar Gold pré-existente:  ${OPTIMIZE_TIME}s            ║"
echo "║  Extrair domínios faltantes:   ${EXTRACT_TIME}s             ║"
echo "║  Otimizar Gold novos:          ${OPTIMIZE2_TIME}s           ║"
echo "║  ─────────────────────────────────────────                  ║"
echo "║  TOTAL:                         ${TOTAL_TIME}s              ║"
echo "║  Hora de término:              $(date '+%Y-%m-%d %H:%M:%S') ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Audit final
echo ""
echo "▸ Auditoria de cobertura final:"
python3 -m ipolitico.main --audit-coverage 2>&1

echo ""
echo "✔ Retomada concluída!"
