# Finding Template — Documentação de Achados

Template padronizado para documentar qualquer descoberta durante o desenvolvimento:
bugs, dívida técnica, mudanças de design, melhorias arquiteturais ou descobertas
importantes.

## Quando usar

| Momento | Exemplo de finding | Ação |
|---------|--------------------|------|
| Durante TDD | "A API devolve um campo que não esperávamos" | Documenta agora |
| Lendo código existente | "Função X tem um bug na borda" | Documenta agora |
| Durante refactor | "Classe Y está fazendo duas coisas" | Documenta agora |
| Durante code review | "Esse approach não escala pro Senado" | Documenta ou chama `/qa` |
| Durante planejamento | "Mudamos de ideia sobre a estratégia" | Documenta agora |
| Final do `/qa` | QA pergunta: "Teve algum achado?" | Responde e documenta |

## Critérios de triagem

| Critério | Ação |
|----------|------|
| **≤5 linhas de correção**, risco baixo (typo, docstring, nome) | Corrige inline, sem issue |
| **>5 linhas**, risco médio (lógica confusa, cobertura faltando) | Pergunta: "Corrigir agora ou virar issue?" |
| **Bug estrutural**, decisão arquitetural, dívida técnica pesada | Vira issue sempre |
| **Mudança de design** (pivot, novo requisito, descoberta) | Vira issue sempre |
| **Dependência externa** (API mudou, lib deprecated) | Vira issue sempre |

## Template do issue

```markdown
---
Status: needs-triage
Date: <YYYY-MM-DD>
Area: <dominio-afetado>     # ex: extractors, core, tools, pipeline, bulk, gold
Severity: low | medium | high
Source: <skill-ou-origem>   # ex: tdd, qa, code-review, finding-manual
Type: bug | tech-debt | architecture | design-change | discovery
Parent-Task: <ref>           # opcional: link para a tarefa pai
---

# <título conciso — o que precisa ser feito>

## Finding

Descrição clara do que foi encontrado. O contexto é mais importante que o
detalhe — qualquer pessoa no projeto deve entender por que isso é relevante.

## Impact

Por que isso importa — o que pode acontecer se não for resolvido:
- Perda de dados? Performance? Bloqueio de feature futura?
- Risco de regressão? Aumento de dívida técnica?

## Suggested fix

Como resolver. Pode ser:
- **Referência a arquivos e linhas**: "Em `foo.py:42`, mudar X para Y"
- **Issue pai**: Se for grande, referencie uma issue de planejamento
- **Roteiro**: Passos necessários para corrigir

## Location

Arquivos e linhas relevantes.

## How found

Breve descrição de como o finding foi descoberto — ajuda a calibrar os scans
automáticos no futuro.

Exemplo: "Durante o ciclo 4 do TDD, percebi que o `_to_snake_case()` não
normalizava o segmento antes da comparação, gerando falsos positivos."
```

## Exemplos por tipo

### Bug

```markdown
---
Severity: high
Type: bug
---

# Extractor ignora paginação em /deputados

## Finding

O método `fetch_all` em `deputados_extractor.py` não itera sobre as páginas
seguintes da API — só pega a primeira página (page=1).

## Impact

Apenas 50 dos 513 deputados são ingeridos. Os dados ficam incompletos sem
aviso.

## Suggested fix

Adicionar loop de paginação: ler `totalPages` do primeiro response e iterar
até o final.

## Location

`src/ipolitico/extractors/camara/api/deputados/deputados_extractor.py:85-92`
```

### Tech Debt

```markdown
---
Severity: medium
Type: tech-debt
---

# Retry logic duplicada em 5 extratores

## Finding

A lógica de `exponential_backoff` com tenacity está copiada em 5 extratores
diferentes com os mesmos parâmetros.

## Impact

- Mudar a política de retry exige editar 5 arquivos
- Risco de um extrator ficar com parâmetros diferentes sem intenção

## Suggested fix

Extrair para um decorator compartilhado em `extractors/base.py` ou
`extractors/camara/api/camara_base.py`.

## Location

Arquivos: `deputados_extractor.py`, `blocos_extractor.py`,
`partidos_extractor.py`, `eventos_extractor.py`, `frentes_extractor.py`
```

### Architecture

```markdown
---
Severity: medium
Type: architecture
---

# SILVER_SCHEMAS sem compatibilidade retroativa

## Finding

Ao adicionar uma coluna nova no `SILVER_SCHEMAS`, jobs antigos que já
escreveram dados sem essa coluna quebram ao fazer refresh.

## Impact

Não podemos evoluir o schema sem limpar e reingerir tudo.

## Suggested fix

Adotar schema evolution: usar `pl.Int64` com null como default para colunas
novas. Documentar política de evolução em `CONTEXT.md`.

## Location

`src/ipolitico/core/schemas.py` (todo o módulo)
```

### Design Change

```markdown
---
Severity: medium
Type: design-change
---

# Estratégia de watermark mudou para janela fixa sem dependências

## Finding

Decidimos que o `WindowResolver` vai calcular a janela como `[último
watermark, agora]` para todos os domínios, ignorando dependências. A lógica
de `depends_on` no `DomainSpec` não é mais usada para janela (só para
ordenação de inicialização).

## Impact

- `depends_on` no `DomainSpec` perdeu metade do seu propósito original
- Código antigo que usava dependências para janela precisa ser revisado

## Suggested fix

Remover a lógica de dependência de janela do `WindowResolver` e deixar
explícito que `depends_on` é só para ordem de inicialização.

## Location

`src/ipolitico/core/window_resolver.py:30-45`
```

## Ciclo de vida do issue

```
[needs-triage]  →  ready-for-agent  →  (implementado via /tdd)
     ↓                    ↓
ready-for-human   (feito)
     ↓
(priorização)
```

1. **needs-triage**: Acabou de ser criado. Precisa de revisão humana.
2. **ready-for-agent**: OK para implementar via `/tdd`.
3. **ready-for-human**: Requer decisão humana (ex: depende de terceiros).
4. **wontfix**: Decidiu-se não fazer.

## Referências

- [Issue tracking](issue-tracker.md) — fluxo completo de gerenciamento de issues
- [Triage labels](triage-labels.md) — definição dos labels de triagem
