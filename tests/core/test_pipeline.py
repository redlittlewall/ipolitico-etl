from unittest.mock import AsyncMock, patch

import polars as pl
import pytest
from ipolitico.main import LoadStrategy, run_pipeline


@pytest.fixture
def mock_dependencies():
    """Mocka todas as dependências pesadas (Rede, Banco e Serviços) do main.py."""
    with (
        patch("ipolitico.main.CamaraClient", autospec=True) as _,
        patch("ipolitico.main.SQLiteSink", autospec=True) as MockSink,
        patch("ipolitico.main.DeputadosExtractor", autospec=True) as MockDep,
        patch("ipolitico.main.DespesasExtractor", autospec=True) as MockDesp,
        patch("ipolitico.main.ProposicoesExtractor", autospec=True) as MockProp,
        patch("ipolitico.main.VotacoesExtractor", autospec=True) as MockVot,
    ):
        # Configurações do Sink (Banco)
        sink_instance = MockSink.return_value
        sink_instance.save = AsyncMock()
        sink_instance.delete_period = AsyncMock()
        sink_instance.get_existing_ids.return_value = []
        sink_instance.get_watermark.return_value = None

        # Configurações dos Extratores
        dep_instance = MockDep.return_value
        dep_instance.extract = AsyncMock(return_value=pl.DataFrame({"id": [1]}))
        dep_instance.extract_detalhes = AsyncMock(return_value=pl.DataFrame())
        dep_instance.get_all_ids = AsyncMock(return_value=[1])

        desp_instance = MockDesp.return_value
        desp_instance.extract = AsyncMock(return_value=pl.DataFrame())

        prop_instance = MockProp.return_value
        prop_instance.extract = AsyncMock(return_value=pl.DataFrame())

        vot_instance = MockVot.return_value
        vot_instance.extract = AsyncMock(return_value=pl.DataFrame({"id": ["VOT1"]}))
        vot_instance.extract_votos = AsyncMock(return_value=pl.DataFrame())

        yield {
            "sink": sink_instance,
            "deputados": dep_instance,
            "despesas": desp_instance,
            "proposicoes": prop_instance,
            "votacoes": vot_instance,
        }


@pytest.mark.asyncio
async def test_run_pipeline_full_load_triggers_deletes(mock_dependencies):
    """
    Testa se a estratégia FULL_LOAD aciona os métodos destrutivos corretos no banco
    antes de iniciar a extração.
    """
    sink = mock_dependencies["sink"]

    await run_pipeline(
        sink=sink,
        state_store=sink,
        start_date="2026-01-01",
        end_date="2026-12-31",
        strategy=LoadStrategy.FULL_LOAD,
    )

    # O FULL_LOAD DEVE ter acionado a limpeza em despesas, proposições e votações.
    assert sink.delete_period.call_count == 3

    # Verifica os argumentos da primeira chamada (Despesas)
    args, kwargs = sink.delete_period.call_args_list[0]
    assert args[0] == "despesas"
    assert args[1] == "2026-01-01"


@pytest.mark.asyncio
async def test_run_pipeline_incremental_skips_deletes(mock_dependencies):
    """
    Testa se a estratégia INCREMENTAL ignora deleções e tenta ler os watermarks do banco.
    """
    sink = mock_dependencies["sink"]

    await run_pipeline(
        sink=sink,
        state_store=sink,
        strategy=LoadStrategy.INCREMENTAL,
    )

    # O INCREMENTAL NUNCA deve apagar dados
    sink.delete_period.assert_not_called()

    # Ele DEVE perguntar o watermark para as tabelas temporais
    assert sink.get_watermark.call_count >= 3
