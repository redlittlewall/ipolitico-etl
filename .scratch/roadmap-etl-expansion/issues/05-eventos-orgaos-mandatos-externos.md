---
Status: ready-for-agent
Date: 2026-06-04
Area: api-camara
Fase: 2
---

# Rotas API: eventos_orgaos + mandatos_externos

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Implementar os endpoints aninhados faltantes:

- `/eventos/{id}/orgaos` → domínio `eventos_orgaos`
- `/deputados/{id}/mandatosExternos` → domínio `mandatos_externos`

**eventos_orgaos**: retorna `Orgao` (mesmo schema da lista de órgãos, mas
representa o relacionamento "quais órgãos organizaram cada evento"). Segue
padrão `evento_child`.

**mandatos_externos**: retorna `DeputadoMandatoExterno` (cargos eletivos
anteriores do deputado — `anoFim`, `anoInicio`, `cargo`, `municipio`,
`siglaPartidoEleicao`, `siglaUf`). Segue padrão `deputado_child`.

Para cada domínio:

1. Adicionar `DomainType` em `core/constants.py`
2. Adicionar `DomainSpec` (watermark None, depends_on do pai, unique_keys)
3. Adicionar `SILVER_SCHEMA` em `core/schemas.py`
4. Adicionar `EARLIEST_DATE_MAP`
5. Criar extrator (reusando `evento_child.py` ou `deputado_child.py` quando
   possível — nova classe filha se schema for diferente)
6. Adicionar entrada no YAML
7. Testes unitários com mock httpx

## Acceptance criteria

- [ ] `DomainType.EVENTOS_ORGAOS` e `DomainType.MANDATOS_EXTERNOS` declarados
- [ ] `DomainSpec`, `EARLIEST_DATE_MAP` e `SILVER_SCHEMA` configurados
- [ ] YAML com entries
- [ ] Extratores e transformers (ou reúso de genéricos) implementados
- [ ] Testes unitários com mock httpx
- [ ] `pytest -q` passando

## Blocked by

None — independente das issues 04 e 06.
