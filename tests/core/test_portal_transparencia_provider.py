"""Testes do PortalTransparenciaSourceProvider — adapter da federação (ticket 02).

Prior art: ``tests/core/test_senado_adm_provider.py`` — manager mockado; o
provider filtra pelos domínios que o manager conhece na config (``domain_configs``).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.sources.portal_transparencia_provider import (
    PortalTransparenciaSourceProvider,
)


def test_provider_name():
    """O nome do provider é o valor registrado no ``--source``."""
    assert PortalTransparenciaSourceProvider.name == "portaldatransparencia"


@pytest.mark.asyncio
async def test_provider_dispatcha_apenas_dominios_configurados():
    """Domínios de outras fontes não são encaminhados (evita erro no --source all)."""
    manager = MagicMock()
    manager.run_domain = AsyncMock()
    manager.config = {"domain_configs": {"cg_orgaos": {}}}
    provider = PortalTransparenciaSourceProvider(manager)

    await provider.run_domains(
        [DomainType.DEPUTADOS, DomainType.CG_ORGAOS],
        LoadStrategy.FULL_LOAD,
        SinkType.DATALAKE,
        None,
        None,
    )

    manager.run_domain.assert_awaited_once_with(
        domain=DomainType.CG_ORGAOS,
        sink_type=SinkType.DATALAKE,
        strategy=LoadStrategy.FULL_LOAD,
        start_date=None,
        end_date=None,
        warmup=True,
    )


@pytest.mark.asyncio
async def test_provider_config_vazia_inerte():
    """Sem domínios na config, nada é despachado (sem erro ruidoso)."""
    manager = MagicMock()
    manager.run_domain = AsyncMock()
    manager.config = {"domain_configs": {}}
    provider = PortalTransparenciaSourceProvider(manager)

    await provider.run_domains(
        [DomainType.CG_ORGAOS],
        LoadStrategy.INCREMENTAL,
        SinkType.DATALAKE,
        "2026-01-01",
        "2026-12-31",
    )

    manager.run_domain.assert_not_awaited()
