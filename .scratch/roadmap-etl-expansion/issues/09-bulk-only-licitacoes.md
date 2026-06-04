---
Status: ready-for-agent
Date: 2026-06-04
Area: bulk
Fase: 3
---

# Domínios Bulk-only: licitações (5 datasets)

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Implementar os 5 datasets de licitações da Câmara, disponíveis apenas como
dumps CSV anuais:

1. **licitacoes** — licitações
2. **licitacoesContratos** — contratos de licitação
3. **licitacoesItens** — itens de licitação
4. **licitacoesPedidos** — pedidos de licitação
5. **licitacoesPropostas** — propostas de licitação

Este é o grupo mais complexo da Fase 3, pois são 5 datasets inter-relacionados
(provavelmente com chaves estrangeiras entre si). Requer:

1. Análise dos CSVs para entender schemas e relações
2. Definição de `SILVER_SCHEMA` para cada um
3. Decisão se todos entram como domínios independentes (sim, append-only)
4. Definição de dependências entre eles (ex: licitacoesContratos depende de
   licitacoes)
5. Implementação completa (DomainType, DomainSpec, BULK_REGISTRY, transformer,
   YAML, testes)

## Acceptance criteria

- [ ] 5 novos `DomainType` declarados
- [ ] `DomainSpec`, `EARLIEST_DATE_MAP`, `SILVER_SCHEMA` configurados
- [ ] `BULK_REGISTRY` com entries (anuais) para os 5 datasets
- [ ] YAML com entries
- [ ] Transformers implementados
- [ ] Testes unitários com fixture CSV
- [ ] `pytest -q` passando
- [ ] Dependências entre datasets documentadas (se aplicável)

## Blocked by

None — Fase 3 pode rodar em paralelo com a Fase 2.
