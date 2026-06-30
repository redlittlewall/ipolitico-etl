---
Status: ready
Priority: P0
Type: fix
---

# Issue 10 — Corrigir Formato de Data nos Extratores (Plenário, Discursos, Comissões)

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

A API do Senado é inconsistente: **paths de URL esperam `YYYYMMDD`** (sem hífens), mas query params aceitam `YYYY-MM-DD`. Os extratores atuais enviam `YYYY-MM-DD` nos paths, causando HTTP 404.

Isso afeta **6 domínios** que passariam a funcionar imediatamente com a correção:

| Domínio | Endpoint | Exemplo correto |
|---|---|---|
| `plenario_agenda` | `plenario/agenda/dia/{data}` | `plenario/agenda/dia/20240601.json` |
| `plenario_resultados` | `plenario/resultado/{data}` | `plenario/resultado/20240601.json` |
| `plenario_sessoes` | `plenario/legislatura/{data}` | `plenario/legislatura/20240601.json` |
| `discursos_plenario` | `plenario/lista/discursos/{di}/{df}` | `plenario/lista/discursos/20240101/20240131.json` |
| `comissoes_reunioes` | `comissao/agenda/{di}/{df}` | `comissao/agenda/20240101/20240131.json` |
| `senadores_discursos` | `senador/{codigo}/discursos?ano={ano}` | endpoint funciona (200), investigar se 0 dados é do transformer |

**O que NÃO deve ser alterado:**
- `processo/emenda` e `processo/documento` usam query params `dataInicio`/`dataFim` — esses aceitam `YYYY-MM-DD` e estão corretos
- `votacoes_comissao` usa query params — está correto

### Decisão de implementação (prototype)

O formato de data no path da URL deve usar `strftime("%Y%m%d")` ao invés de `strftime("%Y-%m-%d")`. A mudança é localizada — apenas nos `f"..."` que montam o endpoint nos métodos `extract()`.

## Acceptance criteria

- [ ] `plenario_agenda` retorna dados Silver > 0 (testar com data de sessão conhecida)
- [ ] `plenario_resultados` retorna dados Silver > 0
- [ ] `plenario_sessoes` retorna dados Silver > 0
- [ ] `discursos_plenario` retorna dados Silver > 0
- [ ] `comissoes_reunioes` retorna dados Silver > 0
- [ ] `senadores_discursos` retorna dados Silver > 0 (se for transformer, incluir ajuste no `_DATA_PATH_SENADOR` ou field map)
- [ ] `processo/emenda` e `processo/documento` continuam funcionando (query params não foram alterados)
- [ ] Todos os 6 domínios passam na Gold optimization
- [ ] `pytest -q` passando (572+)

## Blocked by

None — can start immediately
