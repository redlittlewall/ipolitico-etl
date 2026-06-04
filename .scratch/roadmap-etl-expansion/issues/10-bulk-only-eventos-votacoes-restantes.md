---
Status: ready-for-agent
Date: 2026-06-04
Area: bulk
Fase: 3
---

# Domínios Bulk-only: eventosPresencaDeputados + eventosRequerimentos + votacoesObjetos + votacoesProposicoes

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Implementar 4 datasets bulk-only restantes:

1. **eventosPresencaDeputados** — presença de deputados em eventos (anual)
2. **eventosRequerimentos** — requerimentos de eventos (anual)
3. **votacoesObjetos** — objetos de votação (anual)
4. **votacoesProposicoes** — proposições afetadas por votação (anual)

Para cada domínio:

1. Adicionar `DomainType` em `core/constants.py`
2. Adicionar `DomainSpec` em `core/domain_spec.py`
3. Adicionar `SILVER_SCHEMA` em `core/schemas.py`
4. Adicionar entrada em `BULK_REGISTRY` com URL template anual
5. Criar transformer (ou reusar genérico)
6. Adicionar entrada no YAML
7. Testes unitários com fixture CSV local

## Acceptance criteria

- [ ] 4 novos `DomainType` declarados
- [ ] `DomainSpec`, `EARLIEST_DATE_MAP`, `SILVER_SCHEMA` configurados
- [ ] `BULK_REGISTRY` com entries
- [ ] YAML com entries
- [ ] Transformers implementados
- [ ] Testes unitários com fixture CSV
- [ ] `pytest -q` passando

## Blocked by

None — Fase 3 pode rodar em paralelo com a Fase 2.
