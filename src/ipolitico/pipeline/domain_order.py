"""Ordem de execução e dependências entre domínios da Câmara."""

from __future__ import annotations

from typing import Iterable

from ipolitico.core.constants import DomainType

# Ordem estável quando todos os upstreams devem rodar primeiro
FULL_CAMARA_PIPELINE: tuple[DomainType, ...] = (
    DomainType.DEPUTADOS,
    DomainType.LEGISLATURAS,
    DomainType.BLOCOS,
    DomainType.FRENTES,
    DomainType.FRENTES_MEMBROS,
    DomainType.GRUPOS,
    DomainType.ORGAOS,
    DomainType.ORGAOS_MEMBROS,
    DomainType.PARTIDOS,
    DomainType.DESPESAS,
    DomainType.PROPOSICOES,
    DomainType.TRAMITACOES,
    DomainType.AUTORES,
    DomainType.RELACIONADAS,
    DomainType.TEMAS,
    DomainType.DISCURSOS,
    DomainType.PROFISSÕES,
    DomainType.OCUPACOES,
    DomainType.VOTACOES,
    DomainType.VOTOS,
    DomainType.ORIENTACOES,
    DomainType.EVENTOS,
)

# Dependências obrigatórias (silver/gold já populado antes do domínio)
DOMAIN_UPSTREAM_REQUIREMENTS: dict[DomainType, frozenset[DomainType]] = {
    DomainType.DESPESAS: frozenset({DomainType.DEPUTADOS}),
    DomainType.VOTOS: frozenset({DomainType.VOTACOES}),
    DomainType.PROFISSÕES: frozenset({DomainType.DEPUTADOS}),
    DomainType.OCUPACOES: frozenset({DomainType.DEPUTADOS}),
    DomainType.DISCURSOS: frozenset({DomainType.DEPUTADOS}),
    DomainType.TRAMITACOES: frozenset({DomainType.PROPOSICOES}),
    DomainType.AUTORES: frozenset({DomainType.PROPOSICOES}),
    DomainType.ORIENTACOES: frozenset({DomainType.VOTACOES}),
    DomainType.ORGAOS_MEMBROS: frozenset({DomainType.ORGAOS}),
    DomainType.FRENTES_MEMBROS: frozenset({DomainType.FRENTES}),
    DomainType.RELACIONADAS: frozenset({DomainType.PROPOSICOES}),
    DomainType.TEMAS: frozenset({DomainType.PROPOSICOES}),
}


def expand_camara_domains_with_dependencies(requested: Iterable[DomainType]) -> list[DomainType]:
    """
    Injera domínios faltantes (ex.: deputados antes de despesas) preservando ordenação canônica.
    """
    wanted: set[DomainType] = set(requested)

    expanded = True
    while expanded:
        expanded = False
        for d in list(wanted):
            for up in DOMAIN_UPSTREAM_REQUIREMENTS.get(d, frozenset()):
                if up not in wanted:
                    wanted.add(up)
                    expanded = True

    ordered = [d for d in FULL_CAMARA_PIPELINE if d in wanted]
    # Algum domínio fora da tupla fixa aparece ao final preservando sequência solicitada original
    extra = [d for d in requested if d not in ordered]
    seen: set[DomainType] = set()
    out: list[DomainType] = []
    for item in ordered + extra:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
