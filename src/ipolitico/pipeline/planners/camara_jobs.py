"""Geração de jobs e mapeadores para API/Bulk da Câmara.

Delega para o STRATEGY_REGISTRY em strategies.py, eliminando a cadeia if-elif
anterior. A assinatura pública CamaraJobPlanner.build() é mantida para
compatibilidade com chamadores existentes.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ipolitico.core.constants import DomainType
from ipolitico.core.domain_spec import spec_for
from ipolitico.pipeline.planners.strategies import strategy_for
from ipolitico.pipeline.source_router import ExtractionPlan
from ipolitico.storage.datalake_repository import DataLakeRepository

logger = logging.getLogger(__name__)


class CamaraJobPlanner:
    """Geração de jobs e mapeadores kw para chamadas à API/Bulk.

    Cada tipo de domínio possui uma estratégia registrada em STRATEGY_REGISTRY
    que encapsula a lógica de geração de jobs. Esta classe orquestra a delegação.
    """

    def __init__(self, state_store: Any, lake_repository: DataLakeRepository | None) -> None:
        self._state_store = state_store
        self._lake = lake_repository

    def build(
        self,
        domain: DomainType,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        """Gera jobs e mapper para o domínio, delegando à estratégia registrada.

        Args:
            domain: Tipo do domínio.
            start: Data de início da janela (ISO).
            end: Data de fim da janela (ISO).
            current_leg: ID da legislatura atual.
            anchor_year: Ano âncora da legislatura atual.
            extraction_plan: Plano de extração (API vs Bulk).

        Returns:
            Tupla (jobs, mapper) onde jobs é lista de dicionários e mapper
            é a função que transforma cada job em kwargs de extração.
        """
        spec = spec_for(domain)
        strategy = strategy_for(domain)

        jobs, mapper = strategy.build(
            domain=domain,
            spec=spec,
            start=start,
            end=end,
            current_leg=current_leg,
            anchor_year=anchor_year,
            extraction_plan=extraction_plan,
            state_store=self._state_store,
            lake=self._lake,
        )

        if not jobs:
            logger.info("[%s] Nenhum job gerado pela estratégia.", domain.value.upper())
            return [], lambda x: {}

        return jobs, mapper
