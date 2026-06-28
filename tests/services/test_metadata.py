from unittest.mock import AsyncMock

import pytest

from ipolitico.core.constants import ApiParams
from ipolitico.services.metadata import CamaraMetadataService


@pytest.fixture
def metadata_service():
    client = AsyncMock()
    return CamaraMetadataService(client)


# ==========================================
# TESTES: GET CURRENT LEGISLATURE ID
# ==========================================


@pytest.mark.asyncio
async def test_get_current_legislature_id_success(metadata_service):
    """
    Garante que a API pede exatamente 1 item, em ordem Decrescente (DESC),
    e extrai corretamente o ID do objeto retornado.
    """
    # Simulamos o retorno do governo
    metadata_service.client.fetch.return_value = [{"id": 99, "dataInicio": "2031-02-01"}]

    result = await metadata_service.get_current_legislature_id()

    assert result == 99

    # Valida se as regras do negócio (query params) estão sendo respeitadas
    args, kwargs = metadata_service.client.fetch.call_args
    params_usados = kwargs["params"]
    assert params_usados[ApiParams.ORDEM.value] == "DESC"
    assert params_usados[ApiParams.ITENS.value] == 1


@pytest.mark.asyncio
async def test_get_current_legislature_id_fallback(metadata_service):
    """
    O governo caiu ou a rota de legislaturas mudou.
    O sistema DEVE assumir o fallback (default ou custom) para não crashar o ETL.
    """
    # Cenário 1: API retorna lista vazia
    metadata_service.client.fetch.return_value = []
    assert await metadata_service.get_current_legislature_id() == 57  # Default

    # Cenário 2: API retorna nulo total (erro 404 convertido pelo client)
    metadata_service.client.fetch.return_value = None
    assert await metadata_service.get_current_legislature_id(fallback=58) == 58


# ==========================================
# TESTES: GET LEGISLATURE START DATE
# ==========================================


@pytest.mark.asyncio
async def test_get_legislature_start_date_success(metadata_service):
    """
    Garante que o serviço acessa a chave correta (dataInicio).
    """
    metadata_service.client.fetch.return_value = {"id": 57, "dataInicio": "2023-02-01"}

    result = await metadata_service.get_legislature_start_date(57)

    assert result == "2023-02-01"

    # Verifica se a URL montada estava correta (com o ID no path)
    args, kwargs = metadata_service.client.fetch.call_args
    assert args[0].endswith("/57")


@pytest.mark.asyncio
async def test_get_legislature_start_date_not_found(metadata_service):
    """
     E se a API devolver o objeto da Legislatura sem a chave 'dataInicio'?
    Não pode estourar um KeyError.
    """
    # Cenário 1: Retorno incompleto (sem dataInicio)
    metadata_service.client.fetch.return_value = {"id": 57, "descricao": "Sem data"}
    assert await metadata_service.get_legislature_start_date(57) is None

    # Cenário 2: Retorno vazio/nulo do client
    metadata_service.client.fetch.return_value = None
    assert await metadata_service.get_legislature_start_date(57) is None
