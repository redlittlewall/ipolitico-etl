"""Testes do PortalTransparenciaBulkExtractor (download-de-dados → ZIP → CSV).

Prior art: ``tests/extractors/camara/bulk/test_bulk_extractor.py`` — a diferença
é que o portal constrói a URL por convenção de segmento (``/download-de-dados/
{módulo}[/{YYYY}[MM]]``) e baixa para um diretório persistente (resume via Range
no cliente), não para um temp dir descartável.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.core.config import PORTAL_BULK_BASE_URL
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.extractors.portal_transparencia.bulk.bulk_extractor import (
    PortalTransparenciaBulkExtractor,
)

# Padrão real do portal: /download-de-dados/{módulo}/{YYYYMM}
BULK_BASE = PORTAL_BULK_BASE_URL.rstrip("/")


@pytest.fixture(autouse=True)
def _clear_bulk_cache():
    """Limpa os caches do portal e da classe base antes de cada teste.

    O cache do portal é próprio (``PortalTransparenciaBulkExtractor._bulk_cache``);
    o da base (Câmara) também é limpo para que o teste de isolamento parta de um
    estado vazio independentemente da ordem de execução do pytest.
    """
    PortalTransparenciaBulkExtractor.clear_cache()
    BaseBulkExtractor.clear_cache()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.download_file = AsyncMock(return_value=True)
    return client


# ── _build_url: convenção de segmento ────────────────────────────────────────


def test_build_url_snapshot_module():
    """Sem ano/mês → URL do snapshot: /download-de-dados/{módulo}."""
    ext = PortalTransparenciaBulkExtractor(None, module="servidores")
    assert ext._build_url() == f"{BULK_BASE}/servidores"


def test_build_url_with_year():
    """Com ano → /download-de-dados/{módulo}/{YYYY} (cobertura anual)."""
    ext = PortalTransparenciaBulkExtractor(None, module="servidores")
    assert ext._build_url(year=2024) == f"{BULK_BASE}/servidores/2024"


def test_build_url_with_year_month():
    """Com ano+mês → /download-de-dados/{módulo}/{YYYYMM} (dump mensal)."""
    ext = PortalTransparenciaBulkExtractor(None, module="servidores")
    assert ext._build_url(year=2024, month=1) == f"{BULK_BASE}/servidores/202401"


def test_build_url_month_requires_year():
    """Mês sem ano → erro explícito (URL YYYYMM não faria sentido)."""
    ext = PortalTransparenciaBulkExtractor(None, module="servidores")
    with pytest.raises(ValueError, match="month exige 'year'"):
        ext._build_url(month=3)


def test_build_url_rejects_invalid_month():
    """Mês fora de 1-12 → erro (mesma regra defensiva do base); evita 404 silencioso."""
    ext = PortalTransparenciaBulkExtractor(None, module="servidores")
    with pytest.raises(ValueError, match="Mês inválido"):
        ext._build_url(year=2024, month=13)


# ── extract: download → CSV → _source_url ────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_download_failure_returns_empty(mock_client):
    """Download falhou (404 → False no cliente) → lista vazia, sem _source_url."""
    mock_client.download_file.return_value = False
    ext = PortalTransparenciaBulkExtractor(mock_client, module="servidores")

    result = await ext.extract(year=2024, month=1)

    assert result.is_empty()
    assert "_source_url" not in result.columns


@pytest.mark.asyncio
async def test_extract_downloads_to_persistent_bulk_dir(tmp_path, mock_client):
    """
    O portal baixa para o diretório de bulk persistente (não temp descartável):
    o arquivo fica em disco após o extract, habilitando resume via Range no
    cliente em execuções futuras.
    """

    async def fake_download(url, dest):
        with open(dest, "w", encoding="utf-8") as f:
            f.write("id;nome\n1;FULANO\n")
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(mock_client, module="servidores", bulk_dir=tmp_path)

    result = await ext.extract(year=2024, month=1)

    assert not result.is_empty()
    assert result.columns[0] == "_source_url"
    expected_url = f"{BULK_BASE}/servidores/202401"
    assert result["_source_url"][0] == expected_url
    # Arquivo persistido com o nome do último segmento da URL (sem .zip).
    assert (tmp_path / "202401").exists()


@pytest.mark.asyncio
async def test_extract_unzips_portal_zip(tmp_path, mock_client):
    """
    ZIP sem extensão .zip no nome (ex: segmento "202401"): o extractor detecta
    pelo magic byte (``zipfile.is_zipfile``) e descompacta o CSV interno.
    """
    import zipfile

    async def fake_download(url, dest):
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("servidores.csv", "id;nome\n1;FULANO\n")
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(mock_client, module="servidores", bulk_dir=tmp_path)

    result = await ext.extract(year=2024, month=1)

    assert not result.is_empty()
    assert result["nome"].to_list() == ["FULANO"]
    assert result.columns[0] == "_source_url"


# ── cache: namespacing por subclasse (colisão Câmara × portal) ───────────────


@pytest.mark.asyncio
async def test_portal_cache_isolated_from_base_cache(tmp_path, mock_client):
    """
    O cache do portal é um dict próprio (não o da classe base): um módulo
    "despesas" do portal não pode colidir com o domínio "despesas" da Câmara
    no cache compartilhado.
    """

    async def fake_download(url, dest):
        with open(dest, "w", encoding="utf-8") as f:
            f.write("id;nome\n1;FULANO\n")
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(mock_client, module="despesas", bulk_dir=tmp_path)

    result = await ext.extract(year=2024)

    assert result["nome"].to_list() == ["FULANO"]
    # O portal populou o cache próprio; o da classe base (Câmara) permanece vazio.
    assert PortalTransparenciaBulkExtractor._bulk_cache != {}
    assert BaseBulkExtractor._bulk_cache == {}
