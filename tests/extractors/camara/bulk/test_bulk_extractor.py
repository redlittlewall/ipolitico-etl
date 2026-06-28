"""
Testes unitários do fluxo BaseBulkExtractor (download → ZIP opcional → read_csv).
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import polars as pl
import pytest

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


@pytest.fixture(autouse=True)
def _clear_bulk_cache():
    """Limpa cache compartilhado do BaseBulkExtractor antes de cada teste."""
    BaseBulkExtractor.clear_cache()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.download_file = AsyncMock(return_value=True)
    return client


@pytest.mark.asyncio
@patch(
    "ipolitico.extractors.camara.bulk.base_bulk.BULK_REGISTRY",
    new={
        "dummy": {
            "requires_year": False,
            "url_template": "http://dadosabertos.camara.leg.br/arquivos/dummy/csv/dummy.csv.zip",
            "bulk_granularity": "snapshot",
            "bulk_filter_date_column": None,
        },
    },
)
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

    ext = BaseBulkExtractor(mock_client, domain_name="dummy")
    result = await ext.extract()

    mock_client.download_file.assert_called_once()
    mock_zip_instance.extract.assert_called_once_with("dummy_extraido.csv", ANY)

    assert "id" in result.columns
    assert 'ï»¿"id"' not in result.columns


@pytest.mark.asyncio
@patch(
    "ipolitico.extractors.camara.bulk.base_bulk.BULK_REGISTRY",
    new={
        "dummy": {
            "requires_year": False,
            "url_template": "http://dadosabertos.camara.leg.br/arquivos/dummy/csv/dummy.csv.zip",
            "bulk_granularity": "snapshot",
            "bulk_filter_date_column": None,
            "schema_overrides": {"id": pl.Int64, "ano": pl.Int32},
        },
    },
)
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.read_csv")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.ZipFile")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.is_zipfile")
async def test_extract_passes_schema_overrides_to_read_csv(
    mock_is_zipfile, mock_zipfile, mock_read_csv, mock_client
):
    """
    [SCHEMA OVERRIDES] Verifica que o extract() encaminha o schema_overrides
    do BULK_REGISTRY para o pl.read_csv(), eliminando a necessidade de
    conversão posterior nos transformers.
    """
    mock_is_zipfile.return_value = True
    mock_zip_instance = MagicMock()
    mock_zip_instance.namelist.return_value = ["dummy.csv"]
    mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

    df_bruto = pl.DataFrame({"id": ["1"], "nome": ["A"]})
    mock_read_csv.return_value = df_bruto

    ext = BaseBulkExtractor(mock_client, domain_name="dummy")
    await ext.extract()

    mock_read_csv.assert_called_once()
    _args, kwargs = mock_read_csv.call_args
    assert kwargs.get("schema_overrides") == {"id": pl.Int64, "ano": pl.Int32}


@patch(
    "ipolitico.extractors.camara.bulk.base_bulk.BULK_REGISTRY",
    new={
        "test_url_template": {
            "requires_year": False,
            "url_template": "https://dadosabertos.camara.leg.br/arquivos/teste/csv/teste.csv",
            "bulk_granularity": "snapshot",
            "bulk_filter_date_column": None,
        },
    },
)
def test_base_bulk_build_url_uses_url_template():
    """
    [URL TEMPLATE] Verifica que o _build_url() lê o campo ``url_template``
    do BULK_REGISTRY (em substituição ao campo ``url``).
    """
    ext = BaseBulkExtractor(None, domain_name="test_url_template")
    url = ext._build_url()
    expected = "https://dadosabertos.camara.leg.br/arquivos/teste/csv/teste.csv"
    assert url == expected


@patch(
    "ipolitico.extractors.camara.bulk.base_bulk.BULK_REGISTRY",
    new={
        "test_yearly": {
            "requires_year": True,
            "url_template": "https://example.com/data-{year}.csv",
            "bulk_granularity": "year",
            "bulk_filter_date_column": "data",
        },
    },
)
def test_base_bulk_build_url_year_template():
    """
    [URL TEMPLATE YEAR] Verifica que _build_url formata {year} no template.
    """
    ext = BaseBulkExtractor(None, domain_name="test_yearly")
    url = ext._build_url(year=2026)
    assert url == "https://example.com/data-2026.csv"


def test_base_bulk_build_url_unmapped():
    ext = BaseBulkExtractor(None, domain_name="dominio_fantasma")
    with pytest.raises(ValueError, match="não mapeado no registry"):
        ext._build_url()


def test_base_bulk_build_url_missing_year():
    ext = BaseBulkExtractor(None, domain_name="despesas")
    with pytest.raises(ValueError, match="exige o parâmetro 'year'"):
        ext._build_url()


@pytest.mark.asyncio
async def test_base_bulk_extract_missing_domain():
    ext = BaseBulkExtractor(None, domain_name="")
    with pytest.raises(NotImplementedError, match="domain_name deve ser fornecido no construtor"):
        await ext.extract()


@pytest.mark.asyncio
async def test_base_bulk_extract_download_fails():
    client = AsyncMock()
    client.download_file.return_value = False
    ext = BaseBulkExtractor(client, domain_name="grupos")

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
    ext = BaseBulkExtractor(client, domain_name="despesas")

    result = await ext.extract(year=2026)

    assert result.is_empty()


@pytest.mark.asyncio
@patch(
    "ipolitico.extractors.camara.bulk.base_bulk.BULK_REGISTRY",
    new={
        "orgaos_test": {
            "requires_year": False,
            "url_template": ("https://dadosabertos.camara.leg.br/arquivos/orgaos/csv/orgaos.csv"),
            "bulk_granularity": "snapshot",
            "bulk_filter_date_column": None,
            "schema_overrides": {"idOrgao": pl.Int64},
            "rename_map": {"idOrgao": "id"},
        },
    },
)
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.read_csv")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.ZipFile")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.is_zipfile")
async def test_extract_applies_rename_map(
    mock_is_zipfile, mock_zipfile, mock_read_csv, mock_client
):
    """
    [RENAME MAP] Verifica que o extract() aplica o rename_map do BULK_REGISTRY
    após a leitura do CSV, renomeando colunas como idOrgao → id.
    """
    mock_is_zipfile.return_value = True
    mock_zip_instance = MagicMock()
    mock_zip_instance.namelist.return_value = ["orgaos.csv"]
    mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

    # CSV com coluna idOrgao em vez de id
    df_bruto = pl.DataFrame(
        {"idOrgao": [1, 2], "sigla": ["CD", "SF"], "nome": ["Câmara", "Senado"]}
    )
    mock_read_csv.return_value = df_bruto

    ext = BaseBulkExtractor(mock_client, domain_name="orgaos_test")
    result = await ext.extract()

    assert "id" in result.columns
    assert "idOrgao" not in result.columns
    assert result["id"].to_list() == [1, 2]


@pytest.mark.asyncio
@patch(
    "ipolitico.extractors.camara.bulk.base_bulk.BULK_REGISTRY",
    new={
        "cache_test": {
            "requires_year": False,
            "url_template": "https://dadosabertos.camara.leg.br/arquivos/cachetest/csv/data.csv",
            "bulk_granularity": "snapshot",
            "bulk_filter_date_column": None,
        },
    },
)
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.read_csv")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.ZipFile")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.is_zipfile")
async def test_extract_cache_hit_reuses_dataframe(
    mock_is_zipfile, mock_zipfile, mock_read_csv, mock_client
):
    """
    [CACHE] Verifica que o cache compartilhado funciona: ao chamar extract()
    duas vezes com o mesmo domain_name, a segunda chamada retorna dados sem
    baixar/parsear novamente (read_csv é chamado só na primeira).
    """
    mock_is_zipfile.return_value = True
    mock_zip_instance = MagicMock()
    mock_zip_instance.namelist.return_value = ["data.csv"]
    mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

    df_original = pl.DataFrame({"id": [1, 2, 3], "nome": ["A", "B", "C"]})
    mock_read_csv.return_value = df_original

    ext = BaseBulkExtractor(mock_client, domain_name="cache_test")

    # Primeira chamada → download + read_csv
    result1 = await ext.extract()
    mock_read_csv.assert_called_once()
    assert result1.height == 3

    # Segunda chamada → cache hit, read_csv NÃO é chamado novamente
    result2 = await ext.extract()
    mock_read_csv.assert_called_once()  # ainda 1x
    assert result2.height == 3
    assert result2["id"].to_list() == [1, 2, 3]


@pytest.mark.asyncio
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.read_csv")
async def test_base_bulk_extract_csv_parsing_exception(mock_read_csv):
    client = AsyncMock()
    client.download_file.return_value = True
    mock_read_csv.side_effect = Exception("Erro catastrófico de disco simulado")

    ext = BaseBulkExtractor(client, domain_name="grupos")

    result = await ext.extract()

    assert result.is_empty()
