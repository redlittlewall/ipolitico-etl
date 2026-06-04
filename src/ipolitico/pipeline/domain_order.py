"""Ordem de execução e dependências entre domínios da Câmara."""

from __future__ import annotations

from typing import Iterable

from ipolitico.core.constants import DomainType

# Ordem estável quando todos os upstreams devem rodar primeiro
FULL_CAMARA_PIPELINE: tuple[DomainType, ...] = (
    DomainType.DEPUTADOS,
    DomainType.DEPUTADOS_DETALHE,
    DomainType.LEGISLATURAS,
    DomainType.LEGISLATURAS_DETALHE,
    DomainType.LEGISLATURAS_LIDERES,
    DomainType.LEGISLATURAS_MESA,
    DomainType.BLOCOS,
    DomainType.BLOCOS_PARTIDOS,
    DomainType.FRENTES,
    DomainType.FRENTES_DETALHE,
    DomainType.FRENTES_MEMBROS,
    DomainType.GRUPOS,
    DomainType.GRUPOS_DETALHE,
    DomainType.GRUPOS_MEMBROS,
    DomainType.GRUPOS_HISTORICO,
    DomainType.ORGAOS,
    DomainType.ORGAOS_DETALHE,
    DomainType.ORGAOS_MEMBROS,
    DomainType.ORGAOS_EVENTOS,
    DomainType.ORGAOS_VOTACOES,
    DomainType.PARTIDOS,
    DomainType.PARTIDOS_DETALHE,
    DomainType.PARTIDOS_MEMBROS,
    DomainType.PARTIDOS_LIDERES,
    DomainType.DESPESAS,
    DomainType.PROPOSICOES,
    DomainType.TRAMITACOES,
    DomainType.AUTORES,
    DomainType.RELACIONADAS,
    DomainType.TEMAS,
    DomainType.PROPOSICOES_VOTACOES,
    DomainType.DISCURSOS,
    DomainType.DEPUTADOS_FRENTES,
    DomainType.DEPUTADOS_ORGAOS,
    DomainType.DEPUTADOS_EVENTOS,
    DomainType.DEPUTADOS_HISTORICO,
    DomainType.MANDATOS_EXTERNOS,
    DomainType.PROFISSÕES,
    DomainType.OCUPACOES,
    DomainType.VOTACOES,
    DomainType.VOTACOES_DETALHE,
    DomainType.VOTOS,
    DomainType.ORIENTACOES,
    DomainType.EVENTOS,
    DomainType.EVENTOS_DETALHE,
    DomainType.EVENTOS_DEPUTADOS,
    DomainType.EVENTOS_VOTACOES,
    DomainType.EVENTOS_PAUTA,
    DomainType.EVENTOS_ORGAOS,
    DomainType.REFERENCIAS,
    DomainType.FUNCIONARIOS,
    DomainType.TECAD_CATEGORIAS,
    DomainType.TECAD_TERMOS,
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
    DomainType.DEPUTADOS_FRENTES: frozenset({DomainType.DEPUTADOS}),
    DomainType.DEPUTADOS_ORGAOS: frozenset({DomainType.DEPUTADOS}),
    DomainType.DEPUTADOS_EVENTOS: frozenset({DomainType.DEPUTADOS}),
    DomainType.DEPUTADOS_HISTORICO: frozenset({DomainType.DEPUTADOS}),
    DomainType.MANDATOS_EXTERNOS: frozenset({DomainType.DEPUTADOS}),
    DomainType.EVENTOS_DEPUTADOS: frozenset({DomainType.EVENTOS}),
    DomainType.EVENTOS_VOTACOES: frozenset({DomainType.EVENTOS}),
    DomainType.EVENTOS_PAUTA: frozenset({DomainType.EVENTOS}),
    DomainType.EVENTOS_ORGAOS: frozenset({DomainType.EVENTOS}),
    DomainType.PARTIDOS_MEMBROS: frozenset({DomainType.PARTIDOS}),
    DomainType.PARTIDOS_LIDERES: frozenset({DomainType.PARTIDOS}),
    DomainType.PROPOSICOES_VOTACOES: frozenset({DomainType.PROPOSICOES}),
    DomainType.BLOCOS_PARTIDOS: frozenset({DomainType.BLOCOS}),
    DomainType.DEPUTADOS_DETALHE: frozenset({DomainType.DEPUTADOS}),
    DomainType.ORGAOS_DETALHE: frozenset({DomainType.ORGAOS}),
    DomainType.EVENTOS_DETALHE: frozenset({DomainType.EVENTOS}),
    DomainType.VOTACOES_DETALHE: frozenset({DomainType.VOTACOES}),
    DomainType.FRENTES_DETALHE: frozenset({DomainType.FRENTES}),
    DomainType.PARTIDOS_DETALHE: frozenset({DomainType.PARTIDOS}),
    DomainType.GRUPOS_DETALHE: frozenset({DomainType.GRUPOS}),
    DomainType.LEGISLATURAS_DETALHE: frozenset({DomainType.LEGISLATURAS}),
    DomainType.ORGAOS_EVENTOS: frozenset({DomainType.ORGAOS}),
    DomainType.ORGAOS_VOTACOES: frozenset({DomainType.ORGAOS}),
    DomainType.GRUPOS_MEMBROS: frozenset({DomainType.GRUPOS}),
    DomainType.GRUPOS_HISTORICO: frozenset({DomainType.GRUPOS}),
    DomainType.LEGISLATURAS_LIDERES: frozenset({DomainType.LEGISLATURAS}),
    DomainType.LEGISLATURAS_MESA: frozenset({DomainType.LEGISLATURAS}),
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
