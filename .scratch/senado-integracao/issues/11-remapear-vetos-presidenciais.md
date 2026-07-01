---
Status: done
Closed: 2026-06-30
Close reason: implemented
Priority: P0
Type: fix
---

# Issue 11 — Re-mapear Vetos Presidenciais para Novo Envelope da API

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

A API de vetos do Senado mudou o endpoint e a estrutura de resposta. O endpoint `/materia/vetos/{ano}` agora redireciona para `/dados/ListaVetosAnoCN{ano}.json` com envelope `ListaVetosAnoCN` ao invés do antigo `MateriaVetos`, e os campos retornados são completamente diferentes.

### Estrutura atual da resposta (válida)
```json
{
  "ListaVetosAnoCN": {
    "Metadados": { ... },
    "Vetos": {
      "Veto": [
        {
          "Codigo": 1234,
          "Materia": "...",
          "MateriaVetada": "...",
          "Mensagem": "...",
          "Total": "Sim",
          "Assunto": "...",
          "DataRecebimentoCongresso": "2024-01-15",
          ...
        }
      ]
    }
  }
}
```

### O que precisa mudar

1. **`_DATA_PATH_PRESIDENCIAIS`**: `["MateriaVetos", "Vetos", "Veto"]` → `["ListaVetosAnoCN", "Vetos", "Veto"]`
2. **`_FIELD_MAP_PRESIDENCIAIS`**: Re-mapear com os campos reais da API (`Codigo, Materia, MateriaVetada, Mensagem, Total, Assunto, DataRecebimentoCongresso, ...`)
3. **`vetos_detalhe`**: O endpoint `plenario/resultado/veto/{codigo}` é um endpoint diferente — verificar se ainda é o correto para detalhe do veto, ou se usa o mesmo novo envelope

## Acceptance criteria

- [x] `_DATA_PATH_PRESIDENCIAIS` atualizado para `["ListaVetosAnoCN", "Vetos", "Veto"]`
- [x] `_FIELD_MAP_PRESIDENCIAIS` mapeia todos os 44 campos relevantes do novo envelope
- [x] Transformer renomeia corretamente para snake_case Silver
- [x] Schema Silver atualizado com todos os campos (44 cols + 1 extra no detalhe)
- [x] `vetos_presidenciais` retorna dados Silver > 0 (pelo menos 50+ registros para 2024)
- [x] `vetos_detalhe` também funciona (mesma estrutura base + `dispositivos`)
- [x] `pytest -q` passando (15/15)

## Blocked by

None — can start immediately
