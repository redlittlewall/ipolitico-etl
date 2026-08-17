from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ipolitico.core.constants import DomainType
from ipolitico.main import main


@pytest.mark.asyncio
async def test_main_invokes_federation_and_closes_client():
    with (
        patch("ipolitico.main.load_config", return_value={"domain_configs": {"deputados": {}}}),
        patch("ipolitico.main.CamaraClient") as mock_client_cls,
        patch("ipolitico.main.PipelineBuilder"),
        patch("ipolitico.main.PipelineRunner"),
        patch("ipolitico.main.DataLakeSink"),
        patch("ipolitico.main.PipelineManager") as mock_mgr_cls,
        patch("ipolitico.main.FederationOrchestrator") as mock_fed_cls,
    ):
        inst_client = MagicMock()
        inst_client.close = AsyncMock()
        mock_client_cls.return_value = inst_client

        mock_builder = MagicMock()
        mock_builder.client = inst_client

        mock_mgr = MagicMock()
        mock_mgr.run_domain = AsyncMock()
        mock_mgr.builder = mock_builder
        mock_mgr_cls.return_value = mock_mgr

        mock_fed = MagicMock()
        mock_fed.run_all = AsyncMock()
        mock_fed_cls.return_value = mock_fed

        with patch("sys.argv", ["ipolitico.main", "--source", "camara", "--domains", "deputados"]):
            await main()

        mock_fed.run_all.assert_awaited_once()
        args = mock_fed.run_all.await_args[0]
        assert DomainType.DEPUTADOS in args[0]
        inst_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_source_senado_adm_registers_provider_in_federation():
    """
    ``--source senado-adm`` monta o SenadoAdmClient + manager e registra o
    provider ``senado-adm`` na federação (issue 06). Com config vazia, o
    provider é inerte até as fatias 07-09 adicionarem domínios.
    """
    with (
        patch("ipolitico.main.load_config", return_value={"domain_configs": {}}),
        patch("ipolitico.core.senado_adm_client.SenadoAdmClient") as mock_client_cls,
        patch("ipolitico.main.PipelineBuilder"),
        patch("ipolitico.main.PipelineRunner"),
        patch("ipolitico.main.DataLakeSink"),
        patch("ipolitico.main.PipelineManager") as mock_mgr_cls,
        patch("ipolitico.main.FederationOrchestrator") as mock_fed_cls,
    ):
        inst_client = MagicMock()
        inst_client.close = AsyncMock()
        mock_client_cls.return_value = inst_client

        mock_builder = MagicMock()
        mock_builder.client = inst_client

        mock_mgr = MagicMock()
        mock_mgr.builder = mock_builder
        mock_mgr_cls.return_value = mock_mgr

        mock_fed = MagicMock()
        mock_fed.run_all = AsyncMock()
        mock_fed_cls.return_value = mock_fed

        with patch(
            "sys.argv",
            ["ipolitico.main", "--source", "senado-adm", "--domains", "deputados"],
        ):
            await main()

        mock_client_cls.assert_called_once()
        mock_mgr_cls.assert_called_once()
        mock_fed.run_all.assert_awaited_once()

        providers = mock_fed_cls.call_args.args[0]
        assert len(providers) == 1
        assert providers[0].name == "senado-adm"
