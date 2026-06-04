---
Status: ready-for-agent
Date: 2026-06-04
Area: senado
Fase: 4
---

# Implementar SenadoSourceProvider + primeiros domínios

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Após a pesquisa e documentação da API do Senado (issue 12), implementar o
adapter seguindo o protocolo `SourceProvider`, análogo ao
`CamaraSourceProvider`.

Estrutura nova:

```
src/ipolitico/
├── core/
│   ├── senado_constants.py    # SenadoDomainType, ApiRoutes, etc.
│   ├── senado_schemas.py      # SILVER_SCHEMAS para Senado
│   └── senado_domain_spec.py  # DomainSpec para Senado
├── extractors/senado/         # Extratores (API)
├── transformers/senado/       # Transformers
├── sinks/                     # Reusa DataLakeSink
├── sources/
│   ├── camara_provider.py     # (existente)
│   └── senado_provider.py     # SenadoSourceProvider
└── ...
```

O `SenadoSourceProvider` implementa a mesma interface que
`CamaraSourceProvider`, permitindo que o `FederationOrchestrator` execute
ambos:

```python
class SenadoSourceProvider:
    async def execute(
        self,
        domains: list[SenadoDomainType],
        strategy: LoadStrategy,
        sink_type: SinkType,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None: ...
```

O escopo exato dos primeiros domínios será definido pela issue 12, mas espera-se:

- Senadores (equivalente a deputados)
- Proposições do Senado
- Votações nominais do Senado
- Despesas (se disponível)

## Acceptance criteria

- [ ] `core/senado_constants.py` com DomainType e ApiRoutes
- [ ] `core/senado_schemas.py` com SILVER_SCHEMAS para primeiros domínios
- [ ] `core/senado_domain_spec.py` com specs
- [ ] Extratores para primeiros 3-5 domínios
- [ ] Transformers para primeiros 3-5 domínios
- [ ] `sources/senado_provider.py` com `SenadoSourceProvider`
- [ ] `FederationOrchestrator` consegue executar Câmara + Senado
- [ ] Testes unitários (mock httpx)
- [ ] `pytest -q` passando

## Blocked by

[12 - Pesquisar e documentar a API do Senado](12-senado-pesquisa-documentacao.md)
