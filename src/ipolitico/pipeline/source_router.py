"""Decisão de fonte API vs Bulk com base na estratégia e na janela temporal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ipolitico.core.constants import DomainType, LoadStrategy, SourceType
from ipolitico.core.domain_spec import bulk_meta_for_domain, spec_for
from ipolitico.pipeline.window_resolver import resolve_calendar_years


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
        DomainType.EVENTOS,
        DomainType.ORIENTACOES,
    }
)


class SourceRouter:
    """
    Decide entre fonte API vs Bulk com base na estratégia e granularidade.

    **Snapshot** (dump único, sem partição anual): FULL_LOAD → Bulk; incremental → API.

    **Yearly** (dump particionado por ano): FULL_LOAD multi-ano → Bulk; janela curta ou
    incremental → API (evita ZIP gigante só para cortar dias).
    """

    @classmethod
    def plan(
        cls,
        domain: DomainType,
        strategy: LoadStrategy,
        effective_start_iso: str,
        effective_end_iso: str,
    ) -> ExtractionPlan:
        """
        Decide entre fonte API vs Bulk com base em domínio, estratégia e janela.

        Args:
            domain: Tipo de domínio (ex: DESPESAS, EVENTOS, FRENTES).
            strategy: Estratégia de carga (FULL_LOAD vs INCREMENTAL).
            effective_start_iso: Início da janela de extração (ISO 8601).
            effective_end_iso: Fim da janela de extração (ISO 8601).

        Returns:
            ExtractionPlan com source_type e, se Bulk, coluna de filtro e janela.

        Comportamento:
            - Domínios snapshot em FULL_LOAD → Bulk; incremental → API.
            - Domínios anuais com FULL_LOAD e janela multi-ano → Bulk.
            - Domínios anuais com INCREMENTAL ou janela curta → API.
        """
        spec = spec_for(domain)
        meta = bulk_meta_for_domain(domain)

        # Domínios bulk_only (sem rota API): sempre Bulk
        if meta.get("bulk_only"):
            col = meta.get("bulk_filter_date_column")
            return ExtractionPlan(
                SourceType.BULK,
                bulk_temporal_column=col if isinstance(col, str) else None,
                bulk_eff_start_iso=effective_start_iso,
                bulk_eff_end_iso=effective_end_iso,
            )

        granularity = (spec.bulk_granularity if spec else None) or meta.get("bulk_granularity")

        if granularity == "snapshot":
            if strategy == LoadStrategy.FULL_LOAD:
                col = meta.get("bulk_filter_date_column")
                return ExtractionPlan(
                    SourceType.BULK,
                    bulk_temporal_column=col if isinstance(col, str) else None,
                    bulk_eff_start_iso=effective_start_iso,
                    bulk_eff_end_iso=effective_end_iso,
                )
            return ExtractionPlan(SourceType.API)

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
