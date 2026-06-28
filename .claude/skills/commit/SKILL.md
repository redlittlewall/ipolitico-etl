---
name: commit
description: Stage, test, generate commit message from diff, commit, and push. Use after /qa or after any implementation cycle.
---

# Commit Skill — `/commit`

Stage → test → commit message → push. **No agent delegations.**

## Flow

```
1. git status --short → mostra escopo pro usuário
2. git add -A         (ou staging manual se preferir)
3. python -m pytest -q → ❌ aborta se falhar
4. Gera mensagem de commit do diff:
   <type>(<scope>): <summary>

   <body>
   
   Tipos: feat | fix | refactor | test | docs | chore
5. git commit (pre-commit hook roda)
   ├── auto-fix → re-add → re-tenta
   └── falha real → aborta
6. git push
7. Se branch não for main → pergunta PR (opcional)
```

## Regras

- **Nunca commit com testes falhando** — aborta
- **Mensagem em conventional commits**, inferida do diff
- **Sem Co-Authored-By**
- **Push simples** — sem merge, sem squash

## Exemplo

```
/commit
  → 📋 Escopo: 5 arquivos (src/..., tests/...)
  → pytest -q: 231 passed ✅
  → git commit -m "feat(bulk): 3 dominios bulk-only"
  → git push
  → PR? (s/N)
```
