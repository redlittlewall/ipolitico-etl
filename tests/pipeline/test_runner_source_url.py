"""
Testes do mecanismo único de ``_source_url`` no DataFrame Silver final.

A issue 01 exige que o runner seja a autoridade única sobre ``_source_url``:
preservar a URL injetada na extração (URL do arquivo em bulk, URL com página
em listas paginadas, URL do recurso em registros com ID) e nunca zerá-la.
Estes testes exercitam o ``PipelineRunner`` completo (extractor/transformer
mockados, sink capturando o DataFrame persistido) e fazem assert no
DataFrame Silver final que chega ao ``sink.save``.
"""

from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest

from ipolitico.core.constants import DomainType, MedallionLayer
from ipolitico.core.source_urls import SOURCE_URL_TEMPLATES
from ipolitico.pipeline.builder import PipelineComponents
from ipolitico.pipeline.runner import PipelineRunner

_CAMARA_BASE = "https://dadosabertos.camara.leg.br/api/v2"


def _captured_silver_df(sink) -> pl.DataFrame:
    """Retorna o DataFrame Silver final entregue ao sink.save na 1ª chamada."""
    return sink.save.await_args_list[0].kwargs["df"]


def _make_components(extractor_df: pl.DataFrame, transformer=None) -> PipelineComponents:
    """Monta PipelineComponents com extractor/transformer/sink mockados."""
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extractor_df)

    if transformer is None:
        transformer = MagicMock()
        transformer.transform.side_effect = lambda raw_df, **kw: raw_df

    sink = MagicMock()
    sink.save = AsyncMock()
    sink.flush = AsyncMock()

    return PipelineComponents(extractor=extractor, transformer=transformer, sink=sink)


async def _run_runner(components: PipelineComponents, table_name: str) -> None:
    """Executa o PipelineRunner com 1 item e sem parâmetros de transformação."""
    runner = PipelineRunner(max_workers=1)
    await runner.execute(
        components=components,
        items=[1],
        extract_kwargs_mapper=lambda item: {},
        table_name=table_name,
        layer=MedallionLayer.SILVER,
    )


@pytest.mark.asyncio
async def test_runner_preserves_bulk_download_url_in_silver():
    """Bulk: o DataFrame Silver final preserva a URL de download do arquivo."""
    download_url = (
        "https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes2024.csv.zip"
    )
    raw = pl.DataFrame(
        {
            "id": [1, 2],
            "numero": [10, 20],
            "ano": [2024, 2024],
            "_source_url": [download_url, download_url],
        }
    )
    components = _make_components(raw)
    # "proposicoes" tem template de API — o caminho antigo sobrescreveria a URL.
    await _run_runner(components, DomainType.PROPOSICOES.value)

    df = _captured_silver_df(components.sink)
    assert "_source_url" in df.columns
    assert df["_source_url"].to_list() == [download_url, download_url]
    assert (df["_source_url"] != "").all()


@pytest.mark.asyncio
async def test_runner_preserves_paginated_source_url_with_page():
    """Listas paginadas: a URL com página exata sobrevive até a Silver."""
    urls = [
        f"{_CAMARA_BASE}/deputados/42/despesas?ano=2024&mes=3&pagina=1",
        f"{_CAMARA_BASE}/deputados/42/despesas?ano=2024&mes=3&pagina=2",
    ]
    raw = pl.DataFrame(
        {
            "id_deputado": [42, 42],
            "ano": [2024, 2024],
            "mes": [3, 3],
            "valorLiquido": [100.0, 200.0],
            "_source_url": urls,
        }
    )
    components = _make_components(raw)
    await _run_runner(components, DomainType.DESPESAS.value)

    df = _captured_silver_df(components.sink)
    assert df["_source_url"].to_list() == urls


@pytest.mark.asyncio
async def test_runner_does_not_overwrite_nonempty_source_url():
    """Mecanismo único: runner não sobrescreve URL não-vazia vinda da extração."""
    injected = "https://dadosabertos.camara.leg.br/api/v2/deputados/999?pagina=7"
    raw = pl.DataFrame(
        {
            "id": [123],
            "nome": ["Deputado X"],
            "_source_url": [injected],
        }
    )
    components = _make_components(raw)
    # "deputados" tem template {base}/deputados/{id} — o caminho antigo
    # sobrescreveria com .../deputados/123.
    await _run_runner(components, DomainType.DEPUTADOS.value)

    df = _captured_silver_df(components.sink)
    assert df["_source_url"][0] == injected


@pytest.mark.asyncio
async def test_runner_preserves_source_url_for_bulk_only_domain():
    """Bulk-only: domínio sem template de API não fica com _source_url zerado."""
    file_url = "https://dadosabertos.camara.leg.br/arquivos/funcionarios/csv/funcionarios.csv"
    raw = pl.DataFrame(
        {
            "codGrupo": [1],
            "nome": ["Servidor"],
            "_source_url": [file_url],
        }
    )
    components = _make_components(raw)
    await _run_runner(components, DomainType.FUNCIONARIOS.value)

    df = _captured_silver_df(components.sink)
    assert df["_source_url"][0] == file_url
    assert (df["_source_url"] != "").all()


@pytest.mark.asyncio
async def test_runner_fills_missing_source_url_via_template():
    """Fallback: sem _source_url na extração, o runner preenche via template."""
    raw = pl.DataFrame(
        {
            "id": [123],
            "nome": ["Deputado X"],
        }
    )
    components = _make_components(raw)
    await _run_runner(components, DomainType.DEPUTADOS.value)

    df = _captured_silver_df(components.sink)
    expected = SOURCE_URL_TEMPLATES[DomainType.DEPUTADOS].format(base=_CAMARA_BASE, id=123)
    assert df["_source_url"][0] == expected


@pytest.mark.asyncio
async def test_runner_fills_empty_source_url_via_template():
    """Fallback parcial: linhas com URL vazia recebem o template do domínio."""
    raw = pl.DataFrame(
        {
            "id": [1, 2],
            "nome": ["A", "B"],
            "_source_url": ["", "https://exemplo/ja/preenchida"],
        }
    )
    components = _make_components(raw)
    await _run_runner(components, DomainType.DEPUTADOS.value)

    df = _captured_silver_df(components.sink)
    expected = SOURCE_URL_TEMPLATES[DomainType.DEPUTADOS].format(base=_CAMARA_BASE, id=1)
    assert df["_source_url"].to_list() == [expected, "https://exemplo/ja/preenchida"]
