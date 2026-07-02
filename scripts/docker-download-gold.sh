#!/usr/bin/env bash
# docker-download-gold.sh — Baixa dados Gold da última release do GitHub
#
# Uso:
#   docker-download-gold.sh                      # Baixa e extrai dados Gold
#   docker-download-gold.sh --dry-run             # Mostra URL sem baixar
#   docker-download-gold.sh --source-dir /caminho # Usa diretório local (offline)
#   docker-download-gold.sh --help                # Mostra esta mensagem
#
# A saída é extraída em data/datalake/gold/ (padrão) ou no diretório especificado

set -euo pipefail

REPO="redlittlewall/ipolitico-etl"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"
ASSET_PATTERN="gold-*.tar.gz"
OUTPUT_DIR="data/datalake/gold"
DRY_RUN=false
SOURCE_DIR=""

show_help() {
    cat <<EOF
Uso: $(basename "$0") [opções]

Baixa os dados Gold da última release do GitHub e extrai em data/datalake/gold/.

Opções:
  --dry-run             Apenas mostra a URL da release sem baixar
  --source-dir DIR      Usa diretório local em vez de baixar do GitHub
  --help                Mostra esta mensagem de ajuda

Exemplos:
  $(basename "$0")
  $(basename "$0") --dry-run
  $(basename "$0") --source-dir /tmp/meus-dados
EOF
    exit 0
}

# Parse argumentos
while [ $# -gt 0 ]; do
    case "$1" in
        --help)
            show_help
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --source-dir)
            if [ -z "${2:-}" ]; then
                echo "Erro: --source-dir requer um diretório como argumento" >&2
                exit 1
            fi
            SOURCE_DIR="$2"
            shift 2
            ;;
        *)
            echo "Erro: argumento desconhecido: $1" >&2
            echo "Use --help para ver as opções disponíveis." >&2
            exit 1
            ;;
    esac
done

# Modo --source-dir: copia dados de diretório local
if [ -n "$SOURCE_DIR" ]; then
    if [ ! -d "$SOURCE_DIR" ]; then
        echo "Erro: diretório não encontrado: $SOURCE_DIR" >&2
        exit 1
    fi

    echo "Usando diretório local: $SOURCE_DIR"
    mkdir -p "$OUTPUT_DIR"

    # Copia arquivos parquet recursivamente
    COUNT=$(find "$SOURCE_DIR" -name "*.parquet" 2>/dev/null | wc -l) || true
    if [ "$COUNT" -eq 0 ]; then
        echo "Aviso: nenhum arquivo .parquet encontrado em $SOURCE_DIR." >&2
    else
        echo "Copiando $COUNT arquivos parquet..."
        find "$SOURCE_DIR" -name "*.parquet" -exec cp {} "$OUTPUT_DIR/" \; 2>/dev/null || true
    fi

    echo "Pronto! Dados extraídos em: $OUTPUT_DIR"
    exit 0
fi

# Modo --dry-run: mostra informações da release sem baixar
if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] Repositório: $REPO"
    echo "[dry-run] URL da API: $API_URL"
    echo "[dry-run] Padrão de asset: $ASSET_PATTERN"
    echo "[dry-run] Diretório de saída: $OUTPUT_DIR"

    # Tenta obter a URL da última release (sem baixar o asset)
    if command -v curl &>/dev/null; then
        RELEASE_URL=$(curl -sL --connect-timeout 5 "$API_URL" 2>/dev/null \
            | grep -oP '"browser_download_url":\s*"\K[^"]+' \
            | grep -i "gold" || true)
        if [ -n "$RELEASE_URL" ]; then
            echo "[dry-run] Asset encontrado: $RELEASE_URL"
        else
            echo "[dry-run] Nenhum asset gold encontrado na última release."
            echo "[dry-run] (Isso é normal se ainda não houver uma release com dados Gold.)"
        fi
    else
        echo "[dry-run] curl não disponível — não foi possível verificar a release."
    fi
    exit 0
fi

# Modo normal: baixa e extrai dados
echo "Baixando dados Gold da última release de $REPO..."

if ! command -v curl &>/dev/null; then
    echo "Erro: curl não encontrado. Instale curl ou use --source-dir." >&2
    exit 1
fi

# Obtém URL do asset
ASSET_URL=$(curl -sL --connect-timeout 10 "$API_URL" 2>/dev/null \
    | grep -oP '"browser_download_url":\s*"\K[^"]+' \
    | grep -i "gold" || echo "")

if [ -z "$ASSET_URL" ]; then
    echo "Erro: não foi possível encontrar um asset gold na última release." >&2
    echo "Verifique se há uma release em: https://github.com/$REPO/releases" >&2
    exit 1
fi

echo "Baixando: $ASSET_URL"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# Baixa o tarball
TARBALL="$TMP_DIR/gold-asset.tar.gz"
if ! curl -sL --connect-timeout 30 --retry 3 -o "$TARBALL" "$ASSET_URL"; then
    echo "Erro: falha ao baixar o asset." >&2
    exit 1
fi

# Extrai
mkdir -p "$OUTPUT_DIR"
if ! tar -xzf "$TARBALL" -C "$OUTPUT_DIR" --strip-components=1 2>/dev/null; then
    # Tenta sem --strip-components se falhar
    tar -xzf "$TARBALL" -C "$OUTPUT_DIR" 2>/dev/null || {
        echo "Erro: falha ao extrair o tarball." >&2
        exit 1
    }
fi

echo "Pronto! Dados Gold extraídos em: $OUTPUT_DIR"
