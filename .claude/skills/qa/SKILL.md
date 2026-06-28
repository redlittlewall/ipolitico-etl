---
name: qa
description: Pre-commit quality checks — pytest, pre-commit, debug leftovers scan. Quick, no agent delegations.
---

# QA Skill — `/qa`

Quick quality checks before `/commit`. **No agent delegations** (no code-review, no security-review).

## Flow

### 1. Ask user
```
? Teve algum achado durante a execução que queira documentar? (s/N)
```
If yes, create issue in `.scratch/qa-<data>/`. If no, proceed.

### 2. Automated checks (all local, fast)

```
1. python -m pytest -q      → ❌ aborta se falhar
2. pre-commit run --all-files → auto-fix → re-add → re-try
3. Scan debug leftovers:
   - print(, import pdb, breakpoint()
   - TODO/FIXME/HACK/XXX sem issue link
   - 3+ linhas comentadas consecutivas
```

### 3. Triage

| Tamanho | Ação |
|---------|------|
| ≤5 linhas, baixo risco | Corrige inline |
| >5 linhas ou médio risco | Pergunta: corrigir agora ou documentar? |
| Bug/dívida estrutural | Cria issue |

### 4. Output

```
┌──────────────────────────────────────┐
│ QA Report — <data>                  │
├──────────────────────────────────────┤
│ ✅ pytest: N passed                  │
│ ✅ pre-commit: limpo                 │
│ ✅ debug leftovers: nenhum           │
│                                      │
│ Issues: .scratch/qa-<data>/          │
│                                      │
│ Resultado: ✅ Pode commitar          │
└──────────────────────────────────────┘
```
