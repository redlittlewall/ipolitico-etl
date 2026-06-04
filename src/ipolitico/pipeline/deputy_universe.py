"""Resolução do universo de deputados por legislatura(s) intersectando a janela civil."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from ipolitico.core.constants import DomainType, MedallionLayer
from ipolitico.core.legislature import legislature_id_bounds_for_calendar_years
from ipolitico.pipeline.effective_window import resolve_calendar_years
from ipolitico.storage.datalake_repository import DataLakeRepository
from ipolitico.storage.state_store import StateStore

logger = logging.getLogger(__name__)


def resolve_deputy_ids_for_calendar_window(
    *,
    start_iso: str,
    end_iso: str,
    current_legislature_id: int,
    anchor_year: int,
    lake: Optional[DataLakeRepository],
    state_store: StateStore,
) -> List[Any]:
    """
    Deputados que atuaram em legislatura(s) compatíveis com os anos civis da janela.

    Usa Gold (idLegislatura) ou Silver com a mesma coluna; evita varrer todos os IDs
    históricos do lake quando só interessa o mandato do período.
    """
    start_year, end_year = resolve_calendar_years(start_iso, end_iso)
    leg_start, leg_end = legislature_id_bounds_for_calendar_years(
        start_year,
        end_year,
        current_legislature_id=current_legislature_id,
        anchor_year_current_legislature=anchor_year,
    )

    silver_fallback = state_store.get_existing_ids(
        table_name=DomainType.DEPUTADOS.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )

    if lake is None:
        logger.warning(
            "[DeputyUniverse] Sem DataLakeRepository; fallback com todos os IDs Silver (%s).",
            len(silver_fallback),
        )
        return silver_fallback

    ids = lake.list_deputy_ids_for_legislature_bounds(
        leg_start, leg_end, silver_fallback_ids=silver_fallback
    )
    logger.info(
        "[DeputyUniverse] %s deputados para legs %s..%s (anos %s..%s).",
        len(ids),
        leg_start,
        leg_end,
        start_year,
        end_year,
    )
    return ids
