#!/usr/bin/env bash
# docker-entrypoint.sh — Entrypoint para imagem iPolitico ETL
#
# Roteia comandos especiais para scripts auxiliares:
#   download-data → scripts/docker-download-gold.sh
#   python|pip|jupyter|bash → exec direto (scripts, análise, shell)
#   qualquer outro → ipolitico (CLI principal)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-}" in
    download-data)
        shift
        exec "$SCRIPT_DIR/docker-download-gold.sh" "$@"
        ;;
    python|pip|jupyter|bash)
        exec "$@"
        ;;
    *)
        exec ipolitico "$@"
        ;;
esac
