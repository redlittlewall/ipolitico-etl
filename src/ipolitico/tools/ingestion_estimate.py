"""
Estimativa de requisições HTTP e tempo para ingestão via API da Câmara.

Usa heurísticas calibráveis e, se existir, telemetria em data/api_telemetry.db.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ipolitico.core.config import CAMARA_HTTP_CONCURRENCY, TELEMETRY_PATH
from ipolitico.core.constants import EARLIEST_DATE_MAP, DomainType, LoadStrategy
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY
from ipolitico.pipeline.source_router import SourceRouter
from ipolitico.pipeline.window_resolver import resolve_calendar_years

# Ordens de grandeza observadas em produção (ajuste via env ou telemetria).
DEFAULT_DEPUTY_COUNT = 513
DEFAULT_VOTACOES_PER_MONTH = 100
DEFAULT_PROPOSICOES_PAGES_PER_MONTH = 2
DEFAULT_DESPESAS_PAGES_PER_DEPUTY_YEAR = 1
AVG_HTTP_LATENCY_SEC = 0.45
PAGINATION_OVERHEAD = 1.05


@dataclass(frozen=True)
class DomainEstimate:
    domain: str
    http_requests: int
    bulk_downloads: int
    notes: str


@dataclass(frozen=True)
class IngestionEstimate:
    effective_start: str
    effective_end: str
    strategy: str
    domains: tuple[str, ...]
    domain_estimates: tuple[DomainEstimate, ...]
    total_http_requests: int
    total_bulk_downloads: int
    calibrated_latency_sec: float
    http_concurrency: int
    estimated_api_wall_seconds: float
    estimated_api_wall_hours: float

    def summary_lines(self) -> list[str]:
        lines = [
            f"Janela: {self.effective_start} → {self.effective_end} | {self.strategy}",
            f"HTTP ~{self.total_http_requests:,} req | Bulk ~{self.total_bulk_downloads} arquivos",
            (
                f"Tempo API (ordem de grandeza): "
                f"{self.estimated_api_wall_hours:.1f} h "
                f"({self.estimated_api_wall_seconds:,.0f} s) "
                f"@ {self.http_concurrency} conexões, "
                f"{self.calibrated_latency_sec:.2f} s/req"
            ),
        ]
        for d in self.domain_estimates:
            lines.append(
                f"  • {d.domain}: {d.http_requests:,} HTTP, " f"{d.bulk_downloads} bulk — {d.notes}"
            )
        return lines


def _months_inclusive(start_iso: str, end_iso: str) -> int:
    y0, m0 = int(start_iso[:4]), int(start_iso[5:7])
    y1, m1 = int(end_iso[:4]), int(end_iso[5:7])
    return max(1, (y1 - y0) * 12 + (m1 - m0) + 1)


def _years_inclusive(start_iso: str, end_iso: str) -> int:
    sy, ey = resolve_calendar_years(start_iso, end_iso)
    return ey - sy + 1


def read_telemetry_avg_latency(db_path: Path = TELEMETRY_PATH) -> float | None:
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT AVG(response_time_ms) FROM api_requests
                WHERE success = 1 AND response_time_ms IS NOT NULL
                """
            ).fetchone()
        if row and row[0]:
            return (float(row[0]) / 1000.0) * PAGINATION_OVERHEAD
    except sqlite3.Error:
        return None
    return None


