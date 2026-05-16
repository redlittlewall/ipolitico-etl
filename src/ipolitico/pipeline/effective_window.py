"""Normalização da janela temporal por domínio (floor/resume/hoje)."""

from datetime import datetime
from typing import TYPE_CHECKING

from ipolitico.core.constants import DomainType, LoadStrategy

if TYPE_CHECKING:
    from ipolitico.sinks.datalake_sink import DataLakeSink


def _iso_max(a: str, b: str) -> str:
    return max(a, b)


def _iso_min(a: str, b: str) -> str:
    return min(a, b)


def resolve_calendar_years(span_start: str, span_end: str) -> tuple[int, int]:
    """Retorna anos civis inicial e final a partir de ISO YYYY-MM-DD."""
    y0 = int(span_start.split("-")[0])
    y1 = int(span_end.split("-")[0])
    if y0 > y1:
        return y1, y0
    return y0, y1


def resolve_effective_iso_window(
    domain: DomainType,
    *,
    orchestration_start: str,
    orchestration_end: str,
    earliest_possible: str,
    strategy: LoadStrategy,
    state_store: "DataLakeSink | None",
    watermark_column: str | None,
) -> tuple[str, str]:
    """
    Aplica piso dominial + teto=hoje.

    Incremental já foi materializado em `orchestration_start` via watermark
    em PipelineManager._resolve_dates; esta função reforça piso dominial.

    Logs não são emitidos aqui (SRP): o caller faz observabilidade.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    start = _iso_max(orchestration_start, earliest_possible)
    end = _iso_min(orchestration_end, today)

    _ = strategy  # reservado: futuro skip granular por job usa strategy + watermark
    _ = state_store  # watermark já aplicado antes; campo para extensões (P1)
    _ = watermark_column

    if start > end:
        end = today
    return start, end
