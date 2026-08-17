"""Testes do SenadoAdmSourceProvider — adapter da federação (issue 06).

Prior art: ``tests/core/test_senado_provider.py`` — manager mockado.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.sources.senado_adm_provider import SenadoAdmSourceProvider


def test_senado_adm_provider_name():
    """O nome do provider é o valor registrado no ``--source`` (``senado-adm``)."""
    assert SenadoAdmSourceProvider.name == "senado-adm"


@pytest.mark.asyncio
async def test_senado_adm_provider_dispatches_only_configured_domains():
    """
    Só despacha domínios que o manager conhece (config ``domain_configs``) —
    domínios de outras fontes não são encaminhados, evitando erro ruidoso
    no ``--source all``. Com a config vazia desta fatia, nada é despachado.
    """
    manager = MagicMock()
    manager.run_domain = AsyncMock()
    manager.config = {"domain_configs": {}}  # fatia 06: domínios ainda não existem
    provider = SenadoAdmSourceProvider(manager)

    await provider.run_domains(
        [DomainType.DEPUTADOS, DomainType.SENADORES, DomainType.REFERENCIAS],
        LoadStrategy.INCREMENTAL,
        SinkType.DATALAKE,
        "2024-01-01",
        "2024-02-01",
    )

    manager.run_domain.assert_not_awaited()


@pytest.mark.asyncio
async def test_senado_adm_provider_delegates_owned_domain_to_manager():
    """
    Quando a config já conhece um domínio (futuras fatias 07-09), o provider
    repassa o domínio ao manager com os mesmos argumentos recebidos.
    """
    manager = MagicMock()
    manager.run_domain = AsyncMock()
    manager.config = {"domain_configs": {"deputados": {}}}
    provider = SenadoAdmSourceProvider(manager)

    await provider.run_domains(
        [DomainType.DEPUTADOS, DomainType.SENADORES],
        LoadStrategy.FULL_LOAD,
        SinkType.DATALAKE,
        None,
        None,
        warmup=False,
    )

    manager.run_domain.assert_awaited_once_with(
        domain=DomainType.DEPUTADOS,
        sink_type=SinkType.DATALAKE,
        strategy=LoadStrategy.FULL_LOAD,
        start_date=None,
        end_date=None,
        warmup=False,
    )
