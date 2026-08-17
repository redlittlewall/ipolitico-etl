#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="backups/datalake.$(date +%Y%m%d_%H%M%S).pre_full_load"
echo "=== Backing up datalake to $BACKUP_DIR ==="
mkdir -p backups
cp -a data/datalake "$BACKUP_DIR"
echo "=== Backup concluído: $(du -sh "$BACKUP_DIR" | cut -f1) ==="
