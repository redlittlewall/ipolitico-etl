#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Task Track — worktree tracking para /commit com escopo
# ─────────────────────────────────────────────────────────────
# Uso:
#   scripts/task-track.sh start [descrição]
#     → Cria manifest vazio para a branch atual
#     → Ex: scripts/task-track.sh start "swagger codegen"
#
#   scripts/task-track.sh add <arquivo1> [arquivo2 ...]
#     → Adiciona arquivo(s) ao manifest da branch atual
#     → Sempre roda antes de criar/editar um arquivo
#
#   scripts/task-track.sh list
#     → Lista arquivos no manifest da branch atual
#
#   scripts/task-track.sh finish
#     → Remove o manifest (limpeza pós-commit)
#
#   scripts/task-track.sh status
#     → Mostra manifest vs working tree: arquivos no manifest,
#       arquivos fora do manifest, untracked files
# ─────────────────────────────────────────────────────────────

set -euo pipefail

TRACK_DIR=".claude/task-files"
mkdir -p "$TRACK_DIR"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "detached")
MANIFEST="$TRACK_DIR/$BRANCH.json"

case "${1:-help}" in
  start)
    DESC="${2:-sem descrição}"
    cat > "$MANIFEST" <<- JSON
{
  "branch": "$BRANCH",
  "task": "$DESC",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "files": []
}
JSON
    echo "✅ Task manifest criado: $MANIFEST"
    echo "   Descrição: $DESC"
    ;;

  add)
    if [ ! -f "$MANIFEST" ]; then
      echo "❌ Nenhum manifest ativo para branch '$BRANCH'."
      echo "   Execute 'scripts/task-track.sh start' primeiro."
      exit 1
    fi
    for FILE in "${@:2}"; do
      if [ -z "$FILE" ]; then continue; fi
      # Usa python3 para adicionar ao JSON (mais robusto que sed)
      python3 -c "
import json
with open('$MANIFEST') as f:
    data = json.load(f)
if '$FILE' not in data['files']:
    data['files'].append('$FILE')
with open('$MANIFEST', 'w') as f:
    json.dump(data, f, indent=2)
"
      echo "   📎 $FILE adicionado ao manifest"
    done
    ;;

  list)
    if [ ! -f "$MANIFEST" ]; then
      echo "   (sem manifest ativo para branch '$BRANCH')"
      exit 0
    fi
    python3 -c "
import json
with open('$MANIFEST') as f:
    data = json.load(f)
print(f'📋 Manifest da branch \"{data[\"branch\"]}\"')
print(f'   Task: {data[\"task\"]}')
print(f'   Iniciado: {data[\"started_at\"]}')
print(f'   Arquivos ({len(data[\"files\"])}):')
for f in data['files']:
    print(f'     • {f}')
"
    ;;

  finish)
    if [ ! -f "$MANIFEST" ]; then
      echo "   (sem manifest ativo)"
      exit 0
    fi
    echo "🗑️  Removendo manifest: $MANIFEST"
    rm "$MANIFEST"
    ;;

  status)
    echo "═ Manifest ─────────────────────────────────"
    if [ -f "$MANIFEST" ]; then
      python3 -c "
import json
with open('$MANIFEST') as f:
    data = json.load(f)
print(f'  Branch: {data[\"branch\"]}')
print(f'  Task: {data[\"task\"]}')
print(f'  Arquivos ({len(data[\"files\"])}):')
for f in data['files']:
    print(f'    • {f}')
"
    else
      echo "  (nenhum manifest ativo)"
    fi

    echo ""
    echo "═ Working tree (git status) ────────────────"
    # Files in manifest that exist in working tree
    if [ -f "$MANIFEST" ]; then
      MANIFEST_FILES=$(python3 -c "
import json
with open('$MANIFEST') as f:
    data = json.load(f)
print(' '.join(data['files']))
")
      if [ -n "$MANIFEST_FILES" ]; then
        echo "  No manifest (modificados):"
        for f in $MANIFEST_FILES; do
          if git diff --quiet HEAD -- "$f" 2>/dev/null; then
            echo "    ✅ $f (sem alterações)"
          else
            echo "    📝 $f (modificado)"
          fi
        done
      fi
    fi

    echo ""
    echo "═ Fora do manifest ─────────────────────────"
    # Files changed in working tree but NOT in manifest
    CHANGED=$(git diff --name-only HEAD 2>/dev/null || true)
    UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null || true)
    OUTSIDE=""
    for f in $CHANGED; do
      if [ -f "$MANIFEST" ]; then
        IN_MANIFEST=$(python3 -c "
import json
with open('$MANIFEST') as f:
    data = json.load(f)
print('true' if '$f' in data['files'] else 'false')
")
        if [ "$IN_MANIFEST" = "false" ]; then
          OUTSIDE="$OUTSIDE $f"
        fi
      else
        OUTSIDE="$OUTSIDE $f"
      fi
    done
    for f in $UNTRACKED; do
      # Skip manifest files and .claude
      case "$f" in .claude/*) continue;; esac
      case "$f" in .scratch/*) continue;; esac
      OUTSIDE="$OUTSIDE $f"
    done
    if [ -n "$OUTSIDE" ]; then
      for f in $OUTSIDE; do
        echo "    ⚠️  $f"
      done
    else
      echo "  (tudo no manifest ✅)"
    fi
    ;;

  help|*)
    echo "Uso: scripts/task-track.sh <comando> [args]"
    echo ""
    echo "Comandos:"
    echo "  start [descrição]   Inicia tracking para branch atual"
    echo "  add <arquivo>...    Adiciona arquivo(s) ao manifest"
    echo "  list                Lista arquivos no manifest"
    echo "  finish              Remove o manifest (pós-commit)"
    echo "  status              Mostra manifest vs working tree"
    ;;
esac
