"""Cálculos puros sobre legislatura (Câmara) — independentes do orquestrador."""

from typing import Tuple


def legislature_id_bounds_for_calendar_years(
    start_year: int,
    end_year: int,
    *,
    current_legislature_id: int,
    anchor_year_current_legislature: int,
) -> Tuple[int, int]:
    """
    Estima IDs de legislatura mais prováveis que intersectam anos civis dados.

    Generaliza o mapeamento que antes fixava legislatura atual=57 e ano=2023.
    `anchor_year_current_legislature` deve ser o ano civil de início (YYYY)
    da legislatura atual, obtido via API (ex.: `get_legislature_start_date`).

    Observação: a Câmara tem exceções históricas; usamos heurística de ciclo quadrienal.

    Args:
        start_year: menor ano civil inclusivo na janela efetiva
        end_year: maior ano civil inclusivo na janela efetiva
        current_legislature_id: id numérico da legislatura atual (API)
        anchor_year_current_legislature: ano de início da legislatura atual
    Returns:
        (legislatura_inferior_aproximada, legislatura_superior_aproximada)
    """
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    leg_upper = current_legislature_id - (anchor_year_current_legislature - end_year) // 4 + 1
    leg_lower = max(
        1,
        current_legislature_id - (anchor_year_current_legislature - start_year) // 4 - 1,
    )

    leg_lower = min(leg_lower, leg_upper)
    return leg_lower, leg_upper


def legislature_anchor_year_from_iso(iso_date: str | None, fallback_calendar_year: int) -> int:
    """Extrai YYYY-MM-DD ou somente ano; usa fallback em ISO inválido."""
    if not iso_date:
        return fallback_calendar_year
    trimmed = iso_date.strip()
    if len(trimmed) >= 4 and trimmed[:4].isdigit():
        return int(trimmed[:4])
    return fallback_calendar_year
