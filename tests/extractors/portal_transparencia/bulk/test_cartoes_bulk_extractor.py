"""Testes do PortalCartoesBulkExtractor — dump mensal multi-módulo (ticket 04).

ROTA DUPLA (FULL_LOAD): o histórico de cartões vem de TRÊS módulos bulk
(``cpgf``/``cpcc``/``cpdc``) em ``/download-de-dados/{módulo}/{YYYYMM}``.
Validação real: alguns meses não publicam todos os módulos (cpcc frequentemente
ausente → 403 AccessDenied do S3 → ``download_file`` devolve ``False``), e o
host de dumps tem WAF. O extrator pula o módulo indisponível e concatena os
demais (``pl.concat(how="diagonal_relaxed")`` — os CSVs têm colunas
heterogêneas; as extras do cpdc ficam fora do contrato Silver).
"""

import zipfile
from unittest.mock import AsyncMock

import polars as pl
import pytest

from ipolitico.core.portal_transparencia_client import (
    PortalTransparenciaAPIError,
    PortalTransparenciaClient,
    PortalTransparenciaWAFError,
)
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.extractors.portal_transparencia.bulk.bulk_extractor import (
    PortalTransparenciaBulkExtractor,
)
from ipolitico.extractors.portal_transparencia.bulk.cartoes_bulk_extractor import (
    PortalCartoesBulkExtractor,
)

HEADER_CPGF = (
    "CÓDIGO ÓRGÃO SUPERIOR;NOME ÓRGÃO SUPERIOR;CÓDIGO ÓRGÃO;NOME ÓRGÃO;"
    "CÓDIGO UNIDADE GESTORA;NOME UNIDADE GESTORA;ANO EXTRATO;MÊS EXTRATO;"
    "CPF PORTADOR;NOME PORTADOR;CNPJ OU CPF FAVORECIDO;NOME FAVORECIDO;"
    "TRANSAÇÃO;DATA TRANSAÇÃO;VALOR TRANSAÇÃO"
)
ROW_CPGF = (
    "63000;Advocacia-Geral da União;63000;Advocacia-Geral da União;110161;"
    "SUPERINTENDENCIA REG. DE ADMIN. DA 1ª REGIAO;2024;01;***.195.852-**;"
    "JOSE UELISSON ALVES LEITE;79379491017744;HAVAN S.A;COMPRA A/V - R$ - APRES;"
    "07/12/2023;607,41"
)
HEADER_CPDC = (
    "CÓDIGO ÓRGÃO SUPERIOR;NOME ÓRGÃO SUPERIOR;CÓDIGO ÓRGÃO;NOME ÓRGÃO;"
    "CÓDIGO UNIDADE GESTORA;NOME UNIDADE GESTORA;ANO EXTRATO;MÊS EXTRATO;"
    "CPF PORTADOR;NOME PORTADOR;CNPJ OU CPF FAVORECIDO;NOME FAVORECIDO;"
    "EXECUTOR DESPESA;NÚMERO CONVÊNIO;CÓDIGO CONVENENTE;NOME CONVENENTE;"
    "REPASSE;TRANSAÇÃO;DATA TRANSAÇÃO;VALOR TRANSAÇÃO"
)
ROW_CPDC = (
    "53000;Ministério da Integração e do Desenvolvimento;53000;Ministério da "
    "Integração e do Desenvolvimento Regional;530012;SECRETARIA NACIONAL "
    "PROTECAO E DEFESA CIVIL;2025;06;***.626.932-**;CARLOS ARMANDO DE SOUZA "
    "ALVES;20548185000180;AUTO POSTO XIS IMPORTACAO E EXPORTACAO LTDA;"
    "BRASILEIA / AC;671987;04508933000145;MUNICIPIO DE BRASILEIA;Não;"
    "COMPRA A/V - R$ - APRES;30/04/2025;70922,36"
)
HEADER_CPCC = (
    "CÓDIGO ÓRGÃO SUPERIOR;NOME ÓRGÃO SUPERIOR;CÓDIGO ÓRGÃO;NOME ÓRGÃO;"
    "CÓDIGO UNIDADE GESTORA;NOME UNIDADE GESTORA;ANO EXTRATO;MÊS EXTRATO;"
    "TIPO AQUISIÇÃO;CNPJ OU CPF FAVORECIDO;NOME FAVORECIDO;TRANSAÇÃO;"
    "DATA TRANSAÇÃO;VALOR TRANSAÇÃO"
)
ROW_CPCC = (
    "26000;Ministério da Educação;26417;Instituto Federal de Educação, Ciência "
    "e Tecnologia da Paraíba;155895;IFPB - CAMPUS CATOLE DO ROCHA;2024;01;"
    "Aquisição de Passagem Aérea;01976704000167;SYNCTECH SOLUCOES EM INFORMATICA "
    "LTDA;COMPRA A/V - R$ - APRES;28/11/2023;190,00"
)


