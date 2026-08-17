"""Issue 04 — PipelineRunner + BaseBulkExtractor mockado + fixture ISO-8859-1.

Valida o fluxo completo do runner com o extrator bulk real lendo a fixture
local (ISO-8859-1): parse, normalização no transformer e ``_source_url``
replayável preservada na Silver — incluindo ``Cargo = "Deputado {id}"``
(grupo "Parlamentar") para a atribuição downstream.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest

from ipolitico.core.constants import DomainType, MedallionLayer
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.pipeline.builder import PipelineComponents
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.transformers.camara.institutional_transformer import (
    CamaraFolhaPagamentoTransformer,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "folha_pagamento_2026-07.csv"
BASE_URL = (
    "https://www2.camara.leg.br/transparencia/recursos-humanos/remuneracao/"
    "relatorios-consolidados-por-ano-e-mes"
)


@pytest.fixture(autouse=True)
def _clear_bulk_cache():
    """Limpa cache compartilhado do BaseBulkExtractor antes de cada teste."""
    BaseBulkExtractor.clear_cache()


def _captured_silver_df(sink) -> pl.DataFrame:
    """Retorna o DataFrame Silver final entregue ao sink.save na 1ª chamada."""
    return sink.save.await_args_list[0].kwargs["df"]


@pytest.mark.asyncio
async def test_runner_folha_fixture_iso8859_1():
    """Fluxo completo: fixture latin-1 → Silver com cargo Deputado preservado."""
    client = AsyncMock()

    async def fake_download(url, dest):
        Path(dest).write_bytes(FIXTURE.read_bytes())
        return True

    client.download_file.side_effect = fake_download
    extractor = BaseBulkExtractor(client, domain_name=DomainType.FOLHA_PAGAMENTO.value)

    transformer = CamaraFolhaPagamentoTransformer()
    sink = MagicMock()
    sink.save = AsyncMock()
    sink.flush = AsyncMock()

    components = PipelineComponents(extractor=extractor, transformer=transformer, sink=sink)

    runner = PipelineRunner(max_workers=1)
    await runner.execute(
        components=components,
        items=[{"year": 2026, "month": 7}],
        extract_kwargs_mapper=lambda job: {"year": job["year"], "month": job["month"]},
        table_name=DomainType.FOLHA_PAGAMENTO.value,
        layer=MedallionLayer.SILVER,
    )

    df = _captured_silver_df(sink)
    assert df.height == 3
    assert df["cargo"].to_list() == ["Deputado 42", "Deputado 7", "Servidor"]
    assert df["grupo_funcional"].to_list()[0] == "Parlamentar"
    assert df["remuneracao_fixa"].dtype == pl.Float64
    assert df["remuneracao_fixa"].to_list()[0] == 39293.32

    expected_url = f"{BASE_URL}/2026/julho-de-2026-csv"
    assert df["_source_url"].to_list() == [expected_url] * 3
    assert (df["_source_url"] != "").all()
