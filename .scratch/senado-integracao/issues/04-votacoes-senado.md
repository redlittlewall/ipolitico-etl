---
Status: completed
Type: AFK
---

# Issue 04 — Votações do Senado

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Implementar os domínios de votações do Senado ponta-a-ponta:
`votacoes_senado` (votações nominais em plenário), `votos_senado` (votos
individuais), `votacoes_comissao` (votações em comissões).

### Já existente (não recriar)
- `DomainType.VOTACOES_SENADO`, `VOTOS_SENADO`, `VOTACOES_COMISSAO` registrados
- `DomainSpec` para todos (watermark columns, dependências, unique keys)
- `EarliestDates` para todos
- `FULL_PIPELINE` e `DOMAIN_UPSTREAM_REQUIREMENTS` configurados
- `SILVER_SCHEMA` para `votacoes_senado` (10 campos: votacao_id, codigo_materia, id_processo, identificacao, ementa, data_apresentacao, data_sessao, descricao_votacao, resultado)
- `SILVER_SCHEMA` para `votos_senado` (6 campos: votacao_id, codigo_parlamentar, nome_parlamentar, sigla_partido, sigla_uf, voto)
- `SenadoBaseExtractor` (classe base)

### O que implementar

#### Schemas Silver (1 domínio)
- `SILVER_SCHEMAS[votacoes_comissao]` — modelar schema

#### Extratores (em `extractors/senado/api/votacoes.py`)
- `VotacoesSenadoExtractor` — `GET /votacao` com parâmetros `dataInicio`/`dataFim` (janela mensal). Aceita também `codigoParlamentar` e `idProcesso` como filtros opcionais.
- `VotosSenadoExtractor` — verificar no spec se votos individuais estão embutidos na resposta de `/votacao` ou num endpoint separado. Adaptar conforme a realidade da API.
- `VotacoesComissaoExtractor` — `GET /votacaoComissao/comissao/{siglaComissao}` com janela mensal. Itera por comissão × mês.

#### Transformers (em `transformers/senado/votacoes_transformer.py`)
- `SenadoVotacoesTransformer` — aplicar schema Silver
- `SenadoVotosTransformer` — extrair/achatar votos individuais
- `SenadoVotacoesComissaoTransformer` — aplicar schema

#### YAML
Adicionar em `configs/senado_pipeline.yaml` os 3 domínios

#### Testes
- `tests/extractors/senado/test_votacoes.py` — mock httpx/respx
- `tests/transformers/test_votacoes_transformer.py` — DataFrame conhecido → schema

### Script de verificação

```bash
python -m ipolitico pipeline --source senado --full-load --domains votacoes_senado
python -m ipolitico --audit-coverage | grep -E "votacoes_senado|votos_senado|votacoes_comissao"
pytest -q tests/extractors/senado/test_votacoes.py tests/transformers/test_votacoes_transformer.py
```

## Acceptance criteria

- [ ] `SILVER_SCHEMAS[votacoes_comissao]` criado
- [ ] 3 extratores implementados
- [ ] Transformers implementados
- [ ] YAML com os 3 domínios
- [ ] `python -m ipolitico pipeline --source senado --full-load --domains votacoes_senado` executa sem erros
- [ ] `--audit-coverage` mostra registros > 0
- [ ] `pytest -q` passa

## Blocked by

Issue 03 — Processos (votações depende de `PROCESSOS` como upstream requirement)
