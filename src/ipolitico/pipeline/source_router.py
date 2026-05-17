"""Decisão de fonte API vs Bulk com base na estratégia e na janela temporal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ipolitico.core.constants import DomainType, LoadStrategy, SourceType
from ipolitico.core.domain_spec import bulk_meta_for_domain, spec_for
from ipolitico.pipeline.effective_window import resolve_calendar_years


@dataclass(frozen=True)
class ExtractionPlan:
    """Plano determinístico de extração."""

    source_type: SourceType
    bulk_temporal_column: Optional[str] = None
    bulk_eff_start_iso: Optional[str] = None
    bulk_eff_end_iso: Optional[str] = None


_BULK_YEARLY_DOMAINS = frozenset(
    {
        DomainType.DESPESAS,
        DomainType.PROPOSICOES,
        DomainType.VOTACOES,
    }
)


class SourceRouter:
    """
    Incremental sempre API (watermark + granularidade já calibradas no Planner).

    Full load em domínios com dump anual passa por Bulk quando a janela cobre mais de um
    ano civil; caso contrário mantém API (evita ZIP gigante só para cortar dias).
    """

    @classmethod
    def plan(
        cls,
        domain: DomainType,
        strategy: LoadStrategy,
        effective_start_iso: str,
        effective_end_iso: str,
    ) -> ExtractionPlan:
        spec = spec_for(domain)
        meta = bulk_meta_for_domain(domain)
        granularity = (spec.bulk_granularity if spec else None) or meta.get("bulk_granularity")

        if domain not in _BULK_YEARLY_DOMAINS or granularity != "year":
            return ExtractionPlan(SourceType.API)

        if strategy != LoadStrategy.FULL_LOAD:
            return ExtractionPlan(SourceType.API)

        sy, ey = resolve_calendar_years(effective_start_iso, effective_end_iso)
        if ey - sy < 1:
            return ExtractionPlan(SourceType.API)

        col = meta.get("bulk_filter_date_column")
        return ExtractionPlan(
            SourceType.BULK,
            bulk_temporal_column=col if isinstance(col, str) else None,
            bulk_eff_start_iso=effective_start_iso,
            bulk_eff_end_iso=effective_end_iso,
        )
