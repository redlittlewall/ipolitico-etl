---
name: qa
description: Quality assurance gate after implementation. Runs automated checks, captures session findings, triages everything (fixes small inline, documents big as issues), and optionally delegates to code-review/verify/security-review before /commit.
---

# QA Skill — `/qa`

Quality assurance gate executada **depois do `/tdd`** e **antes do `/commit`**.

```
/tdd <tarefa>
  ↓  implementa + testa
/qa
  ↓  verifica qualidade, captura achados, tria
/commit
  ↓  empacota e publica
```

## Filosofia

- **Automático primeiro**: o que pode rodar AFK, roda
- **Achado pequeno → corrijo agora**: typo, debug leftover, docstring ausente
- **Achado grande → vira issue**: bug estrutural, dívida técnica, planejamento
- **Mínima fricção**: você aprova ou rejeita cada passo interativo
- **Captura proativa**: pergunta o que surgiu DURANTE a execução (TDD, descobertas)

---

## Fluxo completo

### FASE 0 — Captura de achados da sessão

**Antes de rodar qualquer scan automático**, pergunte ao usuário:

```
? Teve algum achado durante esta execução?
  (bug, dívida técnica, mudança de design, descoberta importante)

  Tipos:
    • Bug          — algo que está errado e precisa de correção
    • Tech debt    — algo funcional mas que deveria ser melhorado
    • Architecture — decisão estrutural que afeta o futuro
    • Design change — pivot, novo requisito, descoberta
```

Se o usuário relatar algo, **documente como issue** seguindo o template em
`docs/agents/finding-template.md`:

```
Status: needs-triage
Date: <hoje>
Area: <domínio>
Severity: <low|medium|high>
Source: <skill-ou-origem>
Type: <bug|tech-debt|architecture|design-change|discovery>
```

Os issues vão para `.scratch/qa-<data-hora>/issues/`.

Se o usuário disser que não, siga para Fase 1.

### FASE 1 — Verificações automáticas (AFK-safe)

Tudo isso roda sem sua interação:

```
1. pytest -q
   ├── ok → ✅
   └── falha → ❌ ABORTA (testes precisam passar primeiro)

2. pre-commit run --all-files
   ├── ok → ✅
   └── falha com auto-fix → re-tenta
       └── falha real → ❌ ABORTA

3. Scan de docstrings
   ├── arquivos tocados no diff
   └── verifica classes/funções novas ou alteradas sem docstring
       (segundo regras do CLAUDE.md)

4. Scan de debug leftovers
   ├── `print(`, `import pdb`, `breakpoint()`, `import ipdb`
   ├── `TODO:` / `FIXME:` / `HACK:` / `XXX:` sem issue referenciada
   └── blocos de código comentado (>3 linhas consecutivas)

5. Scan de arquivos esquecidos
   ├── `__pycache__/`, `*.pyc`, `.DS_Store`, `*.swp`
   └── arquivos temporários no working tree

6. Scan de imports órfãos
   ├── imports que podem estar sobrando (uso de `from X import Y` sem Y usado)
   └── `__init__.py` faltando em pacotes novos

── Relatório FASE 1 ──────────────────────────
  ✅ pytest: 208 passed
  ✅ pre-commit: limpo
  ⚠ docstrings: 2 funções sem docstring (detalhe abaixo)
  ✅ debug leftovers: nenhum
  ✅ arquivos esquecidos: nenhum
  ✅ imports: ok
──────────────────────────────────────────────
```

### FASE 2 — Triage dos achados

Para cada achado da Fase 0 + Fase 1 + Fase 3:

| Critério | Ação |
|----------|------|
| **1-5 linhas**, risco baixo | Corrige inline (sem perguntar) |
| **>5 linhas** ou risco médio | Pergunta: "Corrigir agora ou documentar como issue?" |
| **Bug**, decisão arquitetural, dívida estrutural | Cria issue em `.scratch/qa-<data-hora>/issues/` |
| **Findings da Fase 0** (relatados pelo usuário) | Sempre virar issue |

Os issues seguem este formato (veja `docs/agents/finding-template.md` para
detalhes e exemplos):

```markdown
---
Status: needs-triage
Date: 2026-06-04
Area: <domain>
Severity: low | medium | high
Source: qa-skill
Type: bug | tech-debt | architecture | design-change | discovery
---

# <título conciso>

## Finding

Descrição clara do que foi encontrado.

## Impact

Por que isso importa — o que pode acontecer se não for resolvido.

## Suggested fix

Como resolver (pode ser referência a uma issue pai se for muito grande).

## Location

Arquivos e linhas relevantes.
```

### FASE 3 — Revisões interativas (opcional)

Pergunta uma a uma, você decide:

```
? Rodar /code-review (effort: medium)? (s/N)
  ├── s → revisão semântica do diff
  │     ├── achados pequenos → corrige inline
  │     └── achados grandes → cria issue
  └── n → pula

? Rodar /verify? (s/N)
  ├── s → smoke test da app
  └── n → pula

? Rodar /security-review? (s/N)
  ├── s → varre segurança
  └── n → pula
```

### FASE 4 — Encaminhamento

```
? Issues criadas em .scratch/qa-<data-hora>/
  ├── "Revisar issues antes de commitar? (s/N)"
  │   ├── s → mostra resumo de cada issue
  │   └── n → segue

? Partir para /commit agora? (s/N)
  ├── s → delega para /commit
  └── n → "OK. Issues em .scratch/qa-<data-hora>/"
```

---

## Regras de comportamento

### Docstring scan

Usa a definição do `CLAUDE.md`:

> Toda classe ou função **criada ou alterada** DEVE ter docstring padrão com:
> 1. O que é/comportamento central
> 2. Inputs/Args
> 3. Outputs/Returns

O scan verifica funções/classes nos arquivos tocados pelo `git diff --cached`.
Se a função não tiver docstring (ou a docstring estiver desatualizada), reporta.

O scan usa `ast` para detectar corpos de função/classe — não é regex frágil.

### Debug leftovers

- `print(` com argumento (exclui `print()`) — potencial debug leftover
- `import pdb`, `import ipdb`, `import pudb`, `breakpoint()`
- `TODO:`, `FIXME:`, `HACK:`, `XXX:` — considera achado se não tiver `(#issue N)` ou link
- Blocos de 3+ linhas comentadas consecutivas (`# ` em sequência)

### Importação de issues

Quando um issue é grande ou impacta múltiplos domínios, adicionar no cabeçalho:

```
## Blocked by

N/A

## Parent

[PRD: QA findings <data>](../PRD.md)
```

### Output final

A skill sempre imprime um resumo no final:

```
┌─────────────────────────────────────────────────────────────┐
│                     QA Report — 2026-06-04                  │
├─────────────────────────────────────────────────────────────┤
│ FASE 0 — Achados da sessão                                  │
│   📋 "Bug de paginação em /deputados" → issue criado       │
│                                                              │
│ FASE 1 — Automático                                         │
│   ✅ pytest: 208 passed                                     │
│   ✅ pre-commit: limpo                                       │
│   ⚠ docstrings: 2 pendentes (corrigido inline)              │
│   ✅ debug leftovers: nenhum                                 │
│                                                              │
│ FASE 3 — Revisões                                            │
│   ✅ /code-review: nenhum achado                             │
│   ☐ /verify: pulado                                         │
│                                                              │
│ Achados documentados como issues:                            │
│   📋 .scratch/qa-20260604-153000/issues/01-paginacao.md     │
│                                                              │
│ Resultado: ✅ Pode commitar                                  │
└─────────────────────────────────────────────────────────────┘
```
