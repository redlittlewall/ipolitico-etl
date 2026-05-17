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
    DomainType.ORGAOS: _spec(DomainType.ORGAOS, None),
    DomainType.PARTIDOS: _spec(DomainType.PARTIDOS, None),
    DomainType.EVENTOS: _spec(DomainType.EVENTOS, "dataHoraInicio"),
    DomainType.BLOCOS: _spec(DomainType.BLOCOS, None),
    DomainType.FRENTES: _spec(DomainType.FRENTES, None),
    DomainType.GRUPOS: _spec(DomainType.GRUPOS, None),
    DomainType.LEGISLATURAS: _spec(DomainType.LEGISLATURAS, None),
    DomainType.DISCURSOS: _spec(
        DomainType.DISCURSOS,
        "dataHoraInicio",
        frozenset({DomainType.DEPUTADOS}),
    ),
    DomainType.TRAMITACOES: _spec(
        DomainType.TRAMITACOES,
        None,
        frozenset({DomainType.PROPOSICOES}),
    ),
    DomainType.AUTORES: _spec(
        DomainType.AUTORES,
        None,
        frozenset({DomainType.PROPOSICOES}),
    ),
    DomainType.ORIENTACOES: _spec(
        DomainType.ORIENTACOES,
        None,
        frozenset({DomainType.VOTACOES}),
    ),
    DomainType.ORGAOS_MEMBROS: _spec(
        DomainType.ORGAOS_MEMBROS,
        None,
        frozenset({DomainType.ORGAOS}),
    ),
    DomainType.FRENTES_MEMBROS: _spec(
        DomainType.FRENTES_MEMBROS,
        None,
        frozenset({DomainType.FRENTES}),
    ),
    DomainType.RELACIONADAS: _spec(
        DomainType.RELACIONADAS,
        None,
        frozenset({DomainType.PROPOSICOES}),
    ),
    DomainType.TEMAS: _spec(
        DomainType.TEMAS,
        None,
        frozenset({DomainType.PROPOSICOES}),
    ),
    DomainType.DEPUTADOS_FRENTES: _spec(
        DomainType.DEPUTADOS_FRENTES, None, frozenset({DomainType.DEPUTADOS})
    ),
    DomainType.DEPUTADOS_ORGAOS: _spec(
        DomainType.DEPUTADOS_ORGAOS, None, frozenset({DomainType.DEPUTADOS})
    ),
    DomainType.DEPUTADOS_EVENTOS: _spec(
        DomainType.DEPUTADOS_EVENTOS, None, frozenset({DomainType.DEPUTADOS})
    ),
    DomainType.DEPUTADOS_HISTORICO: _spec(
        DomainType.DEPUTADOS_HISTORICO, None, frozenset({DomainType.DEPUTADOS})
    ),
    DomainType.EVENTOS_DEPUTADOS: _spec(
        DomainType.EVENTOS_DEPUTADOS, None, frozenset({DomainType.EVENTOS})
    ),
    DomainType.EVENTOS_VOTACOES: _spec(
        DomainType.EVENTOS_VOTACOES, None, frozenset({DomainType.EVENTOS})
    ),
    DomainType.EVENTOS_PAUTA: _spec(
        DomainType.EVENTOS_PAUTA, None, frozenset({DomainType.EVENTOS})
    ),
    DomainType.PARTIDOS_MEMBROS: _spec(
        DomainType.PARTIDOS_MEMBROS, None, frozenset({DomainType.PARTIDOS})
    ),
    DomainType.PARTIDOS_LIDERES: _spec(
        DomainType.PARTIDOS_LIDERES, None, frozenset({DomainType.PARTIDOS})
    ),
    DomainType.PROPOSICOES_VOTACOES: _spec(
        DomainType.PROPOSICOES_VOTACOES, None, frozenset({DomainType.PROPOSICOES})
    ),
    DomainType.BLOCOS_PARTIDOS: _spec(
        DomainType.BLOCOS_PARTIDOS, None, frozenset({DomainType.BLOCOS})
    ),
    DomainType.REFERENCIAS: _spec(DomainType.REFERENCIAS, None),
}


def bulk_meta_for_domain(domain: DomainType) -> dict:
    return BULK_REGISTRY.get(domain.value, {})


def spec_for(domain: DomainType) -> DomainSpec | None:
    return DOMAIN_SPECS.get(domain)
