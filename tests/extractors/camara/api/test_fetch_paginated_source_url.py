"""
Testes de página exata no ``_source_url`` de listas paginadas (Câmara).

A API da Câmara não devolve a página em cada registro; o
``fetch_paginated`` deve marcar cada registro com ``_source_page`` e o
``_inject_source_url`` deve traduzir isso em ``pagina=N`` na URL de auditoria
para listas sem ID único. Para listas com ID (ex: deputados), a URL de
detalhe continua sendo a melhor forma de replay — sem ``pagina``.
"""

from unittest.mock import AsyncMock

import polars as pl
import pytest

from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor
from ipolitico.extractors.camara.api.deputado_child import DiscursosExtractor
from ipolitico.extractors.camara.api.deputados import DeputadosExtractor
from ipolitico.extractors.camara.api.despesas import DespesasExtractor


class _ConcreteCamaraBase(CamaraBaseExtractor):
    """Subclasse concreta mínima para exercitar o fetch_paginated isolado."""

    async def extract(self, **kwargs):
        return pl.DataFrame()


@pytest.fixture
def mock_client():
    """Cliente HTTP mockado da API Câmara, sem rede, para os testes."""
    client = AsyncMock()
    client.BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
    return client


@pytest.fixture
def small_page_size(monkeypatch):
    """Reduz a página da API Câmara para testes sem gerar 1000 registros."""
    monkeypatch.setattr("ipolitico.extractors.camara.api.camara_base.CAMARA_PAGE_SIZE", 5)
    return 5


@pytest.mark.asyncio
async def test_fetch_paginated_marks_source_page(mock_client, small_page_size):
    """fetch_paginated deve marcar cada registro com a página de origem."""
    page1 = [{"id": i} for i in range(1, small_page_size + 1)]
    page2 = [{"id": 99}]
    mock_client.fetch.side_effect = [page1, page2]

    ext = _ConcreteCamaraBase(client=mock_client)
    data = await ext.fetch_paginated("deputados", {"itens": small_page_size})

    assert len(data) == small_page_size + 1
    assert data[0]["_source_page"] == 1
    assert data[-1]["_source_page"] == 2


@pytest.mark.asyncio
async def test_despesas_multipage_source_url_includes_page(mock_client, small_page_size):
    """Lista paginada sem ID único: _source_url deve carregar pagina=N por registro."""
    page1 = [{"tipoDespesa": "PASSAGEM", "valorLiquido": 100.0}] * small_page_size
    page2 = [{"tipoDespesa": "HOSPEDAGEM", "valorLiquido": 200.0}]
    mock_client.fetch.side_effect = [page1, page2]

    ext = DespesasExtractor(client=mock_client)
    df = await ext.extract(deputado_id=42, year=2024)

    assert df.height == small_page_size + 1
    urls = df["_source_url"].to_list()
    assert all("deputados/42/despesas" in u for u in urls)
    assert all("pagina=1" in u for u in urls[:small_page_size])
    assert "pagina=2" in urls[-1]
    assert "ano=2024" in urls[-1]
    # A coluna interna de página não deve vazar para o DataFrame de saída.
    assert "_source_page" not in df.columns


@pytest.mark.asyncio
async def test_deputados_source_url_detail_without_page(mock_client, small_page_size):
    """Lista com ID único: _source_url aponta direto para o recurso, sem pagina."""
    page1 = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}]
    mock_client.fetch.return_value = page1

    ext = DeputadosExtractor(client=mock_client)
    df = await ext.extract()

    urls = df["_source_url"].to_list()
    assert urls == [
        "https://dadosabertos.camara.leg.br/api/v2/deputados/1",
        "https://dadosabertos.camara.leg.br/api/v2/deputados/2",
    ]
    assert all("pagina" not in u for u in urls)
    assert "_source_page" not in df.columns


@pytest.mark.asyncio
async def test_single_page_despesas_source_url_includes_page_one(mock_client, small_page_size):
    """Página única ainda registra pagina=1, mantendo a URL replayável."""
    page1 = [{"tipoDespesa": "PASSAGEM", "valorLiquido": 100.0}]
    mock_client.fetch.return_value = page1

    ext = DespesasExtractor(client=mock_client)
    df = await ext.extract(deputado_id=7, year=2024, month=3)

    url = df["_source_url"][0]
    assert "deputados/7/despesas" in url
    assert "ano=2024" in url
    assert "mes=3" in url
    assert "pagina=1" in url


@pytest.mark.asyncio
async def test_discursos_chunked_window_url_replayable_per_chunk(mock_client, small_page_size):
    """Janela > 4 anos: cada chunk carrega seu dataInicio/dataFim + pagina local.

    Sem isso, a página reiniciada em cada chunk combinada à janela completa
    apontaria para a página errada ao reabrir a URL (issue 01).
    """
    chunk1_page1 = [{"codigo": i} for i in range(small_page_size)]
    chunk1_page2 = [{"codigo": 999}]
    chunk2_page1 = [{"codigo": 1111}]
    mock_client.fetch.side_effect = [chunk1_page1, chunk1_page2, chunk2_page1]

    ext = DiscursosExtractor(client=mock_client)
    df = await ext.extract(deputado_id=7, start_date="2010-01-01", end_date="2017-12-31")

    assert df.height == small_page_size + 2
    urls = df["_source_url"].to_list()
    # Chunk 1 (2010-01-01 a 2013-12-31): pagina=1 nas 5 primeiras, pagina=2 na última.
    assert all(
        "dataInicio=2010-01-01" in u and "dataFim=2013-12-31" in u for u in urls[:small_page_size]
    )
    assert all("pagina=1" in u for u in urls[:small_page_size])
    assert "dataInicio=2010-01-01" in urls[small_page_size]
    assert "pagina=2" in urls[small_page_size]
    # Chunk 2 (2014-01-01 a 2017-12-31): pagina reinicia em 1 com as datas do chunk.
    assert "dataInicio=2014-01-01" in urls[-1]
    assert "dataFim=2017-12-31" in urls[-1]
    assert "pagina=1" in urls[-1]
    assert (df["id_deputado"] == 7).all()
    assert "_source_page" not in df.columns
