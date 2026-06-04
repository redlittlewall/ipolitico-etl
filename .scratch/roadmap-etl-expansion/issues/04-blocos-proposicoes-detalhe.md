---
Status: ready-for-agent
Date: 2026-06-04
Area: api-camara
Fase: 2
---

# Rotas API: blocos_detalhe + proposicoes_detalhe

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Implementar os endpoints de detalhe faltantes:

- `/blocos/{id}` → domínio `blocos_detalhe`
- `/proposicoes/{id}` → domínio `proposicoes_detalhe`

Ambos seguem o padrão `detail_child` de extrator + `CamaraDetalheTransformer`
já existentes. É necessário:

1. Adicionar `DomainType.BLOCOS_DETALHE` e `DomainType.PROPOSICOES_DETALHE` em
   `core/constants.py` (verificar se `blocos_detalhe` já existe — se sim,
   validar que está correto)
2. Adicionar `DomainSpec` em `core/domain_spec.py`
3. Adicionar `SILVER_SCHEMA` em `core/schemas.py` (ou verificar se já existe
   entrada para `detail_child`)
4. Adicionar extratores em `detail_child.py` (classes `BlocosDetalheExtractor`
   e `ProposicoesDetalheExtractor`)
5. Adicionar entrada no YAML (`configs/camara_pipeline.yaml`)
6. Adicionar `EARLIEST_DATE_MAP` em `core/constants.py` para ambos
7. Testes unitários com mock httpx

**Nota sobre `/blocos/{id}`**: o schema Swagger é idêntico ao da rota raiz
(`Bloco`). Se o payload retornado for estritamente o mesmo, este domínio pode
ser descartado (não adiciona dados novos). Validar com uma chamada real antes
de implementar.

## Acceptance criteria

- [ ] `DomainType.BLOCOS_DETALHE` e `DomainType.PROPOSICOES_DETALHE` declarados
- [ ] `DomainSpec` e `EARLIEST_DATE_MAP` configurados
- [ ] `SILVER_SCHEMA` configurado para ambos
- [ ] YAML com entries para ambos domínios
- [ ] Extratores seguem padrão `detail_child`
- [ ] Testes unitários com mock httpx
- [ ] `pytest -q` passando

## Blocked by

None — pode começar imediatamente.
