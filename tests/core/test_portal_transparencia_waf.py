"""Testes do tratamento de AWS WAF no cliente do Portal da Transparência (ticket 03).

O host de dumps bulk (``portaldatransparencia.gov.br/download-de-dados`` /
``dadosabertos-download.cgu.gov.br``) responde 403 + desafio JS (CAPTCHA) a
clientes não-browser — verificado na validação real do ticket 03. O WAF não é
transitório (re-tentar não resolve o desafio JS), então:

1. ``PortalTransparenciaClient._download_once`` detecta a assinatura do WAF
   (header ``x-amzn-waf-action`` ou corpo com ``awswaf``) e levanta
   ``PortalTransparenciaWAFError`` — SEM retry (a assinatura é diferente de um
   403 genérico do host).
2. ``PortalTransparenciaBulkExtractor.extract`` captura o erro e devolve lista
   vazia — o job não cai; quando o WAF liberar, o mesmo job passa a baixar.
3. A API v3 (``api.portaldatransparencia.gov.br``) NÃO fica atrás desse WAF:
   401/403 lá continua sendo ``PortalTransparenciaAuthError`` (chave inválida).
"""

from unittest.mock import AsyncMock

import pytest
import respx

from ipolitico.core.portal_transparencia_client import (
    PortalTransparenciaAPIError,
    PortalTransparenciaAuthError,
    PortalTransparenciaClient,
    PortalTransparenciaWAFError,
)
from ipolitico.extractors.portal_transparencia.bulk.bulk_extractor import (
    PortalTransparenciaBulkExtractor,
)

API_KEY = "chave-de-teste-fake"
BULK_URL = "https://portaldatransparencia.gov.br/download-de-dados/servidores/202401"


@pytest.mark.asyncio
async def test_download_waf_403_por_header_levanta_waf_error(tmp_path):
    """403 com header ``x-amzn-waf-action`` → WAFError, SEM retry."""
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    dest = tmp_path / "202401"

    with respx.mock:
        route = respx.get(BULK_URL).respond(403, headers={"x-amzn-waf-action": "block"})
        with pytest.raises(PortalTransparenciaWAFError):
            await client.download_file(BULK_URL, str(dest))

    assert route.call_count == 1  # WAF não é transitório: re-tentar não resolve o desafio JS


@pytest.mark.asyncio
async def test_download_waf_403_por_corpo_levanta_waf_error(tmp_path):
    """403 sem header WAF mas com corpo ``awswaf`` (desafio JS) → WAFError."""
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    dest = tmp_path / "202401"

    with respx.mock:
        route = respx.get(BULK_URL).respond(
            403,
            text="<html><script>awswaf</script> AccessDenied: request blocked</html>",
        )
        with pytest.raises(PortalTransparenciaWAFError):
            await client.download_file(BULK_URL, str(dest))

    assert route.call_count == 1


@pytest.mark.asyncio
async def test_download_403_sem_assinatura_waf_e_api_error_fatal(tmp_path):
    """403 do host SEM assinatura WAF → APIError fatal (não confunde com WAF)."""
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    dest = tmp_path / "202401"

    with respx.mock:
        route = respx.get(BULK_URL).respond(403, text="Forbidden")
        with pytest.raises(PortalTransparenciaAPIError) as exc:
            await client.download_file(BULK_URL, str(dest))

    assert route.call_count == 1  # erro fatal, sem retry
    # status_code exposto: o extrator bulk multi-módulo distingue o 403 do módulo
    # indisponível (pulado) de outros erros fatais via esse atributo.
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_download_403_header_aws_generico_e_api_error_fatal(tmp_path):
    """403 com headers/corpo AWS GENÉRICOS (sem assinatura WAF) → APIError fatal.

    ``x-amzn-requestid``/``x-amzn-trace-id`` e corpo ``AccessDenied`` aparecem
    em qualquer 403 de S3/CloudFront — NÃO são assinatura do WAF. Só
    ``x-amzn-waf-*`` e o desafio ``awswaf`` contam; um 403 fatal não pode ser
    engolido como "WAF gracioso".
    """
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    dest = tmp_path / "202401"

    with respx.mock:
        route = respx.get(BULK_URL).respond(
            403,
            headers={"x-amzn-requestid": "abc", "x-amzn-trace-id": "root=1-2-3"},
            text="AccessDenied",
        )
        with pytest.raises(PortalTransparenciaAPIError) as exc:
            await client.download_file(BULK_URL, str(dest))

    assert route.call_count == 1  # erro fatal, sem retry
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_download_403_accessdenied_xml_do_s3_e_ausencia(tmp_path):
    """403 do S3 anônimo com envelope XML <Code>AccessDenied</Code> → False.

    Ticket 04: o host de dumps é S3 anônimo — objeto ausente responde 403 com o
    envelope XML ``<Error><Code>AccessDenied</Code>`` (listing negado → nunca
    chega a 404). Isso é AUSÊNCIA (análogo ao 404), não erro fatal: o job deve
    devolver vazio sem cair (pep/imoveis não publicados, cpcc sem mês).
    """
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    dest = tmp_path / "202401"

    with respx.mock:
        route = respx.get(BULK_URL).respond(
            403,
            headers={"content-type": "application/xml"},
            text=(
                "<Error><Code>AccessDenied</Code><Message>Access Denied</Message>"
                "<RequestId>abc</RequestId><HostId>xyz</HostId></Error>"
            ),
        )
        ok = await client.download_file(BULK_URL, str(dest))

    assert ok is False
    assert route.call_count == 1  # ausência: sem retry (análogo ao 404)


@pytest.mark.asyncio
async def test_fetch_403_continua_sendo_auth_error():
    """API v3: 403 NÃO é WAF (host diferente) — segue sendo AuthError (chave inválida)."""
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)

    with respx.mock:
        route = respx.get(
            "https://api.portaldatransparencia.gov.br/api-de-dados/orgaos-siape"
        ).respond(403, text="Invalid API key")
        with pytest.raises(PortalTransparenciaAuthError):
            await client.fetch("api-de-dados/orgaos-siape")

    assert route.call_count == 1


@pytest.mark.asyncio
async def test_extractor_captura_waf_e_devolve_vazio(tmp_path):
    """Extrator bulk captura WAFError e devolve lista vazia — o job não cai."""
    client = PortalTransparenciaClient(api_key=API_KEY)
    ext = PortalTransparenciaBulkExtractor(client, module="servidores", bulk_dir=tmp_path)

    with respx.mock:
        respx.get(BULK_URL).respond(403, headers={"x-amzn-waf-action": "block"})
        result = await ext.extract(year=2024, month=1)

    assert result.is_empty()
    assert "_source_url" not in result.columns


@pytest.mark.asyncio
async def test_extractor_passa_por_download_normal_sem_waf(tmp_path):
    """Sem WAF (200), o extractor flui normalmente e devolve o CSV lido."""
    client = AsyncMock()

    async def fake_download(url, dest):
        with open(dest, "w", encoding="utf-8") as f:
            f.write("id_servidor;nome\n1;FULANO\n")
        return True

    client.download_file.side_effect = fake_download
    ext = PortalTransparenciaBulkExtractor(client, module="servidores", bulk_dir=tmp_path)

    result = await ext.extract(year=2024, month=1)

    assert not result.is_empty()
    assert result["nome"].to_list() == ["FULANO"]
