---
name: commit
description: Commit and push changes with proper message, pre-commit handling, and optional PR creation. Use after /tdd finishes or after any implementation cycle.
---

# Commit Skill — `/commit`

Automatiza o ritual de commit + push após finalizar uma tarefa. Cobre todo o
ciclo: staging, testes, pre-commit, mensagem convencional, push e PR opcional.

## Quando usar

- **Sempre depois do `/tdd`** — após o último GRN refactor, chame `/commit`
- Depois de qualquer alteração manual no código que você queira commitar
- Depois de refatorações ou correções rápidas

## Fluxo

```
/git add -A
/pytest -q (se falhar → aborta)
/git commit (pre-commit roda como hook)
  ├── se pre-commit auto-fixar → git add -A + git commit (re-tenta)
  └── se pre-commit falhar de verdade → aborta
/git push
└── se branch não for main → pergunta: "Quer abrir um PR?"
    ├── sim → gh pr create (título = mensagem, corpo = detalhes)
    └── não → pronto
```

## Regras

### Staging

- `git add -A` sempre — não pergunta o que stagear
- Se não houver mudanças, avisa e termina

### Testes

- `python -m pytest -q` antes de qualquer commit
- Se falhar, aborta imediatamente e mostra o erro

### Pre-commit hook

- O hook `git commit` roda `ruff --fix` e `ruff-format`
- Se o hook auto-corrigir arquivos, o commit falha — a skill **readiciona**
  os arquivos modificados e **re-tenta o commit com a mesma mensagem**
- Se o hook falhar por erro real (lint não corrigível), aborta

### Mensagem de commit

Formato **conventional commits**, inferida do diff:

```
<type>(<scope>): <summary>

<corpo> (opcional, extraído do diff)
```

O tipo é inferido do que o diff contém:

| Tipo | Quando usar |
|------|-------------|
| `feat` | Novas funcionalidades (extratores, transformers, domínios) |
| `fix` | Correção de bug |
| `refactor` | Mudança na estrutura sem mudar comportamento |
| `test` | Só testes novos |
| `docs` | Só documentação |
| `chore` | Config, CI, build |

O **scope** é a área de domínio mais afetada (ex: `detalhe`, `bulk`, `pipeline`,
`core`). Se tocar múltiplas áreas igualmente, omite o escopo.

**Sem `Co-Authored-By`** no rodapé.

### PR (opcional)

- Só pergunta se a branch **não** for `main`
- Usa `gh pr create --title <título> --body <corpo>`
- O corpo do PR é montado a partir da descrição detalhada do commit
- Se o usuário recusar, apenas push

## Comportamento detalhado

### 1. Verificação inicial

```python
1. git status --porcelain → lista mudanças
2. Se vazio → "Nada para commitar." → sai
```

### 2. Staging e teste

```python
1. git add -A
2. python -m pytest -q
   ├── ok → continua
   └── falha → "Testes falhando. Abortando." → mostra output → sai (exit 1)
```

### 3. Commit com retry de pre-commit

```python
1. Monta mensagem de commit a partir do diff
2. git commit -m "<mensagem>"
   ├── retcode 0 → sucesso → continua
   ├── retcode != 0:
   │   git diff --name-only → verifica se é auto-fix do ruff
   │   ├── sim → git add -A + git commit -m "<mensagem>" (re-tenta 1x)
   │   └── não → mostra erro → aborta
   └── 2o retry falhar → aborta
```

### 4. Push e PR

```python
1. git push
   ├── falha → mostra erro → aborta
   └── ok → verifica branch:
       ├── main → "Commit feito e enviado." → fim
       └── feat/*, fix/* etc → "Quer abrir um PR também? (s/N)"
           ├── s → gh pr create --title "..." --body "..."
           └── n → fim
```

## Exemplo de uso

```bash
# Após finalizar uma tarefa com /tdd
/commit

# A skill vai:
#   git add -A
#   pytest -q
#   git commit -m "feat(detalhe): blocos_detalhe e proposicoes_detalhe"
#   (se ruff auto-fixar, re-tenta)
#   git push
#   "Branch feat/foo não é main. Quer abrir um PR? (s/N)"
```

## Limitações conhecidas

- **Não lida com conflitos de merge** — se o push falhar por divergência,
  a skill aborta e você resolve manualmente
- **Não edita mensagens** — se você quiser ajustar a mensagem, cancele a skill
  e commite manualmente
- **Não faz squash** — commits individuais como saem do TDD
