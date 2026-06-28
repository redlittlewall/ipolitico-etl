from ipolitico.core.legislature import (
    legislature_anchor_year_from_iso,
    legislature_id_bounds_for_calendar_years,
)


def test_leg_bounds_matches_legacy_heuristic():
    leg_lo, leg_hi = legislature_id_bounds_for_calendar_years(
        2020,
        2021,
        current_legislature_id=57,
        anchor_year_current_legislature=2023,
    )
    assert leg_lo == 56
    assert leg_hi == 58


def test_anchor_year_fallback():
    assert legislature_anchor_year_from_iso(None, 2030) == 2030
    assert legislature_anchor_year_from_iso("2023-02-01", 2000) == 2023
