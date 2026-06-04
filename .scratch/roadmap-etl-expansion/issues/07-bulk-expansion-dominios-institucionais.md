---
Status: ready-for-agent
Date: 2026-06-04
Area: bulk
Fase: 2
---

# Registrar dumps Bulk para domínios já cobertos pela API

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Expandir o `BULK_REGISTRY` para incluir todos os datasets bulk disponíveis no
portal de Dados Abertos da Câmara que correspondem a domínios já implementados
via API.

O `BaseBulkExtractor._build_url()` é atualizado para usar um padrão de URL
genérico com template, ao invés de URL fixa por dataset:

```python
BULK_REGISTRY: dict[str, dict] = {
    "eventos": {
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-{year}.csv",
        "requires_year": True,
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataHoraInicio",
    },
    "frentes": {
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/frentes/csv/frentes.csv",
        "requires_year": False,
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
    },
    ...
}
```

Domínios a adicionar (que já têm implementação via API):

| Dataset | Granularidade | Domínio(s) correspondente(s) |
|---|---|---|
| eventos | Anual | eventos |
| frentes | Snapshot | frentes |
| grupos | Snapshot | grupos |
| gruposMembros | Snapshot | grupos_membros |
| gruposHistorico | Snapshot | grupos_historico |
| legislaturas | Snapshot | legislaturas |
| legislaturasMesas | Snapshot | legislaturas_mesa |
| orgaos | Snapshot | orgaos |
| orgaosDeputados | Snapshot (por legislatura) | deputados_orgaos |
| frentesDeputados | Snapshot | deputados_frentes |
| deputadosOcupacoes | Snapshot | ocupacoes |
| deputadosProfissoes | Snapshot | profissoes |
| votacoesOrientacoes | Anual | orientacoes |

Alguns datasets podem precisar de ajuste no `SourceRouter` para que a rota
Bulk seja selecionada para estes novos registros (a lógica de "Bulk se
full-load multi-ano" já existe; mas datasets snapshot sem `ano` podem precisar
de tratamento especial).

Os transformers precisam de adaptação mínima para aceitar dados Bulk
(possivelmente nomes de colunas diferentes entre Bulk CSV e API JSON). Isso
pode ser feito por domínio dentro do transformer existente.

## Acceptance criteria

- [ ] `BaseBulkExtractor._build_url()` suporta `url_template` genérico
- [ ] `BULK_REGISTRY` tem entradas para todos os 13 datasets listados
- [ ] `SourceRouter` consegue usar Bulk para estes domínios em full load
- [ ] Transformers existentes tratam colunas Bulk (quando divergirem da API)
- [ ] Testes: `BaseBulkExtractor` com template URL + fixture CSV
- [ ] `pytest -q` passando

## Blocked by

None — independente das demais issues da Fase 2.
