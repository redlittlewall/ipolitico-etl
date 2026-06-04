---
Status: ready-for-agent
Date: 2026-06-04
Area: arquitetura
Fase: 0
---

# Commit da remoção das subclasses Bulk rasas

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Committar as alterações já implementadas e testadas no working tree que
removem as 5 subclasses rasas de `BaseBulkExtractor` (`deputados_bulk.py`,
`despesas_bulk.py`, `proposicoes_bulk.py`, `votacoes_bulk.py`) e consolidam a
lógica no próprio `BaseBulkExtractor`, que agora aceita `domain_name` como
parâmetro do construtor.

## Acceptance criteria

- [ ] 12 arquivos modificados são commitados com mensagem descritiva
- [ ] Nenhum teste quebrado (124/124 testes passando)
- [ ] Os arquivos deletados não aparecem mais no working tree

## Blocked by

None — pode começar imediatamente.
