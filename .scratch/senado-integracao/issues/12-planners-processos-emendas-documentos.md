---
Status: ready
Priority: P0
Type: fix
---

# Issue 12 — Criar Planners Anuais/Semestrais para Processos Emendas e Documentos

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

A API do Senado impõe limites de janela temporal para dois endpoints de processos:

- **`processo/emenda`**: Limite de **1 ano** por requisição
- **`processo/documento`**: Limite de **6 meses** por requisição

Atualmente, o planner envia uma janela única `1949-01-01 → 2026-06-30` (77 anos), que a API rejeita com HTTP 400.

### Solução

Criar um planner parametrizável que segmenta janelas históricas em blocos de tamanho máximo configurável. Pode ser um novo método no `WindowResolver` ou um planner específico para Senado.

**Decisão de implementação (prototype):**
- Novo parâmetro `max_window_days` no planner (365 para emendas, 180 para documentos)
- O planner divide a janela total `[earliest_date, today]` em chunks de `max_window_days`
- Cada chunk vira um job independente (parallelizável)

## Acceptance criteria

- [ ] `processo_emendas` processa janela completa sem HTTP 400
- [ ] `processo_documentos` processa janela completa sem HTTP 400
- [ ] Ambos retornam dados Silver > 0
- [ ] Planners não quebram domínios existentes (processos, votações)
- [ ] `pytest -q` passando

## Blocked by

None — can start immediately