def _write_module_zip(dest, member: str, content: str) -> None:
    """Escreve o ZIP mensal real do módulo (CSV latin-1 — encoding do registry)."""
    with zipfile.ZipFile(dest, "w") as zf:
        zf.writestr(member, content.encode("latin-1"))


@pytest.fixture(autouse=True)
def _clear_bulk_caches():
    """Limpa os caches do portal, do base e o próprio do cartões."""
    PortalTransparenciaBulkExtractor.clear_cache()
    BaseBulkExtractor.clear_cache()
    PortalCartoesBulkExtractor._module_cache.clear()


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=PortalTransparenciaClient)
    client.download_file = AsyncMock(return_value=True)
    return client


@pytest.fixture
def ext(mock_client, tmp_path):
    return PortalCartoesBulkExtractor(mock_client, domain_name="cg_cartoes", bulk_dir=tmp_path)


@pytest.mark.asyncio
async def test_build_module_url(ext):
    """URL por módulo na convenção de segmento; mês inválido levanta ValueError."""
    assert ext._build_module_url("cpgf", 2025, 6).endswith("/download-de-dados/cpgf/202506")
    assert ext._build_module_url("cpdc", 2024, 1).endswith("/download-de-dados/cpdc/202401")
    with pytest.raises(ValueError):
        ext._build_module_url("cpgf", 2025, 13)


@pytest.mark.asyncio
async def test_extract_pula_modulo_faltante_e_concatena(ext, mock_client):
    """cpcc ausente (download_file → False) é pulado; cpgf+cpdc concatenados."""

    async def fake_download(url, dest):
        if "/cpcc/" in url:
            return False
        if "/cpgf/" in url:
            _write_module_zip(dest, "202506_CPGF.csv", HEADER_CPGF + "\n" + ROW_CPGF + "\n")
        else:
            _write_module_zip(dest, "202506_CPDC.csv", HEADER_CPDC + "\n" + ROW_CPDC + "\n")
        return True

    mock_client.download_file.side_effect = fake_download
    result = await ext.extract(year=2025, month=6)

    # 2 linhas (cpgf + cpdc); cpcc pulado graciosamente.
    assert result.height == 2
    # concat diagonal_relaxed: colunas do contrato + extras do cpdc (convênio).
    assert "NOME FAVORECIDO" in result.columns
    assert "VALOR TRANSAÇÃO" in result.columns
    assert "NÚMERO CONVÊNIO" in result.columns
    cpgf_row = result.filter(pl.col("_source_url").str.contains("/cpgf/"))
    assert cpgf_row["VALOR TRANSAÇÃO"][0] == "607,41"
    cpdc_row = result.filter(pl.col("_source_url").str.contains("/cpdc/"))
    assert cpdc_row["VALOR TRANSAÇÃO"][0] == "70922,36"


