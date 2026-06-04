---
name: commit
description: Commit and push changes with proper message, pre-commit handling, and optional PR creation. Uses worktree tracking to scope commits to task files only. Use after /tdd finishes or after any implementation cycle.
---

# Commit Skill — `/commit`

Automatiza o ritual de commit + push após finalizar uma tarefa. Usa **worktree
tracking** (`scripts/task-track.sh`) para garantir que só arquivos da tarefa
atual sejam commitados — prevenindo contaminação entre execuções paralelas.

## Quando usar

- **Sempre depois do `/tdd`** — após o último GREEN refactor, chame `/commit`
- Depois de qualquer alteração manual no código que você queira commitar
- Depois de refatorações ou correções rápidas

## Fluxo

```
/commit
  ├── 1. Verifica manifest de tracking → scaneia escopo
  ├── 2. Staging (manifest ou manual)
  │     ├── Manifest existe → git add <arquivos do manifest>
  │     └── Sem manifest → mostra diff e pergunta o que stagear
  ├── 3. pytest -q (se falhar → aborta)
  ├── 4. git commit (pre-commit roda como hook)
  │     ├── se pre-commit auto-fixar → git add -A + git commit (re-tenta)
  │     └── se pre-commit falhar de verdade → aborta
  ├── 5. task-track.sh finish (limpa manifest)
  ├── 6. git push
  └── 7. PR opcional (se branch não for main)
```

## Regras

### 1. Verificação de escopo (worktree tracking)

Antes de qualquer stage, verifique o manifest:

```bash
scripts/task-track.sh status
```

Isso mostra:
- **No manifest**: arquivos que a tarefa atual declarou
- **Fora do manifest**: arquivos modificados que NÃO pertencem à tarefa

### 2. Staging

**Cenário A — Manifest existe (recomendado):**

```bash
# Lê os arquivos do manifest e staggeia APENAS eles
MANIFEST_FILES=$(python3 -c "
import json
with open('.claude/task-files/$(git rev-parse --abbrev-ref HEAD).json') as f:
    data = json.load(f)
print(' '.join(data['files']))
")
git add $MANIFEST_FILES
```

Depois, **verifique se há arquivos fora do manifest**:

```bash
scripts/task-track.sh status
```

Se houver arquivos fora do manifest:
- Mostre a lista para o usuário
- Pergunte: "Há N arquivo(s) modificado(s) fora do manifest desta tarefa.
  Incluir no commit? (s/N)"

**Cenário B — Sem manifest (alteração manual):**

Execute `git status --short` e mostre o diff ao usuário:
- Pergunte: "Quer stagear tudo (git add -A) ou prefere selecionar manualmente?"
- Se "tudo" → `git add -A`
- Se "selecionar" → "Use 'git add <arquivo>' manualmente e rode /commit de novo"

### 3. Testes

```bash
python -m pytest -q
```

- Se falhar, aborta imediatamente e mostra o erro
- Se o usuário quiser commitar mesmo com testes falhando, pergunte:
  "Testes estão falhando. Deseja commitar assim mesmo? (s/N)"

### 4. Pre-commit hook

- O hook `git commit` roda `ruff --fix` e `ruff-format`
- Se o hook auto-corrigir arquivos, o commit falha — readicione os arquivos
  modificados pelo auto-fix e re-tente o commit com a mesma mensagem
- Se o hook falhar por erro real (lint não corrigível), aborta

### 5. Limpeza do manifest

Após o commit bem-sucedido (antes do push):

```bash
scripts/task-track.sh finish
```

### 6. Mensagem de commit

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

### 7. Push e PR

```bash
git push
```

- Se falhar → mostra erro → aborta
- Se branch for `main` → "Commit feito e enviado." → fim
- Se não for `main` → pergunta: "Quer abrir um PR também? (s/N)"
  - s → `gh pr create --title "<mensagem>" --body "<corpo>"`
  - n → pronto

## Transparência com o usuário

Sempre mostre ao usuário o **escopo do commit** antes de prosseguir:

```
📋 Escopo do commit (worktree tracking):
   • src/ipolitico/tools/swagger_codegen.py
   • tests/tools/test_swagger_codegen.py
   • tests/tools/fixtures/minimal_swagger.json

⚠️  1 arquivo fora do manifest:
   • src/ipolitico/core/nao_relacionado.py

   Incluir o arquivo fora do manifest? (s/N)
```

## Exemplo de uso

```bash
# Após finalizar uma tarefa com /tdd
/commit

# Fluxo:
#   1. scripts/task-track.sh status  → manifest com 3 arquivos
#   2. git add <3 arquivos>
#   3. pytest -q                      → 208 passed
#   4. git commit -m "feat(tools): swagger_codegen"
#   5. scripts/task-track.sh finish
#   6. git push
#   7. "Branch feat/foo não é main. Quer abrir um PR? (s/N)"
```

## Limitações conhecidas

- **Não lida com conflitos de merge** — se o push falhar por divergência,
  aborta e você resolve manualmente
- **Não edita mensagens** — se quiser ajustar a mensagem, cancele e commite
  manualmente
- **Não faz squash** — commits individuais como saem do TDD
- **Manifest pode ficar obsoleto** se você editar arquivos sem rodar
  `task-track.sh add`. O `/commit` detecta isso e pergunta o que fazer
