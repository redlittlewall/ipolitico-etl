"""Issue 04 — FOLHA_PAGAMENTO: URLs mensais, parse ISO-8859-1 e 404 → vazio.

O consolidado mensal da folha da Câmara é o primeiro domínio bulk **mensal**:
1 arquivo por (ano, mês), nomes de mês sem acento na URL, codificação
ISO-8859-1 e meses com 404 (2011/2015/2022) tratados como ausência (lista
vazia), nunca como exceção.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import polars as pl
import pytest

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "folha_pagamento_2026-07.csv"
BASE_URL = (
    "https://www2.camara.leg.br/transparencia/recursos-humanos/remuneracao/"
    "relatorios-consolidados-por-ano-e-mes"
)


@pytest.fixture(autouse=True)
def _clear_bulk_cache():
    """Limpa cache compartilhado do BaseBulkExtractor antes de cada teste."""
    BaseBulkExtractor.clear_cache()


class TestBuildUrlMensal:
    """URL de download: 1 arquivo por (ano, mês), nomes sem acento."""

    def test_url_julho(self):
        ext = BaseBulkExtractor(None, domain_name="folha_pagamento")
        url = ext._build_url(year=2026, month=7)
        assert url == f"{BASE_URL}/2026/julho-de-2026-csv"

    def test_url_nomes_de_mes_sem_acento(self):
        """março vira 'marco' na URL (sem acento) — convenção da fonte."""
        ext = BaseBulkExtractor(None, domain_name="folha_pagamento")
        assert ext._build_url(year=2026, month=3) == f"{BASE_URL}/2026/marco-de-2026-csv"
        assert ext._build_url(year=2026, month=1) == f"{BASE_URL}/2026/janeiro-de-2026-csv"
        assert ext._build_url(year=2026, month=12) == f"{BASE_URL}/2026/dezembro-de-2026-csv"

    def test_url_exige_month(self):
        ext = BaseBulkExtractor(None, domain_name="folha_pagamento")
        with pytest.raises(ValueError, match="month"):
            ext._build_url(year=2026)

    def test_url_exige_year(self):
        ext = BaseBulkExtractor(None, domain_name="folha_pagamento")
        with pytest.raises(ValueError, match="year"):
            ext._build_url(month=7)


@pytest.mark.asyncio
async def test_extract_parse_iso8859_1_fixture():
    """Parse real de fixture local ISO-8859-1: colunas acentuadas preservadas."""
    client = AsyncMock()

    async def fake_download(url, dest):
        Path(dest).write_bytes(FIXTURE.read_bytes())
        return True

    client.download_file.side_effect = fake_download
    ext = BaseBulkExtractor(client, domain_name="folha_pagamento")
    result = await ext.extract(year=2026, month=7)

    assert not result.is_empty()
    assert result.height == 3
    assert "Cargo Individualizado do Servidor" in result.columns
    cargos = result["Cargo Individualizado do Servidor"].to_list()
    assert "Deputado 42" in cargos

    expected_url = f"{BASE_URL}/2026/julho-de-2026-csv"
    assert result["_source_url"].to_list() == [expected_url] * 3


@pytest.mark.asyncio
async def test_extract_404_vira_lista_vazia():
    """404 (lacuna) → lista vazia, nunca exceção (2011/2015/2022)."""
    client = AsyncMock()
    client.download_file.return_value = False
    ext = BaseBulkExtractor(client, domain_name="folha_pagamento")
    result = await ext.extract(year=2022, month=1)

    assert result.is_empty()
    assert "_source_url" not in result.columns


@pytest.mark.asyncio
async def test_extract_exige_month():
    """Sem mês, o extrator recusa (mês é obrigatório para domínios mensais)."""
    client = AsyncMock()
    client.download_file.return_value = True
    ext = BaseBulkExtractor(client, domain_name="folha_pagamento")
    with pytest.raises(ValueError, match="month"):
        await ext.extract(year=2026)


@pytest.mark.asyncio
async def test_extract_cache_separa_por_mes():
    """Cache é chaveado por (domínio, ano, mês) — meses distintos não colidem."""
    client = AsyncMock()

    async def fake_download(url, dest):
        Path(dest).write_bytes(FIXTURE.read_bytes())
        return True

    client.download_file.side_effect = fake_download
    ext = BaseBulkExtractor(client, domain_name="folha_pagamento")

    with patch(
        "ipolitico.extractors.camara.bulk.base_bulk.pl.read_csv", wraps=pl.read_csv
    ) as mock_read:
        await ext.extract(year=2026, month=6)
        await ext.extract(year=2026, month=6)  # cache hit
        await ext.extract(year=2026, month=7)  # outro mês → novo parse

    assert mock_read.call_count == 2
