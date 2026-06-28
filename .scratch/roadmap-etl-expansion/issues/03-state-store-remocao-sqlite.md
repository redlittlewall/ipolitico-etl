---
Status: ready-for-agent
Date: 2026-06-04
Area: arquitetura
Fase: 1
---

# StateStore interface + DataLakeRepository implementation + remoção SQLiteSink

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Extrair os métodos `get_watermark()` e `get_existing_ids()` de `BaseSink`
para uma nova interface `StateStore` em `storage/state_store.py`.

Arquivos modificados:

- **Criar** `storage/state_store.py` com a interface `StateStore`
- **Modificar** `storage/datalake_repository.py`: `DataLakeRepository` implementa `StateStore`
- **Modificar** `sinks/base.py`: `BaseSink` perde `get_watermark()` e `get_existing_ids()` — fica apenas `save()` e `flush()`
- **Modificar** `pipeline/window_resolver.py`: recebe `StateStore` em vez de `BaseSink`
- **Modificar** `pipeline/planners/camara_jobs.py` e `strategies.py`: recebem `StateStore` em vez de `BaseSink`
- **Modificar** `pipeline/manager.py`: injeta `self._lake` (DataLakeRepository) como `StateStore`
- **Remover** `sinks/sqlite_sink.py`
- **Remover** `SinkType.SQLITE` de `core/constants.py`
- **Simplificar** `pipeline/builder.py`: remove ramo `if sink_type == SinkType.SQLITE`
- **Remover** `tests/sinks/test_sqlite_sink.py`

Estado do `PipelineManager`:

```
antes:  WindowResolver(state_store=BaseSink)
depois: WindowResolver(state_store=StateStore)
        CamaraJobPlanner(state_store=StateStore, lake=DataLakeRepository)

        PipelineManager.state_store → BaseSink (só save/flush)
        PipelineManager._lake → DataLakeRepository (implements StateStore)
```

## Acceptance criteria

- [ ] Interface `StateStore` definida com `get_watermark()` e `get_existing_ids()`
- [ ] `DataLakeRepository` implementa `StateStore`
- [ ] `WindowResolver` e `CamaraJobPlanner` aceitam `StateStore`
- [ ] `PipelineBuilder.build()` não tem mais branch SQLite
- [ ] `SQLiteSink` removido (arquivo + enum + referências)
- [ ] Testes existentes continuam passando após adaptação para `StateStore`
- [ ] Testes unitários para `StateStore` (tempdir + Parquet)
- [ ] `pytest -q` passando

## Blocked by

None — independente da issue 02.