def estimate_domain(
    domain: DomainType,
    start_iso: str,
    end_iso: str,
    strategy: LoadStrategy,
    *,
    deputy_count: int = DEFAULT_DEPUTY_COUNT,
    votacoes_per_month: int = DEFAULT_VOTACOES_PER_MONTH,
    force_api: bool = False,
) -> DomainEstimate:
    """
    Estima o número de requisições HTTP e downloads bulk para um domínio.

    Para domínios bulk, consulta ``bulk_granularity`` no BULK_REGISTRY:
    granularidade ``"snapshot"`` conta 1 download independente da janela
    temporal; ``"year"`` conta um download por ano.

    Args:
        domain: Tipo do domínio.
        start_iso: Início da janela (ISO).
        end_iso: Fim da janela (ISO).
        strategy: Estratégia de carga.
        deputy_count: Número de deputados (para heurísticas API).
        votacoes_per_month: Média de votações por mês.
        force_api: Se True, ignora bulk e força estimativa via API.

    Returns:
        DomainEstimate com contagem estimada de HTTP e bulk downloads.
    """
    plan = SourceRouter.plan(domain, strategy, start_iso, end_iso)
    use_bulk = plan.source_type.value == "bulk" and not force_api
    years = _years_inclusive(start_iso, end_iso)
    months = _months_inclusive(start_iso, end_iso)

    if use_bulk:
        granularity = BULK_REGISTRY.get(domain.value, {}).get("bulk_granularity", "year")
        bulk = 1 if granularity == "snapshot" else years
        return DomainEstimate(
            domain=domain.value,
            http_requests=0,
            bulk_downloads=bulk,
            notes=f"SourceRouter=BULK ({bulk} ano(s)); transform local",
        )

    if domain == DomainType.DEPUTADOS:
        if start_iso <= EARLIEST_DATE_MAP[DomainType.DEPUTADOS]:
            http = 57
            return DomainEstimate(domain.value, http, 0, "~57 legislaturas (1 lista paginada cada)")
        return DomainEstimate(domain.value, 2, 0, "1 janela temporal (lista paginada)")

    if domain == DomainType.DESPESAS:
        jobs = deputy_count * years
        http = int(jobs * DEFAULT_DESPESAS_PAGES_PER_DEPUTY_YEAR * PAGINATION_OVERHEAD)
        return DomainEstimate(
            domain.value,
            http,
            0,
            f"API: {deputy_count} deputados × {years} ano(s) (~{jobs} jobs)",
        )

    if domain == DomainType.PROPOSICOES:
        http = int(months * DEFAULT_PROPOSICOES_PAGES_PER_MONTH * PAGINATION_OVERHEAD)
        return DomainEstimate(domain.value, http, 0, f"{months} micro-lote(s) mensais")

    if domain == DomainType.VOTACOES:
        http = int(months * DEFAULT_PROPOSICOES_PAGES_PER_MONTH * PAGINATION_OVERHEAD)
        return DomainEstimate(
            domain.value,
            http,
            0,
            f"{months} mês(es); ~{votacoes_per_month} votações/mês na API",
        )

    if domain == DomainType.VOTOS:
        votacoes = months * votacoes_per_month
        return DomainEstimate(
            domain.value,
            votacoes,
            0,
            f"1 GET /votacoes/{{id}}/votos por votação (~{votacoes} no período)",
        )

    if domain in (DomainType.PROFISSÕES, DomainType.OCUPACOES):
        return DomainEstimate(
            domain.value,
            deputy_count,
            0,
            f"1 GET /deputados/{{id}}/{domain.value} por deputado",
        )

    return DomainEstimate(domain.value, 1, 0, "fallback")


def estimate_camara_ingestion(
    domains: Iterable[DomainType],
    start_iso: str,
    end_iso: str,
    strategy: LoadStrategy = LoadStrategy.FULL_LOAD,
    *,
    deputy_count: int = DEFAULT_DEPUTY_COUNT,
    http_concurrency: int | None = None,
    latency_sec: float | None = None,
) -> IngestionEstimate:
    today = datetime.now().strftime("%Y-%m-%d")
    eff_end = min(end_iso[:10], today)
    domain_list = tuple(domains)

    per_domain: list[DomainEstimate] = []
    for d in domain_list:
        floor = EARLIEST_DATE_MAP.get(d, start_iso)
        eff_start = max(start_iso[:10], floor)
        if eff_start > eff_end:
            continue
        per_domain.append(
            estimate_domain(d, eff_start, eff_end, strategy, deputy_count=deputy_count)
        )

    total_http = sum(e.http_requests for e in per_domain)
    total_bulk = sum(e.bulk_downloads for e in per_domain)
    conc = http_concurrency if http_concurrency is not None else CAMARA_HTTP_CONCURRENCY
    lat = (
        latency_sec
        if latency_sec is not None
        else (read_telemetry_avg_latency() or AVG_HTTP_LATENCY_SEC)
    )
    wall = (total_http / max(1, conc)) * lat if total_http else 0.0

    return IngestionEstimate(
        effective_start=start_iso[:10],
        effective_end=eff_end,
        strategy=strategy.value,
        domains=tuple(d.value for d in domain_list),
        domain_estimates=tuple(per_domain),
        total_http_requests=total_http,
        total_bulk_downloads=total_bulk,
        calibrated_latency_sec=lat,
        http_concurrency=conc,
        estimated_api_wall_seconds=wall,
        estimated_api_wall_hours=wall / 3600.0,
    )


