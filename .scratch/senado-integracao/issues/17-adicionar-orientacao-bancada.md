---
Status: ready
Priority: P2
Type: feature
---

# Issue 17 — Adicionar Dados de Orientação de Bancada em Votações

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Endpoint novo de alto valor:

- **`plenario/votacao/orientacaoBancada/{dataInicio}/{dataFim}`**: Retorna como cada líder partidário orientou sua bancada em cada votação nominal

Este é um dado **exclusivo do Senado** (a Câmara não oferece equivalente direto) e de alto valor para análise política — permite saber se um partido orientou "sim", "não", "livre" ou "obstrução" em cada votação.

### Implementação

1. Novo extrator com planner temporal (janelas mensais ou trimestrais)
2. Novo transformer que normaliza os campos: `dataSessao`, `codigoMateria`, `siglaPartido`, `orientacao`, `codigoVotacao`
3. Schema Silver novo
4. Mapear no `senado_pipeline.yaml`
5. Dependência de `votacoes_senado` (precisa dos IDs de votação)

## Acceptance criteria

- [ ] Extrator `OrientacaoBancadaExtractor` implementado
- [ ] Transformer normaliza orientações para Silver
- [ ] Schema Silver com campos: `data_sessao`, `codigo_materia`, `sigla_partido`, `orientacao`, `codigo_votacao`
- [ ] Mapeado no `senado_pipeline.yaml`
- [ ] `pytest -q` passando

## Blocked by

- Issue 10 (padrão consolidado)
