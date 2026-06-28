#!/usr/bin/env bash
# ==============================================================================
# scripts/release.sh — Primeira Release Oficial do iPolitico ETL
# ==============================================================================
# Uso:  bash scripts/release.sh
# Pré-requisitos: gh CLI autenticado (gh auth status), pipeline incremental
#                 finalizada com --optimize.
#
# O que faz:
#   1. Verifica se o Gold tem dados
#   2. Empacota camada Gold em gold.tar.gz
#   3. Sobe como Release v1.0.0 no GitHub
#   4. Cria tag "latest" apontando pra mesma release
# ==============================================================================

set -euo pipefail

# ── Cores ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[ATENÇÃO]${NC} $1"; }
err()   { echo -e "${RED}[ERRO]${NC}  $1"; exit 1; }

# ── 1. Verifica pré-requisitos ────────────────────────────────────────────────
info "Verificando pré-requisitos..."

command -v gh >/dev/null 2>&1 || err "gh CLI não encontrada. Instale: https://cli.github.com/"
command -v tar >/dev/null 2>&1 || err "tar não encontrado"

gh auth status 2>&1 | grep -q "Logged in" || err "gh não autenticado. Rode: gh auth login"

cd "$(git rev-parse --show-toplevel)"
info "Repositório: $(git remote get-url origin)"

# ── 2. Verifica Gold ──────────────────────────────────────────────────────────
GOLD_DIR="data/datalake/gold"
if [ ! -d "$GOLD_DIR" ]; then
    err "Diretório $GOLD_DIR não encontrado. Execute o pipeline primeiro."
fi

GOLD_COUNT=$(find "$GOLD_DIR" -name "*.parquet" | wc -l)
if [ "$GOLD_COUNT" -eq 0 ]; then
    err "Nenhum arquivo .parquet encontrado em $GOLD_DIR. Execute o pipeline com --optimize."
fi
ok "$GOLD_COUNT arquivos Parquet encontrados na camada Gold"

# ── 3. Última execução do pipeline ─────────────────────────────────────────────
LAST_LOG=$(find . -name "ipolitico_etl.log" -newer "$GOLD_DIR" -type f 2>/dev/null | head -1)
if [ -n "$LAST_LOG" ]; then
    DURATION=$(grep -oP 'Tempo total de execução: \K[0-9.]+' "$LAST_LOG" | tail -1)
    [ -n "$DURATION" ] && info "Última execução: ${DURATION}s" || warn "Não foi possível ler duração do log"
fi

# ── 4. Verifica se git está limpo (opcional) ───────────────────────────────────
if [ -n "$(git status --porcelain)" ]; then
    warn "Há alterações não commitadas no repositório."
    echo "    Recomendado: faça commit antes da release (v1.0.0)."
    echo -n "    Continuar mesmo assim? [s/N] "
    read -r answer
    [ "$answer" != "s" ] && [ "$answer" != "S" ] && err "Release cancelada."
fi

# ── 5. Verifica se é o primeiro commit do release (ou já existe tag) ───────────
if git rev-parse "v1.0.0" >/dev/null 2>&1; then
    warn "Tag v1.0.0 já existe localmente."
    echo -n "    Sobrescrever? A release existente será deletada. [s/N] "
    read -r answer
    [ "$answer" != "s" ] && [ "$answer" != "S" ] && err "Release cancelada."
    git tag -d v1.0.0
    git push origin :refs/tags/v1.0.0 2>/dev/null || true
    gh release delete v1.0.0 --yes 2>/dev/null || true
fi
if git rev-parse "latest" >/dev/null 2>&1; then
    git tag -d latest 2>/dev/null || true
    git push origin :refs/tags/latest 2>/dev/null || true
fi
gh release delete latest --yes 2>/dev/null || true

# ── 6. Empacota Gold ───────────────────────────────────────────────────────────
GOLD_ARCHIVE="gold-$(date +%Y%m%d).tar.gz"
info "Empacotando Gold → $GOLD_ARCHIVE ..."

cd data/datalake
tar czf "../../$GOLD_ARCHIVE" gold/
cd ../..

SIZE=$(du -sh "$GOLD_ARCHIVE" | cut -f1)
ok "$GOLD_ARCHIVE gerado ($SIZE)"

# ── 7. Cria Release v1.0.0 ────────────────────────────────────────────────────
info "Criando release v1.0.0 no GitHub..."

# Gera notas da release
RELEASE_NOTES=$(cat <<-EOF
## iPolitico ETL v1.0.0 — "Deputados"

Primeira release oficial do iPolitico ETL. Cobertura **100%** da API de Dados
Abertos da Câmara dos Deputados (64/64 domínios).

### 📦 Dados incluídos

| Categoria | Domínios | Registros |
|---|---|---|
| Deputados | deputados, historico, detalhe, etc. | ~11.169 |
| Despesas CEAP | despesas | ~1.427.511 |
| Proposições | proposicoes, autores, tramitacoes, etc. | ~14.907 |
| Votações | votacoes, votos, orientacoes | ~485.747 |
| Eventos | eventos, deputados, pauta, orgaos | ~58.930 |
| Partidos/Blocos/Frentes | 9 domínios | ~1.721 |
| Licitações | 5 domínios | ~125.636 |
| **Total Gold** | **64 domínios** | **~7,3 milhões** |

### 🚀 Como usar

\`\`\`bash
wget https://github.com/redlittlewall/ipolitico-etl/releases/latest/download/gold.tar.gz
tar xzf gold.tar.gz
# → gold/ com 1 .parquet por domínio
\`\`\`

### 🔧 Stack

- Python 3.12+ · Polars · HTTPX · DuckDB · GitHub Actions
- Arquitetura Medallion (Bronze → Silver → Gold)
- Incremental automático semanal via CI
- Append-only + dedup na Gold

### 📜 Licença

MIT — dados públicos, código aberto.
EOF
)

gh release create v1.0.0 \
    --title "iPolitico ETL v1.0.0 — Deputados" \
    --notes "$RELEASE_NOTES" \
    --target "$(git rev-parse HEAD)" \
    "$GOLD_ARCHIVE" || err "Falha ao criar release v1.0.0"

ok "Release v1.0.0 criada com sucesso!"

# ── 8. Cria tag "latest" ──────────────────────────────────────────────────────
info "Criando tag 'latest' (aponta para v1.0.0)..."

gh release create latest \
    --title "Última versão estável" \
    --notes "Release apontada para a versão mais recente dos dados. Use esta URL para downloads automáticos." \
    --target "$(git rev-parse HEAD)" \
    "$GOLD_ARCHIVE" --clobber 2>/dev/null || \
    gh release upload latest "$GOLD_ARCHIVE" --clobber 2>/dev/null

ok "Tag 'latest' criada. Links:"
echo ""
echo "    📥 Download:"
echo "      https://github.com/redlittlewall/ipolitico-etl/releases/latest/download/gold.tar.gz"
echo ""
echo "    🌐 Release:"
echo "      https://github.com/redlittlewall/ipolitico-etl/releases/tag/v1.0.0"
echo ""

# ── 9. Limpeza ────────────────────────────────────────────────────────────────
rm -f "$GOLD_ARCHIVE"
ok "Release finalizada! 🎉"
