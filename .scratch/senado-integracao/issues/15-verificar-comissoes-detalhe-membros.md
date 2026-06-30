---
Status: ready
Priority: P1
Type: investigate
---

# Issue 15 — Verificar Comissões Detalhe e Membros (Data Paths e Envelopes)

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Três domínios de comissão executaram (1 job cada) mas produziram 0 dados:

| Domínio | Endpoint | Status |
|---|---|---|
| `comissoes_detalhe` | `comissao/{codigo}` | 0 dados |
| `comissoes_membros` | `composicao/comissao/{codigo}?ativas=S` | 0 dados |
| `comissoes_reunioes` | `comissao/agenda/{di}/{df}` | 0 dados (também afetado pelo date format) |

### O que investigar

1. **`comissoes_detalhe`**: Endpoint retorna 200. Envelope é `ComissoesCongressoNacional.Colegiados.Colegiado[]`. Verificar se `_DATA_PATH` no extrator corresponde a essa estrutura.
2. **`comissoes_membros`**: Endpoint retorna 200 com `?ativas=S`. Envelope é `ComposicaoAtivaComissaoSf`. Verificar `data_path` no extrator.
3. **`comissoes_reunioes`**: Corrigir date format primeiro (#10), depois testar se o `data_path` corresponde ao envelope de retorno.
4. Os transformers em `institutional_transformer.py` — conferir se `_COMISSOES_DETALHE_FIELD_MAP` e `_COMISSOES_MEMBROS_FIELD_MAP` estão alinhados com os campos reais.

## Acceptance criteria

- [ ] `comissoes_detalhe` retorna dados Silver > 0
- [ ] `comissoes_membros` retorna dados Silver > 0
- [ ] `comissoes_reunioes` retorna dados Silver > 0 (após correção do date format)
- [ ] `pytest -q` passando

## Blocked by

- Issue 10 (comissoes_reunioes depende da correção do date format)

## Blocked by

Issue 10 (comissoes_reunioes depende da correção do date format)
