"""
Testes Unitários do Orquestrador (Pipeline).
Garante o cumprimento dos contratos de idempotência (FULL LOAD vs INCREMENTAL)
e o isolamento de domínios solicitados pelo usuário.
"""

from unittest.mock import AsyncMock, patch

import pytest
from ipolitico.main import LoadStrategy, run_pipeline


@pytest.fixture
def mock_dependencies():
    """Mocka a infraestrutura pesada (Rede e Banco) mantendo o isolamento dos testes."""
    with (
        patch("ipolitico.main.CamaraClient", autospec=True) as _,
        patch("ipolitico.main.SQLiteSink", autospec=True) as MockSink,
        patch("ipolitico.main.CamaraExtractorFactory.get_extractor") as mock_get_extractor,
    ):
        # 1. Configurações do Sink (Banco de Dados Fake)
        sink_instance = MockSink.return_value
        sink_instance.save = AsyncMock()
        sink_instance.delete_period = AsyncMock()
        sink_instance.get_existing_ids.return_value = [100, 200]  # Simula IDs já baixados
        sink_instance.get_watermark.return_value = "2023-01-01"

        # 2. Configurações do Extrator (Nova arquitetura de streaming retorna None)
        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=None)
        mock_extractor.extract_detalhes = AsyncMock(return_value=None)
        mock_extractor.extract_votos = AsyncMock(return_value=None)

        mock_get_extractor.return_value = mock_extractor

        yield {
            "sink": sink_instance,
            "mock_extractor": mock_extractor,
        }


@pytest.mark.asyncio
async def test_run_pipeline_full_load_triggers_deletes(mock_dependencies):
    """
    Testa se a estratégia FULL_LOAD aciona os métodos de deleção destrutiva
    no banco de dados para os 3 domínios temporais, garantindo a idempotência.
    """
    sink = mock_dependencies["sink"]

    await run_pipeline(
        sink=sink,
        state_store=sink,
        start_date="2026-01-01",
        end_date="2026-12-31",
        strategy=LoadStrategy.FULL_LOAD,
    )

    # O FULL_LOAD DEVE ter acionado a limpeza em despesas, proposições e votações (3 vezes)
    assert sink.delete_period.call_count == 3

    # Audita se o primeiro expurgo foi chamado corretamente para as Despesas
    args, _ = sink.delete_period.call_args_list[0]
    assert args[0] == "despesas"
    assert args[1] == "2026-01-01"
    assert args[2] == "2026-12-31"


@pytest.mark.asyncio
async def test_run_pipeline_incremental_skips_deletes(mock_dependencies):
    """
    Testa se a estratégia INCREMENTAL protege os dados antigos,
    ignorando deleções e lendo os watermarks do banco (state_store).
    """
    sink = mock_dependencies["sink"]

    await run_pipeline(
        sink=sink,
        state_store=sink,
        strategy=LoadStrategy.INCREMENTAL,
    )

    # O INCREMENTAL NUNCA deve apagar dados
    sink.delete_period.assert_not_called()

    # DEVE perguntar o watermark para 'despesas', 'proposicoes' e 'votacoes'
    assert sink.get_watermark.call_count >= 3


@pytest.mark.asyncio
async def test_run_pipeline_respects_domain_filter(mock_dependencies):
    """
    Testa o recurso de 'Modo Light'.
    Se o usuário pediu apenas 'deputados', os outros domínios não podem ser extraídos.
    """
    sink = mock_dependencies["sink"]
    extractor = mock_dependencies["mock_extractor"]

    await run_pipeline(
        sink=sink,
        state_store=sink,
        domains=["deputados"],  # Isolando o escopo
    )

    # Verifica se os watermarks das outras tabelas NÃO foram consultados
    sink.get_watermark.assert_not_called()

    # A extração ocorreu, mas não apagou nem buscou metadados dos outros domínios
    assert extractor.extract.call_count > 0