def estimate_full_history_api_only() -> IngestionEstimate:
    """Cenário pessimista: tudo via API desde os pisos históricos (sem bulk)."""
    end = datetime.now().strftime("%Y-%m-%d")
    per: list[DomainEstimate] = []
    for d in (
        DomainType.DEPUTADOS,
        DomainType.DESPESAS,
        DomainType.PROPOSICOES,
        DomainType.VOTACOES,
        DomainType.VOTOS,
        DomainType.PROFISSÕES,
        DomainType.OCUPACOES,
    ):
        start = EARLIEST_DATE_MAP.get(d, "2000-01-01")
        per.append(estimate_domain(d, start, end, LoadStrategy.FULL_LOAD, force_api=True))
    total_http = sum(e.http_requests for e in per)
    total_bulk = sum(e.bulk_downloads for e in per)
    lat = read_telemetry_avg_latency() or AVG_HTTP_LATENCY_SEC
    conc = CAMARA_HTTP_CONCURRENCY
    wall = (total_http / max(1, conc)) * lat
    return IngestionEstimate(
        effective_start="pisos históricos",
        effective_end=end,
        strategy="full_load_api_only",
        domains=tuple(
            d.value
            for d in (
                DomainType.DEPUTADOS,
                DomainType.DESPESAS,
                DomainType.PROPOSICOES,
                DomainType.VOTACOES,
                DomainType.VOTOS,
                DomainType.PROFISSÕES,
                DomainType.OCUPACOES,
            )
        ),
        domain_estimates=tuple(per),
        total_http_requests=total_http,
        total_bulk_downloads=total_bulk,
        calibrated_latency_sec=lat,
        http_concurrency=conc,
        estimated_api_wall_seconds=wall,
        estimated_api_wall_hours=wall / 3600.0,
    )


def estimate_full_history_hybrid() -> IngestionEstimate:
    """Cenário recomendado: bulk multi-ano onde o router permite."""
    domains = (
        DomainType.DEPUTADOS,
        DomainType.DESPESAS,
        DomainType.PROPOSICOES,
        DomainType.VOTACOES,
        DomainType.VOTOS,
    )
    per: list[DomainEstimate] = []
    end = datetime.now().strftime("%Y-%m-%d")
    for d in domains:
        start = EARLIEST_DATE_MAP.get(d, "2000-01-01")
        per.append(estimate_domain(d, start, end, LoadStrategy.FULL_LOAD))
    total_http = sum(e.http_requests for e in per)
    total_bulk = sum(e.bulk_downloads for e in per)
    lat = read_telemetry_avg_latency() or AVG_HTTP_LATENCY_SEC
    conc = CAMARA_HTTP_CONCURRENCY
    wall = (total_http / max(1, conc)) * lat
    return IngestionEstimate(
        effective_start="pisos históricos",
        effective_end=end,
        strategy="full_load_hybrid",
        domains=tuple(d.value for d in domains),
        domain_estimates=tuple(per),
        total_http_requests=total_http,
        total_bulk_downloads=total_bulk,
        calibrated_latency_sec=lat,
        http_concurrency=conc,
        estimated_api_wall_seconds=wall,
        estimated_api_wall_hours=wall / 3600.0,
    )
