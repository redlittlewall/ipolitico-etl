"""Ordem de execução e dependências entre domínios da Câmara."""

from __future__ import annotations

from typing import Iterable

from ipolitico.core.constants import DomainType

# Ordem estável quando todos os upstreams devem rodar primeiro
FULL_PIPELINE: tuple[DomainType, ...] = (
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
    DomainType.DEPUTADOS_HISTORICO,
    DomainType.DISCURSOS,
    DomainType.DEPUTADOS_FRENTES,
    DomainType.DEPUTADOS_ORGAOS,
    DomainType.DEPUTADOS_EVENTOS,
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
    DomainType.LICITACOES,
    DomainType.LICITACOES_CONTRATOS,
    DomainType.LICITACOES_ITENS,
    DomainType.LICITACOES_PEDIDOS,
    DomainType.LICITACOES_PROPOSTAS,
    DomainType.EVENTOS_PRESENCA_DEPUTADOS,
    DomainType.EVENTOS_REQUERIMENTOS,
    DomainType.VOTACOES_OBJETOS,
    DomainType.VOTACOES_PROPOSICOES,
    DomainType.FOLHA_PAGAMENTO,
    # ── Senado ────────────────────────────────────────────────────────────
    DomainType.SENADORES,
    DomainType.SENADORES_DETALHE,
    DomainType.PROCESSOS,
    DomainType.PROCESSOS_DETALHE,
    DomainType.PROCESSOS_EMENDAS,
    DomainType.PROCESSOS_DOCUMENTOS,
    DomainType.VOTACOES_SENADO,
    DomainType.VOTOS_SENADO,
    DomainType.VOTACOES_COMISSAO,
    DomainType.ORCAMENTO_EMENDAS,
    DomainType.ORCAMENTO_OFICIOS,
    DomainType.VETOS_PRESIDENCIAIS,
    DomainType.VETOS_DETALHE,
    DomainType.SENADORES_DISCURSOS,
    DomainType.DISCURSOS_PLENARIO,
    DomainType.DISCURSOS_TEXTO,
    DomainType.NOTAS_TAQUIGRAFIA_SESSAO,
    DomainType.NOTAS_TAQUIGRAFIA_REUNIAO,
    DomainType.COMISSOES_SENADO,
    DomainType.COMISSOES_DETALHE,
    DomainType.COMISSOES_REUNIOES,
    DomainType.COMISSOES_MEMBROS,
    DomainType.PLENARIO_AGENDA,
    DomainType.PLENARIO_RESULTADOS,
    DomainType.PLENARIO_SESSOES,
    DomainType.BLOCOS_SENADO,
    DomainType.LIDERANCAS_SENADO,
    DomainType.MESA_SENADO,
    DomainType.MESA_CONGRESSO,
    DomainType.SENADORES_MANDATOS,
    DomainType.SENADORES_FILIACOES,
    DomainType.ORIENTACAO_BANCADA,
    # ── Senado — API administrativa (adm-dadosabertos) ─────────────────────
    DomainType.SERVIDORES,
    DomainType.REMUNERACOES,
    DomainType.DESPESAS_CEAPS,
    # ── Portal da Transparência (CGU) — Poder Executivo ────────────────────
    DomainType.CG_ORGAOS,
    DomainType.CG_SERVIDORES,
    DomainType.CG_REMUNERACOES,
    DomainType.CG_PEP,
    DomainType.CG_VIAGENS,
    DomainType.CG_CARTOES,
    DomainType.CG_IMOVEIS_FUNCIONAIS,
    DomainType.CG_EMENDAS,
    DomainType.CG_CEIS,
    DomainType.CG_CNEP,
    DomainType.CG_CEPIM,
    DomainType.CG_CEAF,
    DomainType.CG_ACORDOS_LENIENCIA,
    DomainType.CG_LICITACOES,
    DomainType.CG_CONTRATOS,
    DomainType.CG_CONTRATOS_ADITIVOS,
    DomainType.CG_CONVENIOS,
    DomainType.CG_CONVENIOS_ADITIVOS,
    DomainType.CG_DESPESAS_EMPENHOS,
    DomainType.CG_DESPESAS_PAGAMENTOS,
)

