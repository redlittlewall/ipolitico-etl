"""Testes do ZIP multi-CSV do PortalTransparenciaBulkExtractor (ticket 03).

Os dumps mensais do portal (ex: módulo ``servidores``) vêm em ZIP com VÁRIOS
CSVs por mês — o ``BaseBulkExtractor`` descompacta só o primeiro. A subclasse do
portal sobrescreve ``_load_raw_df`` para extrair TODOS os CSVs e concatená-los
em diagonal (``how="diagonal_relaxed"``): colunas presentes em um arquivo e
ausentes em outro viram nulo (ex: layout pré-2020 × pós-2020).
"""

import zipfile
from unittest.mock import AsyncMock

import polars as pl
import pytest

from ipolitico.core.config import PORTAL_BULK_BASE_URL
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.extractors.portal_transparencia.bulk.bulk_extractor import (
    PortalTransparenciaBulkExtractor,
)

BULK_BASE = PORTAL_BULK_BASE_URL.rstrip("/")


@pytest.fixture(autouse=True)
def _clear_bulk_cache():
    """Limpa os caches do portal e da classe base antes de cada teste."""
    PortalTransparenciaBulkExtractor.clear_cache()
    BaseBulkExtractor.clear_cache()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.download_file = AsyncMock(return_value=True)
    return client


@pytest.mark.asyncio
async def test_extract_concatena_todos_os_csvs_do_zip(tmp_path, mock_client):
    """ZIP com 2 CSVs de colunas DIFERENTES → concat em diagonal, todas as linhas."""
    url = f"{BULK_BASE}/servidores/202401"

    async def fake_download(dest_url, dest):
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr(
                "servidores_1.csv",
                "id_servidor;nome;remuneracao_basica\n1;FULANO;1000,00\n2;CICLANO;2000,00\n",
            )
            zf.writestr(
                "servidores_2.csv",
                "id_servidor;nome;gratificacao_natalina\n3;BELTRANO;500,00\n",
            )
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(mock_client, module="servidores", bulk_dir=tmp_path)

    result = await ext.extract(year=2024, month=1)

    assert result.height == 3
    assert result["nome"].to_list() == ["FULANO", "CICLANO", "BELTRANO"]
    # id_servidor lido como String (infer_schema_length=0 → Utf8 determinístico);
    # a tipagem estrita (String→Int64) vive no transformer, não no extrator raw.
    assert result["id_servidor"].to_list() == ["1", "2", "3"]
    # Colunas de arquivos diferentes coexistem; ausência → nulo (diagonal_relaxed).
    assert result["remuneracao_basica"].to_list() == ["1000,00", "2000,00", None]
    assert result["gratificacao_natalina"].to_list() == [None, None, "500,00"]
    # _source_url é a mesma URL do dump mensal em todas as linhas.
    assert result.columns[0] == "_source_url"
    assert result["_source_url"].to_list() == [url] * 3


@pytest.mark.asyncio
async def test_extract_zip_sem_csv_retorna_vazio(tmp_path, mock_client):
    """ZIP sem arquivos (apenas diretórios) → DataFrame vazio, sem crash."""
    async def fake_download(dest_url, dest):
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("202401/", "")
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(mock_client, module="servidores", bulk_dir=tmp_path)

    result = await ext.extract(year=2024, month=1)

    assert result.is_empty()


@pytest.mark.asyncio
async def test_extract_csv_unico_sem_zip_continua_funcionando(tmp_path, mock_client):
    """Dump CSV direto (sem ZIP) continua pelo caminho da classe base."""
    async def fake_download(dest_url, dest):
        with open(dest, "w", encoding="utf-8") as f:
            f.write("id_servidor;nome\n1;FULANO\n")
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(mock_client, module="servidores", bulk_dir=tmp_path)

    result = await ext.extract(year=2024, month=1)

    assert not result.is_empty()
    assert result["nome"].to_list() == ["FULANO"]
    assert result.columns[0] == "_source_url"


@pytest.mark.asyncio
async def test_extract_200_com_corpo_html_devolve_vazio(tmp_path, mock_client):
    """200 com corpo HTML (página de erro do host) → vazio, sem injetar lixo.

    Dumps do portal têm nome de segmento (ex: "202401"), sem extensão ".zip" —
    o guard do base por extensão não dispara. O override detecta o corpo HTML
    pelo primeiro byte ("<") antes do read_csv.
    """
    async def fake_download(dest_url, dest):
        with open(dest, "w", encoding="utf-8") as f:
            f.write("<html><body>Serviço indisponível</body></html>")
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(mock_client, module="servidores", bulk_dir=tmp_path)

    result = await ext.extract(year=2024, month=1)

    assert result.is_empty()
    assert "_source_url" not in result.columns
