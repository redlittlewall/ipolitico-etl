"""Metadados declarativos por domínio (watermark, dependências, granularidade bulk)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet

from ipolitico.core.constants import EARLIEST_DATE_MAP, DomainType
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY


@dataclass(frozen=True)
class DomainSpec:
    domain: DomainType
    watermark_column: str | None
    earliest_iso: str
    depends_on: FrozenSet[DomainType]
    bulk_granularity: str | None = None


def _spec(
    domain: DomainType,
    wm: str | None,
    deps: FrozenSet[DomainType] = frozenset(),
) -> DomainSpec:
    meta = BULK_REGISTRY.get(domain.value, {})
    return DomainSpec(
        domain=domain,
        watermark_column=wm,
        earliest_iso=EARLIEST_DATE_MAP.get(domain, "1826-04-29"),
        depends_on=deps,
        bulk_granularity=meta.get("bulk_granularity"),
    )


DOMAIN_SPECS: dict[DomainType, DomainSpec] = {
    DomainType.DEPUTADOS: _spec(DomainType.DEPUTADOS, None),
    DomainType.DESPESAS: _spec(
        DomainType.DESPESAS,
        "dataDocumento",
        frozenset({DomainType.DEPUTADOS}),
    ),
    DomainType.PROPOSICOES: _spec(DomainType.PROPOSICOES, "dataApresentacao"),
    DomainType.VOTACOES: _spec(DomainType.VOTACOES, "data"),
    DomainType.VOTOS: _spec(DomainType.VOTOS, None, frozenset({DomainType.VOTACOES})),
    DomainType.PROFISSÕES: _spec(
        DomainType.PROFISSÕES,
        None,
        frozenset({DomainType.DEPUTADOS}),
    ),
    DomainType.OCUPACOES: _spec(
        DomainType.OCUPACOES,
        None,
        frozenset({DomainType.DEPUTADOS}),
    ),
}


def bulk_meta_for_domain(domain: DomainType) -> dict:
    return BULK_REGISTRY.get(domain.value, {})


def spec_for(domain: DomainType) -> DomainSpec | None:
    return DOMAIN_SPECS.get(domain)