# Dependências obrigatórias (silver/gold já populado antes do domínio)
DOMAIN_UPSTREAM_REQUIREMENTS: dict[DomainType, frozenset[DomainType]] = {
    DomainType.DESPESAS: frozenset({DomainType.DEPUTADOS}),
    DomainType.VOTOS: frozenset({DomainType.VOTACOES}),
    DomainType.PROFISSÕES: frozenset({DomainType.DEPUTADOS}),
    DomainType.OCUPACOES: frozenset({DomainType.DEPUTADOS}),
    DomainType.DISCURSOS: frozenset({DomainType.DEPUTADOS, DomainType.DEPUTADOS_HISTORICO}),
    DomainType.TRAMITACOES: frozenset({DomainType.PROPOSICOES}),
    DomainType.AUTORES: frozenset({DomainType.PROPOSICOES}),
    DomainType.ORIENTACOES: frozenset({DomainType.VOTACOES}),
    DomainType.ORGAOS_MEMBROS: frozenset({DomainType.ORGAOS}),
    DomainType.FRENTES_MEMBROS: frozenset({DomainType.FRENTES}),
    DomainType.RELACIONADAS: frozenset({DomainType.PROPOSICOES}),
    DomainType.TEMAS: frozenset({DomainType.PROPOSICOES}),
    DomainType.DEPUTADOS_FRENTES: frozenset({DomainType.DEPUTADOS}),
    DomainType.DEPUTADOS_ORGAOS: frozenset({DomainType.DEPUTADOS, DomainType.DEPUTADOS_HISTORICO}),
    DomainType.DEPUTADOS_EVENTOS: frozenset({DomainType.DEPUTADOS, DomainType.DEPUTADOS_HISTORICO}),
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
    # ── Senado ────────────────────────────────────────────────────────────
    DomainType.SENADORES_DETALHE: frozenset({DomainType.SENADORES}),
    DomainType.PROCESSOS_DETALHE: frozenset({DomainType.PROCESSOS}),
    DomainType.PROCESSOS_EMENDAS: frozenset({DomainType.PROCESSOS}),
    DomainType.PROCESSOS_DOCUMENTOS: frozenset({DomainType.PROCESSOS}),
    DomainType.VOTACOES_SENADO: frozenset({DomainType.PROCESSOS}),
    DomainType.VOTOS_SENADO: frozenset({DomainType.VOTACOES_SENADO}),
    DomainType.VOTACOES_COMISSAO: frozenset({DomainType.PROCESSOS, DomainType.COMISSOES_SENADO}),
    DomainType.VETOS_DETALHE: frozenset({DomainType.VETOS_PRESIDENCIAIS}),
    DomainType.SENADORES_DISCURSOS: frozenset({DomainType.SENADORES}),
    DomainType.DISCURSOS_TEXTO: frozenset({DomainType.DISCURSOS_PLENARIO}),
    DomainType.COMISSOES_DETALHE: frozenset({DomainType.COMISSOES_SENADO}),
    DomainType.COMISSOES_REUNIOES: frozenset({DomainType.COMISSOES_SENADO}),
    DomainType.COMISSOES_MEMBROS: frozenset({DomainType.COMISSOES_SENADO}),
    DomainType.ORIENTACAO_BANCADA: frozenset({DomainType.VOTACOES_SENADO}),
    DomainType.SENADORES_MANDATOS: frozenset({DomainType.SENADORES}),
    DomainType.SENADORES_FILIACOES: frozenset({DomainType.SENADORES}),
}


def expand_domains_with_dependencies(requested: Iterable[DomainType]) -> list[DomainType]:
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

    ordered = [d for d in FULL_PIPELINE if d in wanted]
    # Algum domínio fora da tupla fixa aparece ao final preservando sequência solicitada original
    extra = [d for d in requested if d not in ordered]
    seen: set[DomainType] = set()
    out: list[DomainType] = []
    for item in ordered + extra:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
