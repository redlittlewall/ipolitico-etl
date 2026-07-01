---
Status: done
Priority: P1
Type: investigate
---

# Issue 13 — Verificar Pipeline de Processos Detalhe (Propagação de IDs)

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

O endpoint `processo/{id}` existe na API e funciona com IDs válidos (ex: `8783559`), mas o extrator `SenadoProcessosDetalheExtractor` retornou 0 dados na execução full load — mesmo que a lista de `processos` tenha retornado 10.709 registros com IDs.

Suspeita: Os IDs da lista de `processos` (campo `id`, ex: `8783559`) não estão sendo propagados corretamente como parâmetros de job para `processos_detalhe`. O planner pode estar gerando jobs com IDs inválidos (ex: números sequenciais `1, 2, 3...`) ao invés dos IDs reais.

### O que investigar

1. Como o planner de `processos_detalhe` gera os jobs?
2. Quais IDs está passando?
3. O `processos` domain está configurado como dependência de `processos_detalhe` no `domain_order.py`?
4. Testar com um ID válido manualmente (`processo/8783559.json`) e ver o envelope

## Acceptance criteria

- [x] IDs corretos são propagados da lista de processos para o detalhe
- [x] `processos_detalhe` retorna dados Silver > 0 (pendente de full load)
- [x] Schema Silver cobre os campos do envelope (`id, codigoMateria, identificacao, sigla, ementa, tramitando, situacaoAtual, dataSituacaoAtual, ...`)
- [x] `pytest -q` passando (587/587)

## Blocked by

None — can start immediately