@pytest.mark.asyncio
async def test_extract_waf_num_modulo_pula_e_concatena_os_demais(ext, mock_client):
    """WAF no módulo cpgf é pulado (job não cai); cpcc/cpdc seguem normal."""

    async def fake_download(url, dest):
        if "/cpgf/" in url:
            raise PortalTransparenciaWAFError("WAF bloqueou o dump")
        if "/cpcc/" in url:
            _write_module_zip(dest, "202506_CPCC.csv", HEADER_CPCC + "\n" + ROW_CPCC + "\n")
        else:
            _write_module_zip(dest, "202506_CPDC.csv", HEADER_CPDC + "\n" + ROW_CPDC + "\n")
        return True

    mock_client.download_file.side_effect = fake_download
    result = await ext.extract(year=2025, month=6)

    assert result.height == 2  # cpcc + cpdc; cpgf pulado pelo WAF
    assert not result["_source_url"].str.contains("/cpgf/").any()
    assert result["_source_url"].str.contains("/cpdc/").any()


@pytest.mark.asyncio
async def test_extract_api_error_403_num_modulo_pula(ext, mock_client):
    """403 genérico do host (sem WAF/XML) num módulo → pula; os demais seguem.

    Plano §4.4: o catch por módulo cobre WAFError E PortalTransparenciaAPIError
    com ``status_code == 403`` (um 403 SEM os marcadores que o cliente já
    resolveu antes). Erro de AUTENTICAÇÃO real (403 da API, sem 403 no
    download) permanece fatal — o extrator não engole.
    """

    async def fake_download(url, dest):
        if "/cpgf/" in url:
            raise PortalTransparenciaAPIError("Erro HTTP 403 ao baixar X", status_code=403)
        if "/cpcc/" in url:
            _write_module_zip(dest, "202506_CPCC.csv", HEADER_CPCC + "\n" + ROW_CPCC + "\n")
        else:
            _write_module_zip(dest, "202506_CPDC.csv", HEADER_CPDC + "\n" + ROW_CPDC + "\n")
        return True

    mock_client.download_file.side_effect = fake_download
    result = await ext.extract(year=2025, month=6)

    assert result.height == 2  # cpcc + cpdc; cpgf pulado pelo 403
    assert not result["_source_url"].str.contains("/cpgf/").any()
    assert result["_source_url"].str.contains("/cpdc/").any()


@pytest.mark.asyncio
async def test_extract_api_error_403_nao_engole_erro_sem_403(ext, mock_client):
    """APIError SEM status 403 continua fatal — não mascara falha real."""

    async def fake_download(url, dest):
        raise PortalTransparenciaAPIError("Erro HTTP 500 ao baixar X", status_code=500)

    mock_client.download_file.side_effect = fake_download
    with pytest.raises(PortalTransparenciaAPIError):
        await ext.extract(year=2025, month=6)


@pytest.mark.asyncio
async def test_extract_nenhum_modulo_publicado_retorna_vazio(ext, mock_client):
    """Todos os módulos indisponíveis (False) → DataFrame vazio, sem crash."""
    mock_client.download_file = AsyncMock(return_value=False)
    result = await ext.extract(year=2025, month=6)

    assert result.is_empty()
    assert mock_client.download_file.call_count == 3  # um download por módulo


@pytest.mark.asyncio
async def test_cache_por_modulo_evita_downloads_redundantes(mock_client, tmp_path):
    """Cache próprio por (module, year, month): 2ª extração não baixa de novo."""
    ext = PortalCartoesBulkExtractor(
        mock_client, modules=["cpgf", "cpcc"], domain_name="cg_cartoes", bulk_dir=tmp_path
    )

    async def fake_download(url, dest):
        if "/cpgf/" in url:
            _write_module_zip(dest, "202401_CPGF.csv", HEADER_CPGF + "\n" + ROW_CPGF + "\n")
        else:
            _write_module_zip(dest, "202401_CPCC.csv", HEADER_CPCC + "\n" + ROW_CPCC + "\n")
        return True

    mock_client.download_file.side_effect = fake_download
    first = await ext.extract(year=2024, month=1)
    calls_first = mock_client.download_file.call_count
    second = await ext.extract(year=2024, month=1)

    assert first.height == 2 and second.height == 2
    # A 2ª extração reusa o cache — nenhum download novo.
    assert mock_client.download_file.call_count == calls_first


@pytest.mark.asyncio
async def test_extract_sem_janela_levanta_value_error(ext, mock_client):
    """Sem year/month o dump de módulo não tem URL (ValueError documentado)."""
    with pytest.raises(ValueError):
        await ext.extract()
