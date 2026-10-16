"""Testes do SenadoSourceProvider — adapter da federação.

Espelha o contrato do ``SenadoAdmSourceProvider``: o provider só deve
encaminhar domínios que o manager conhece na config (``domain_configs``),
evitando o erro ruidoso "Configuração não encontrada no YAML" no
``--source all`` (domínios de outras fontes não pertencem a este manager).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.sources.senado_provider import SenadoSourceProvider


def test_senado_provider_name():
    """O nome do provider é o valor registrado no ``--source`` (``senado``)."""
    assert SenadoSourceProvider.name == "senado"


@pytest.mark.asyncio
async def test_senado_provider_dispatches_only_configured_domains():
    """
    Domínios de outras fontes não são encaminhados ao manager: sem isso,
    ``--source all`` registra ``logger.error`` para cada domínio que o YAML
    do Senado não conhece.
    """
    manager = MagicMock()
    manager.run_domain = AsyncMock()
    manager.config = {"domain_configs": {"senadores": {}}}
    provider = SenadoSourceProvider(manager)

    await provider.run_domains(
        [DomainType.DEPUTADOS, DomainType.SENADORES, DomainType.REFERENCIAS],
        LoadStrategy.INCREMENTAL,
        SinkType.DATALAKE,
        "2024-01-01",
        "2024-02-01",
    )

    manager.run_domain.assert_awaited_once_with(
        domain=DomainType.SENADORES,
        sink_type=SinkType.DATALAKE,
        strategy=LoadStrategy.INCREMENTAL,
        start_date="2024-01-01",
        end_date="2024-02-01",
        warmup=True,
    )


@pytest.mark.asyncio
async def test_senado_provider_delegates_owned_domains_to_manager():
    """
    Quando a config conhece vários domínios do Senado, todos são repassados
    ao manager com os mesmos argumentos recebidos.
    """
    manager = MagicMock()
    manager.run_domain = AsyncMock()
    manager.config = {"domain_configs": {"senadores": {}, "vetos_presidenciais": {}}}
    provider = SenadoSourceProvider(manager)

    await provider.run_domains(
        [DomainType.SENADORES, DomainType.VETOS_PRESIDENCIAIS],
        LoadStrategy.FULL_LOAD,
        SinkType.DATALAKE,
        None,
        None,
        warmup=False,
    )

    assert manager.run_domain.await_count == 2
    manager.run_domain.assert_any_await(
        domain=DomainType.SENADORES,
        sink_type=SinkType.DATALAKE,
        strategy=LoadStrategy.FULL_LOAD,
        start_date=None,
        end_date=None,
        warmup=False,
    )
    manager.run_domain.assert_any_await(
        domain=DomainType.VETOS_PRESIDENCIAIS,
        sink_type=SinkType.DATALAKE,
        strategy=LoadStrategy.FULL_LOAD,
        start_date=None,
        end_date=None,
        warmup=False,
    )
