---
Status: ready
Priority: P1
Type: investigate
---

# Issue 14 — Verificar Votações Comissão (Siglas e Planner)

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

O endpoint `votacaoComissao/comissao/{sigla}` funciona e retorna dados ricos (votos individuais dos membros da comissão). Testado manualmente com `CAE` — retorna votos desde 2015 com estrutura completa.

Porém, na execução full load, o extrator `SenadoVotacoesComissaoExtractor` retornou 0 dados.

### O que investigar

1. Como o planner obtém a sigla da comissão? Precisa vir de `comissoes_senado` (campo `SiglaColegiado`)
2. O `domain_order.py` tem `votacoes_comissao` dependendo de `comissoes_senado`?
3. Testar com sigla `CAE`, `CCJ`, `CAS` — todas devem funcionar
4. O transformer precisa extrair os votos aninhados (`Votacao.Votos.Voto[]`) ou apenas o cabeçalho da votação?
5. Verificar se o planner está gerando jobs com/sem janela temporal (query params `dataInicio`/`dataFim`)

## Acceptance criteria

- [ ] `votacoes_comissao` retorna dados Silver > 0
- [ ] Votos individuais dos membros estão sendo extraídos (ou apenas cabeçalho, conforme decisão)
- [ ] Schema Silver cobre os campos: `codigoVotacao`, `siglaColegiado`, `identificacaoMateria`, `dataHoraInicioReuniao`, votos
- [ ] `pytest -q` passando

## Blocked by

None — can start immediately
