"""Filtros de jobs já cobertos no lake (resume incremental por chave de job)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

DeputyYear = Tuple[Any, int]


def filter_despesas_api_jobs(
    jobs: List[Dict[str, Any]],
    covered: Set[DeputyYear],
) -> List[Dict[str, Any]]:
    """Remove pares (deputado_id, year) já presentes na Silver de despesas."""
    if not covered:
        return jobs

    kept: List[Dict[str, Any]] = []
    skipped = 0
    for job in jobs:
        key = (job.get("deputado_id"), int(job["year"]))
        if key in covered:
            skipped += 1
            continue
        kept.append(job)

    if skipped:
        logger.info(
            "[DESPESAS] Resume: %s jobs ignorados (par deputado×ano já na Silver), %s restantes.",
            skipped,
            len(kept),
        )
    return kept
