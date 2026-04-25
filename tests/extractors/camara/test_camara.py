from unittest.mock import AsyncMock, MagicMock

import pytest
from ipolitico.core.config import CAMARA_PAGE_SIZE
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.camara.camara_base import CamaraBaseExtractor


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def mock_state_store():
    return MagicMock()


@pytest.fixture
def extractor(mock_client, mock_state_store):
    return CamaraBaseExtractor(client=mock_client, state_store=mock_state_store)


def test_build_params_limpa_nulos_e_extrai_enums(extractor):
    """Garante que a função prepare os parâmetros removendo Nones e resolvendo Enums."""
    raw_params = {
        ApiParams.ANO: 2026,
        ApiParams.MES: None,  # Deve ser removido
        ApiParams.ORDEM: ApiParams.ORDEM_ASC,  # Deve extrair "ASC"
        "param_estranho": "valor",
    }

    cleaned = extractor.build_params(raw_params)

    # O Enum da chave deve virar string ("ano")
    assert "ano" in cleaned
    assert cleaned["ano"] == 2026
    # Nones devem ser extirpados para não sujar a URL
    assert "mes" not in cleaned
    # O Enum do valor deve ser resolvido ("ASC")
    assert cleaned["ordem"] == "ASC"
    assert cleaned["param_estranho"] == "valor"


@pytest.mark.asyncio
async def test_fetch_paginated_para_na_pagina_incompleta(extractor):
    """
    Testa se o while loop entende que a paginação acabou quando
    a API devolve menos itens do que o tamanho da página.
    """
    # Página 1 volta cheia. Página 2 volta com apenas 1 item (Fim da extração)
    extractor.client.fetch.side_effect = [
        [{"id": i} for i in range(CAMARA_PAGE_SIZE)],
        [{"id": 999}],
    ]

    resultado = await extractor.fetch_paginated("teste", {})

    assert len(resultado) == CAMARA_PAGE_SIZE + 1
    assert extractor.client.fetch.call_count == 2

    # Valida se os parâmetros de paginação foram injetados corretamente na chamada HTTP
    args_chamada_1, kwargs_chamada_1 = extractor.client.fetch.call_args_list[0]
    assert kwargs_chamada_1["params"]["pagina"] == 1
    assert kwargs_chamada_1["params"]["itens"] == CAMARA_PAGE_SIZE

    args_chamada_2, kwargs_chamada_2 = extractor.client.fetch.call_args_list[1]
    assert kwargs_chamada_2["params"]["pagina"] == 2


@pytest.mark.asyncio
async def test_fetch_paginated_lista_vazia(extractor):
    """Garante que quebra o loop imediatamente se a API devolver vazio no primeiro request."""
    extractor.client.fetch.return_value = []

    resultado = await extractor.fetch_paginated("teste", {})

    assert resultado == []
    assert extractor.client.fetch.call_count == 1
