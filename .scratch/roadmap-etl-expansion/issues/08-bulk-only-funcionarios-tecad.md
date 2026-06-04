---
Status: ready-for-agent
Date: 2026-06-04
Area: bulk
Fase: 3
---

# Domínios Bulk-only: funcionarios + tecadCategorias + tecadTermos

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Implementar três novos domínios que só existem como dumps CSV (sem rota na API
REST da Câmara):

1. **funcionarios** — servidores da Câmara dos Deputados (snapshot)
2. **tecadCategorias** — categorias da pauta legislativa (snapshot)
3. **tecadTermos** — termos da pauta legislativa (snapshot)

Para cada domínio:

1. Adicionar `DomainType` em `core/constants.py`
2. Adicionar `DomainSpec` em `core/domain_spec.py`
3. Adicionar `SILVER_SCHEMA` em `core/schemas.py` (espiar o CSV para definir)
4. Adicionar entrada em `BULK_REGISTRY` com URL template snapshot
5. Criar transformer (ou reusar genérico se schema for simples)
6. Adicionar entrada no YAML
7. Testes unitários com fixture CSV local

## Acceptance criteria

- [ ] Três novos `DomainType` declarados
- [ ] `DomainSpec`, `EARLIEST_DATE_MAP`, `SILVER_SCHEMA` configurados
- [ ] `BULK_REGISTRY` com entries para funcionarios, tecadCategorias, tecadTermos
- [ ] YAML com entries
- [ ] Transformers (ou reúso de genérico) implementados
- [ ] Testes unitários com fixture CSV
- [ ] `pytest -q` passando

## Blocked by

None — Fase 3 pode rodar em paralelo com a Fase 2.
