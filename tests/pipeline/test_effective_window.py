"""P0.6 / P2: janela efetiva (piso dominial + teto=hoje)."""

from datetime import datetime
from unittest.mock import MagicMock

from ipolitico.core.constants import DomainType, LoadStrategy
from ipolitico.pipeline.effective_window import (
    resolve_calendar_years,
    resolve_effective_iso_window,
)


def test_resolve_calendar_years_normal():
    assert resolve_calendar_years("2024-03-01", "2026-01-15") == (2024, 2026)


def test_resolve_calendar_years_swapped():
    assert resolve_calendar_years("2026-01-01", "2024-12-31") == (2024, 2026)


def test_effective_window_applies_domain_floor(monkeypatch):
    monkeypatch.setattr(
        "ipolitico.pipeline.effective_window.datetime",
        MagicMock(now=MagicMock(return_value=datetime(2025, 6, 1))),
    )
    start, end = resolve_effective_iso_window(
        DomainType.DESPESAS,
        orchestration_start="2000-01-01",
        orchestration_end="2025-12-31",
        earliest_possible="2009-01-01",
        strategy=LoadStrategy.FULL_LOAD,
        state_store=None,
        watermark_column="dataDocumento",
    )
    assert start == "2009-01-01"
    assert end == "2025-06-01"


def test_effective_window_caps_at_today(monkeypatch):
    monkeypatch.setattr(
        "ipolitico.pipeline.effective_window.datetime",
        MagicMock(now=MagicMock(return_value=datetime(2024, 3, 15))),
    )
    start, end = resolve_effective_iso_window(
        DomainType.PROPOSICOES,
        orchestration_start="2024-01-01",
        orchestration_end="2099-12-31",
        earliest_possible="1988-01-01",
        strategy=LoadStrategy.INCREMENTAL,
        state_store=MagicMock(),
        watermark_column="dataApresentacao",
    )
    assert start >= "1988-01-01"
    assert end == "2024-03-15"
