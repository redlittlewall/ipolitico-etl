"""Testes do SenadoClient — comportamento público, não implementação."""

import logging
from unittest.mock import patch

import httpx
import pytest
import respx

from ipolitico.core.senado_client import SenadoAPIError, SenadoClient


@pytest.mark.asyncio
async def test_senado_client_returns_data():
    """
    Happy path: SenadoClient.fetch() retorna o JSON decodificado da API,
    sem manipular envelopes (diferente da Câmara).
    """
    client = SenadoClient()
    fake_data = {"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": [{"id": 1}]}}}

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").respond(
            status_code=200, json=fake_data
        )

        result = await client.fetch("senador/lista/atual")
        assert result == fake_data


@pytest.mark.asyncio
async def test_senado_client_returns_empty_on_404():
    """
    Falsos 404: a API retorna 404 para recursos sem dados.
    O cliente deve retornar lista vazia em vez de tentar retry.
    """
    client = SenadoClient()

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").respond(
            status_code=404
        )

        result = await client.fetch("senador/lista/atual")

        assert isinstance(result, list)
        assert result == []


@pytest.mark.asyncio
@patch("asyncio.sleep")  # Evita o sleep do exponential backoff do tenacity
async def test_senado_client_retry_on_429_then_success(mock_sleep):
    """
    Garante que o cliente retenta após 429 e retorna dados na segunda tentativa.
    O patch em asyncio.sleep evita a espera real do exponential backoff.
    """
    client = SenadoClient()
    fake_data = {"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": [{"id": 1}]}}}

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(200, json=fake_data),
            ]
        )

        result = await client.fetch("senador/lista/atual")

        assert result == fake_data


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_senado_client_raises_after_exhausted_retries(mock_sleep):
    """
    Se a API retorna 429 em todas as tentativas, o cliente deve lançar
    SenadoAPIError após esgotar as retentativas.
    """
    client = SenadoClient(max_retries=2)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").respond(429)

        with pytest.raises(SenadoAPIError):
            await client.fetch("senador/lista/atual")


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_senado_client_logs_single_warning_on_final_failure(mock_sleep, caplog):
    """
    429 persistente não deve gerar 1 WARNING por tentativa (ruído que
    dominava o log do ETL). O retry por tentativa é DEBUG; apenas a exaustão
    final registra 1 WARNING.
    """
    caplog.set_level(logging.WARNING, logger="ipolitico.core.senado_client")
    client = SenadoClient()

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").respond(429)

        with pytest.raises(SenadoAPIError):
            await client.fetch("senador/lista/atual")

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "após" in warnings[0].getMessage()


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_senado_client_logs_retry_attempts_at_debug(mock_sleep, caplog):
    """
    O 429 intermediário (com sucesso na retentativa) é registrado em DEBUG,
    não em WARNING — mantém o log informativo sem poluir.
    """
    caplog.set_level(logging.DEBUG, logger="ipolitico.core.senado_client")
    client = SenadoClient()
    fake_data = {"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": [{"id": 1}]}}}

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(200, json=fake_data),
            ]
        )

        result = await client.fetch("senador/lista/atual")

        assert result == fake_data

    debug_transient = [
        r for r in caplog.records if r.levelname == "DEBUG" and "Erro transitório" in r.getMessage()
    ]
    assert len(debug_transient) == 1
    assert not any(r.levelname == "WARNING" for r in caplog.records)
