"""
Testes unitários do fluxo BaseBulkExtractor (download → ZIP opcional → read_csv).
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import polars as pl
import pytest
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class UnmappedBulk(BaseBulkExtractor):
    domain_name = "dominio_fantasma"


class MissingYearBulk(BaseBulkExtractor):
    domain_name = "despesas"


class EmptyDomainBulk(BaseBulkExtractor):
    domain_name = ""


class ValidZipBulk(BaseBulkExtractor):
    domain_name = "despesas"


class ValidCsvBulk(BaseBulkExtractor):
    domain_name = "deputados"


class DummyBulkExtractor(BaseBulkExtractor):
    """Domínio não registrado; URL fixa termina em .zip para exercitar o ramo ZIP."""

    domain_name = "dummy"

    def _build_url(self, year=None):
        return "http://dadosabertos.camara.leg.br/arquivos/dummy/csv/dummy.csv.zip"


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.download_file = AsyncMock(return_value=True)
    return client


@pytest.mark.asyncio
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.read_csv")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.ZipFile")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.is_zipfile")
async def test_base_bulk_extraction_flow_zip(
    mock_is_zipfile, mock_zipfile, mock_read_csv, mock_client
):
    mock_is_zipfile.return_value = True

    mock_zip_instance = MagicMock()
    mock_zip_instance.namelist.return_value = ["dummy_extraido.csv"]
    mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

    df_sujo = pl.DataFrame(
        {
            'ï»¿"id"': [1, 2],
            "nome": ["A", "B"],
        }
    )
    mock_read_csv.return_value = df_sujo

    ext = DummyBulkExtractor(mock_client)
    result = await ext.extract()

    mock_client.download_file.assert_called_once()
    mock_zip_instance.extract.assert_called_once_with("dummy_extraido.csv", ANY)

    assert "id" in result.columns
    assert 'ï»¿"id"' not in result.columns


def test_base_bulk_build_url_unmapped():
    ext = UnmappedBulk(None)
    with pytest.raises(ValueError, match="não mapeado no registry"):
        ext._build_url()


def test_base_bulk_build_url_missing_year():
    ext = MissingYearBulk(None)
    with pytest.raises(ValueError, match="exige o parâmetro 'year'"):
        ext._build_url()


@pytest.mark.asyncio
async def test_base_bulk_extract_missing_domain():
    ext = EmptyDomainBulk(None)
    with pytest.raises(NotImplementedError, match="domain_name deve ser definido"):
        await ext.extract()


@pytest.mark.asyncio
async def test_base_bulk_extract_download_fails():
    client = AsyncMock()
    client.download_file.return_value = False
    ext = ValidCsvBulk(client)

    result = await ext.extract()

    assert result.is_empty()


@pytest.mark.asyncio
async def test_base_bulk_extract_bad_zip_file():
    client = AsyncMock()

    async def fake_download(url, dest):
        with open(dest, "w", encoding="utf-8") as f:
            f.write("Isto não é um arquivo ZIP válido. É um HTML de erro do NGINX.")
        return True

    client.download_file.side_effect = fake_download
    ext = ValidZipBulk(client)

    result = await ext.extract(year=2026)

    assert result.is_empty()


@pytest.mark.asyncio
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.read_csv")
async def test_base_bulk_extract_csv_parsing_exception(mock_read_csv):
    client = AsyncMock()
    client.download_file.return_value = True
    mock_read_csv.side_effect = Exception("Erro catastrófico de disco simulado")

    ext = ValidCsvBulk(client)

    result = await ext.extract()

    assert result.is_empty()
