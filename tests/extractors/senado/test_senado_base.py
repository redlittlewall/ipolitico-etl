"""Testes do SenadoBaseExtractor — comportamento público, não implementação."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor


@pytest.mark.asyncio
async def test_fetch_flat_returns_data():
    """
    fetch_flat() chama SenadoClient.fetch() internamente e retorna o
    JSON cru da API (sem flatten — isso é responsabilidade do extrator
    específico que chama flatten_response depois).
    """
    client = SenadoClient()
    extractor = SenadoBaseExtractor(client)
    fake_data = [{"id": 1, "nome": "Senador A"}]

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").respond(
            status_code=200,
            json={"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": fake_data}}},
        )

        result = await extractor.fetch_flat("senador/lista/atual")

        assert result == {
            "ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": fake_data}}
        }


@pytest.mark.asyncio
async def test_flatten_response_extracts_array():
    """
    flatten_response() navega pela data_path e extrai o array alvo.
    """
    extractor = SenadoBaseExtractor(client=None)
    data = {"nivel1": {"nivel2": {"nivel3": [1, 2, 3]}}}
    result = extractor.flatten_response(data, ["nivel1", "nivel2", "nivel3"])
    assert result == [1, 2, 3]


def test_flatten_response_missing_path_returns_empty():
    """
    flatten_response() retorna lista vazia se o data_path não existir.
    """
    extractor = SenadoBaseExtractor(client=None)
    data = {"soh_isso": {"aqui": [1]}}
    result = extractor.flatten_response(data, ["nivel1", "nivel2"])
    assert result == []


def test_ensure_list_single_dict():
    """
    _ensure_list() normaliza objeto-único para lista de 1 elemento.
    """
    extractor = SenadoBaseExtractor(client=None)
    result = extractor._ensure_list({"id": 1, "nome": "Teste"})
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == {"id": 1, "nome": "Teste"}


def test_ensure_list_already_list():
    """
    _ensure_list() retorna a lista intocada se já for lista.
    """
    extractor = SenadoBaseExtractor(client=None)
    items = [{"id": 1}, {"id": 2}]
    result = extractor._ensure_list(items)
    assert result is items  # mesma referência (não copiou)


def test_ensure_list_none():
    """
    _ensure_list() retorna lista vazia para None.
    """
    extractor = SenadoBaseExtractor(client=None)
    result = extractor._ensure_list(None)
    assert result == []


def test_senado_base_url_comes_from_client():
    """SenadoBaseExtractor.base_url deve vir do client.BASE_URL."""
    client = SenadoClient()
    extractor = SenadoBaseExtractor(client)
    assert extractor.base_url == "https://legis.senado.leg.br/dadosabertos"
