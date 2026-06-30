---
Status: completed
Type: AFK
---

# Issue 07 — Discursos e Notas Taquigráficas

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de discursos e notas taquigráficas ponta-a-ponta:
`senadores_discursos` (discursos por senador), `discursos_plenario`
(discursos em plenário por período), `discursos_texto` (texto integral),
`notas_taquigrafia_sessao` (notas de sessão) e `notas_taquigrafia_reuniao`
(notas de reunião de comissão).

**Nota:** Discursos são o exemplo clássico de XML-heritage no PRD original:
envelope aninhado com `Parlamentar.Pronunciamentos.Pronunciamento`.
Quando 1 discurso, `Pronunciamento` é objeto (`_ensure_list` necessário).
Quando 2+, é lista.

### Já existente (não recriar)
- Todos os 5 `DomainType`s registrados
- `DomainSpec` para todos (watermark columns, dependências)
- `EarliestDates` para todos
- `FULL_PIPELINE` e `DOMAIN_UPSTREAM_REQUIREMENTS` configurados
- `SenadoBaseExtractor` (classe base)

### O que implementar

#### Schemas Silver (5 domínios)
- `SILVER_SCHEMAS[senadores_discursos]` — modelar a partir de `GET /senador/{codigo}/discursos`
- `SILVER_SCHEMAS[discursos_plenario]` — modelar a partir de `GET /plenario/lista/discursos/{inicio}/{fim}`
- `SILVER_SCHEMAS[discursos_texto]` — modelar a partir de `GET /discurso/texto-integral/{codigo}`
- `SILVER_SCHEMAS[notas_taquigrafia_sessao]` — modelar a partir de `GET /taquigrafia/notas/sessao/{idSessao}`
- `SILVER_SCHEMAS[notas_taquigrafia_reuniao]` — modelar a partir de `GET /taquigrafia/notas/reuniao/{idReuniao}`

#### Extratores (em `extractors/senado/api/discursos.py`)
- `DiscursosSenadorExtractor` — `GET /senador/{codigo}/discursos`, 1 mês por senador. Data path: `["Parlamentar", "Pronunciamentos", "Pronunciamento"]`
- `DiscursosPlenarioExtractor` — `GET /plenario/lista/discursos/{inicio}/{fim}`, janela mensal
- `DiscursosTextoExtractor` — `GET /discurso/texto-integral/{codigo}`, 1 job por discurso
- `NotasTaquigrafiaSessaoExtractor` — `GET /taquigrafia/notas/sessao/{idSessao}`
- `NotasTaquigrafiaReuniaoExtractor` — `GET /taquigrafia/notas/reuniao/{idReuniao}`
- Notas taquigrafia dependem de IDs de sessão (Plenário) ou reunião (Comissões) — podem ficar para um segundo momento dentro desta issue

#### Transformers (em `transformers/senado/discursos_transformer.py`)
- Aplicar schemas Silver. O transformer de discursos precisa lidar com o aninhamento XML-heritage (`Parlamentar.Pronunciamentos.Pronunciamento`)
- `_ensure_list` será usado pelo `flatten_response` do `SenadoBaseExtractor`

#### YAML
Adicionar em `configs/senado_pipeline.yaml` os 5 domínios

#### Testes
- `tests/extractors/senado/test_discursos.py` — mock httpx com estrutura XML-heritage real (objeto-único e lista)
- `tests/transformers/test_discursos_transformer.py` — DataFrame conhecido → schema

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --incremental --domains senadores_discursos
python -m ipolitico --audit-coverage | grep -E "discursos|notas_taquigrafia"
pytest -q tests/extractors/senado/test_discursos.py tests/transformers/test_discursos_transformer.py
```

## Acceptance criteria

- [x] 5 schemas Silver criados
- [x] 5 extratores implementados
- [x] Transformer(s) implementados com tratamento de XML-heritage
- [x] YAML com os 5 domínios
- [x] Testes unitários passando (incluindo edge case objeto-único vs lista)
- [x] `pytest -q` passa

## Blocked by

- Issue 02 — Senadores (`senadores_discursos` depende de `senadores`)
- Issue 06a — Comissões (`notas_taquigrafia_reuniao` depende de `comissoes_reunioes`)
- Issue 06b — Plenário (`notas_taquigrafia_sessao` depende de `plenario_sessoes`)

**Nota:** `senadores_discursos` e `discursos_plenario` podem ser implementados
independentemente de 06a/06b — apenas notas taquigrafia dependem deles.
