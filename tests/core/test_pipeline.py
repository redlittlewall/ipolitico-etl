"""
Testes Unitários do Orquestrador (Pipeline).
Garante o cumprimento dos contratos de idempotência (FULL LOAD vs INCREMENTAL)
e o isolamento de domínios solicitados pelo usuário.
"""

import sys
from unittest.mock import AsyncMock, patch

import pytest
from ipolitico.core.constants import DomainType, LoadStrategy, SourceType
from ipolitico.main import chunk_list, main, run_pipeline


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


def test_chunk_list():
    """Garante o fatiamento de arrays para micro-batching."""
    lista = [1, 2, 3, 4, 5]
    lotes = list(chunk_list(lista, 2))
    assert lotes == [[1, 2], [3, 4], [5]]


@pytest.mark.asyncio
async def test_run_pipeline_bulk_execution(mock_dependencies):
    """
    Garante que o orquestrador sabe invocar os extratores Bulk.
    """
    sink = mock_dependencies["sink"]

    with patch("ipolitico.main.CamaraExtractorFactory.get_extractor") as mock_factory:
        mock_ext = AsyncMock()
        mock_factory.return_value = mock_ext

        await run_pipeline(
            sink=sink,
            state_store=sink,
            start_date="2026-01-01",
            end_date="2026-12-31",
            source=SourceType.BULK,
            domains=[
                DomainType.DEPUTADOS,
                DomainType.DESPESAS,
                DomainType.PROPOSICOES,
                DomainType.VOTACOES,
            ],
        )

        # O extract deve ter sido chamado várias vezes (uma para cada domínio/ano)
        assert mock_ext.extract.call_count >= 4


@pytest.mark.asyncio
async def test_run_pipeline_deputados_detalhes_missing(mock_dependencies):
    """
    Testa o fluxo onde já temos deputados salvos, mas faltam os detalhes deles.
    """
    sink = mock_dependencies["sink"]

    # Simula que temos o deputado ID 10 no banco, mas não temos na tabela de detalhes
    def mock_get_existing_ids(table):
        if table == "deputados":
            return [10]
        if table == "deputados_detalhes":
            return []
        return []

    sink.get_existing_ids.side_effect = mock_get_existing_ids

    with patch("ipolitico.main.CamaraExtractorFactory.get_extractor") as mock_factory:
        mock_ext = AsyncMock()
        mock_factory.return_value = mock_ext

        await run_pipeline(
            sink=sink, state_store=sink, source=SourceType.API, domains=[DomainType.DEPUTADOS]
        )

        # Garante que o orquestrador acionou o extract_detalhes para o ID 10
        mock_ext.extract_detalhes.assert_called_once()


@pytest.mark.asyncio
async def test_run_pipeline_exception_handling(mock_dependencies):
    """Garante que erros da factory crasham graciosamente."""
    sink = mock_dependencies["sink"]

    with patch(
        "ipolitico.main.CamaraExtractorFactory.get_extractor",
        side_effect=Exception("Erro Injetado"),
    ):
        with pytest.raises(Exception, match="Erro Injetado"):
            await run_pipeline(sink=sink, state_store=sink)


@pytest.mark.asyncio
@patch("ipolitico.main.run_pipeline", new_callable=AsyncMock)
async def test_main_cli_default_dates(mock_run):
    """
    Simula a execução via terminal (CLI) usando FULL_LOAD sem passar datas.
    O sistema deve calcular o 'primeiro_dia_mes' automaticamente.
    """
    # Simulamos o usuário digitando: python main.py --strategy full_load --domains deputados
    test_args = ["main.py", "--strategy", "full_load", "--domains", "deputados"]

    with patch.object(sys, "argv", test_args):
        await main()

        # Garante que o orquestrador foi acionado
        mock_run.assert_called_once()

        # Garante que a data inicial injetada no run_pipeline não é None (calculada automaticamente)
        kwargs = mock_run.call_args.kwargs
        assert kwargs["start_date"] is not None
        assert kwargs["start_date"].endswith("-01")  # Verifica se pegou o primeiro dia do mês


@pytest.mark.asyncio
async def test_run_pipeline_extraction_exception_handling(mock_dependencies):
    """
    Força um erro DENTRO do bloco 'try' (durante a extração) para testar a
    captura (logger.error), o repasse do erro (raise) e o 'finally' fechando o client.
    """
    sink = mock_dependencies["sink"]

    # 1. Criamos um mock assassino isolado apenas para este teste
    ext_sabotado = AsyncMock()
    ext_sabotado.extract.side_effect = Exception("O governo desligou os servidores")

    # 2. Substituímos a Factory para retornar nosso mock sabotado
    with patch("ipolitico.main.CamaraExtractorFactory.get_extractor", return_value=ext_sabotado):
        # 3. Garante que a exceção sobe para o terminal
        with pytest.raises(Exception, match="O governo desligou os servidores"):
            await run_pipeline(sink=sink, state_store=sink, domains=[DomainType.DEPUTADOS])


@pytest.mark.asyncio
@patch("ipolitico.main.run_pipeline", new_callable=AsyncMock)
async def test_main_cli_explicit_dates(mock_run):
    """
    Garante que se o usuário forçar datas no terminal, o Orquestrador
    respeita e não tenta calcular datas automáticas.
    """
    import sys

    # Simulamos o usuário digitando datas explícitas
    test_args = ["main.py", "--start-date", "2026-05-01", "--end-date", "2026-05-31"]

    with patch.object(sys, "argv", test_args):
        await main()

        # Inspeciona o que foi injetado na função principal
        kwargs = mock_run.call_args.kwargs
        assert kwargs["start_date"] == "2026-05-01"
        assert kwargs["end_date"] == "2026-05-31"
