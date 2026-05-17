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


def filter_votacao_ids_pending_votos(
    votacao_ids: List[Any],
    covered: set[Any],
) -> List[Any]:
    """Remove votações cujo nominal já está na Silver/Gold de votos."""
    if not covered:
        return votacao_ids
    pending = [v for v in votacao_ids if v not in covered]
    skipped = len(votacao_ids) - len(pending)
    if skipped:
        logger.info(
            "[VOTOS] Resume: %s votações já materializadas; %s pendentes.",
            skipped,
            len(pending),
        )
    return pending


def filter_deputado_child_jobs(
    jobs: List[Dict[str, Any]],
    covered_deputy_ids: set[Any],
) -> List[Dict[str, Any]]:
    """Remove jobs de rotas filhas (/profissoes, /ocupacoes) já ingeridas."""
    if not covered_deputy_ids:
        return jobs
    kept = [j for j in jobs if j.get("deputado_id") not in covered_deputy_ids]
    skipped = len(jobs) - len(kept)
    if skipped:
        logger.info(
            "[DEPUTADO_CHILD] Resume: %s deputados ignorados (já na Silver), %s restantes.",
            skipped,
            len(kept),
        )
    return kept


def filter_entity_ids_pending_child(
    entity_ids: List[Any],
    covered: set[Any],
    domain_label: str,
    id_label: str = "entidades",
) -> List[Any]:
    if not covered:
        return entity_ids
    pending = [e for e in entity_ids if e not in covered]
    skipped = len(entity_ids) - len(pending)
    if skipped:
        logger.info(
            "[%s] Resume: %s %s já materializadas; %s pendentes.",
            domain_label.upper(),
            skipped,
            id_label,
            len(pending),
        )
    return pending


def filter_proposicao_ids_pending_child(
    proposicao_ids: List[Any],
    covered: set[Any],
    domain_label: str,
) -> List[Any]:
    if not covered:
        return proposicao_ids
    pending = [p for p in proposicao_ids if p not in covered]
    skipped = len(proposicao_ids) - len(pending)
    if skipped:
        logger.info(
            "[%s] Resume: %s proposições já materializadas; %s pendentes.",
            domain_label.upper(),
            skipped,
            len(pending),
        )
    return pending
