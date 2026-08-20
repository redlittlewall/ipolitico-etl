"""Metadados declarativos por domínio (watermark, dependências, unique_keys, granularidade bulk)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet

from ipolitico.core.constants import (
    COVERAGE_GAP_YEARS,
    COVERAGE_GAPS,
    EARLIEST_DATE_MAP,
    DomainType,
)
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

# URLs de auditoria para recursos com ID único na API da Câmara.
_SOURCE_URL_FORMATS: dict[DomainType, str] = {
    DomainType.DEPUTADOS: "https://dadosabertos.camara.leg.br/api/v2/deputados/{resource_id}",
    DomainType.PROPOSICOES: "https://dadosabertos.camara.leg.br/api/v2/proposicoes/{resource_id}",
    DomainType.VOTACOES: "https://dadosabertos.camara.leg.br/api/v2/votacoes/{resource_id}",
    DomainType.ORGAOS: "https://dadosabertos.camara.leg.br/api/v2/orgaos/{resource_id}",
    DomainType.PARTIDOS: "https://dadosabertos.camara.leg.br/api/v2/partidos/{resource_id}",
    DomainType.EVENTOS: "https://dadosabertos.camara.leg.br/api/v2/eventos/{resource_id}",
    DomainType.BLOCOS: "https://dadosabertos.camara.leg.br/api/v2/blocos/{resource_id}",
    DomainType.FRENTES: "https://dadosabertos.camara.leg.br/api/v2/frentes/{resource_id}",
    DomainType.GRUPOS: "https://dadosabertos.camara.leg.br/api/v2/grupos/{resource_id}",
    DomainType.LEGISLATURAS: "https://dadosabertos.camara.leg.br/api/v2/legislaturas/{resource_id}",
    DomainType.DEPUTADOS_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/deputados/{resource_id}",
    DomainType.PROPOSICOES_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/proposicoes/{resource_id}",
    DomainType.VOTACOES_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/votacoes/{resource_id}",
    DomainType.ORGAOS_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/orgaos/{resource_id}",
    DomainType.PARTIDOS_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/partidos/{resource_id}",
    DomainType.EVENTOS_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/eventos/{resource_id}",
    DomainType.FRENTES_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/frentes/{resource_id}",
    DomainType.GRUPOS_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/grupos/{resource_id}",
    DomainType.LEGISLATURAS_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/legislaturas/{resource_id}",
    DomainType.BLOCOS_DETALHE: "https://dadosabertos.camara.leg.br/api/v2/blocos/{resource_id}",
    DomainType.VOTOS: "https://dadosabertos.camara.leg.br/api/v2/votacoes/{resource_id}/votos",
    DomainType.ORIENTACOES: "https://dadosabertos.camara.leg.br/api/v2/votacoes/{resource_id}/orientacoes",
    # ── Senado — Entidades raiz ───────────────────────────────────────────────────
    DomainType.SENADORES: "https://legis.senado.leg.br/dadosabertos/senador/{resource_id}",
    DomainType.SENADORES_DETALHE: "https://legis.senado.leg.br/dadosabertos/senador/{resource_id}",
    DomainType.SENADORES_MANDATOS: "https://legis.senado.leg.br/dadosabertos/senador/{resource_id}/mandatos",
    DomainType.SENADORES_FILIACOES: "https://legis.senado.leg.br/dadosabertos/senador/{resource_id}/filiacoes",
    DomainType.PROCESSOS: "https://legis.senado.leg.br/dadosabertos/materia/{resource_id}",
    DomainType.PROCESSOS_DETALHE: "https://legis.senado.leg.br/dadosabertos/materia/{resource_id}",
    DomainType.PROCESSOS_EMENDAS: "https://legis.senado.leg.br/dadosabertos/materia/{resource_id}/emendas",
    DomainType.PROCESSOS_DOCUMENTOS: "https://legis.senado.leg.br/dadosabertos/materia/{resource_id}/documentos",
    DomainType.VOTACOES_SENADO: "https://legis.senado.leg.br/dadosabertos/votacao/{resource_id}",
    DomainType.VOTACOES_COMISSAO: "https://legis.senado.leg.br/dadosabertos/votacao/{resource_id}",
    DomainType.COMISSOES_SENADO: "https://legis.senado.leg.br/dadosabertos/comissao/{resource_id}",
    DomainType.COMISSOES_DETALHE: "https://legis.senado.leg.br/dadosabertos/comissao/{resource_id}",
    DomainType.BLOCOS_SENADO: "https://legis.senado.leg.br/dadosabertos/bloco/{resource_id}",
    DomainType.VETOS_PRESIDENCIAIS: "https://legis.senado.leg.br/dadosabertos/veto/{resource_id}",
    DomainType.VETOS_DETALHE: "https://legis.senado.leg.br/dadosabertos/veto/{resource_id}",
    DomainType.SENADORES_DISCURSOS: "https://legis.senado.leg.br/dadosabertos/senador/{resource_id}/discursos",
}


@dataclass(frozen=True)
class DomainSpec:
    domain: DomainType
    watermark_column: str | None
    earliest_iso: str
    depends_on: FrozenSet[DomainType]
    unique_keys: tuple[str, ...] = ("id",)
    sub_domain: str | None = None
    bulk_granularity: str | None = None
    stable: bool = False
    source_url_format: str | None = None
    coverage_gaps: tuple[str, ...] = ()
    coverage_gap_years: tuple[int, ...] = ()


def _spec(
    domain: DomainType,
    wm: str | None,
    deps: FrozenSet[DomainType] = frozenset(),
    uk: tuple[str, ...] = ("id",),
    sub: str | None = None,
    stable: bool = False,
    source_url_format: str | None = None,
) -> DomainSpec:
    meta = BULK_REGISTRY.get(domain.value, {})
    return DomainSpec(
        domain=domain,
        watermark_column=wm,
        earliest_iso=EARLIEST_DATE_MAP.get(domain, "1826-04-29"),
        depends_on=deps,
        unique_keys=uk,
        sub_domain=sub,
        bulk_granularity=meta.get("bulk_granularity"),
        stable=stable,
        source_url_format=source_url_format or _SOURCE_URL_FORMATS.get(domain),
        coverage_gaps=COVERAGE_GAPS.get(domain.value, ()),
        coverage_gap_years=COVERAGE_GAP_YEARS.get(domain.value, ()),
    )


DOMAIN_SPECS: dict[DomainType, DomainSpec] = {
    DomainType.DEPUTADOS: _spec(DomainType.DEPUTADOS, None),
    DomainType.DESPESAS: _spec(
        DomainType.DESPESAS,
        "dataDocumento",
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "numDocumento", "codDocumento", "parcela", "valorLiquido"),
    ),
    DomainType.PROPOSICOES: _spec(DomainType.PROPOSICOES, "dataApresentacao"),
    DomainType.VOTACOES: _spec(DomainType.VOTACOES, "data", sub="votacoes"),
    DomainType.VOTOS: _spec(
        DomainType.VOTOS,
        None,
        frozenset({DomainType.VOTACOES}),
        uk=("id_deputado", "votacao_id"),
        sub="votos",
    ),
    DomainType.PROFISSÕES: _spec(
        DomainType.PROFISSÕES,
        None,
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "titulo", "entidade", "anoInicio"),
        sub="profissoes",
    ),
    DomainType.OCUPACOES: _spec(
        DomainType.OCUPACOES,
        None,
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "titulo", "entidade", "anoInicio"),
        sub="ocupacoes",
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
        uk=("id_deputado", "dataHoraInicio"),
    ),
    DomainType.TRAMITACOES: _spec(
        DomainType.TRAMITACOES,
        None,
        frozenset({DomainType.PROPOSICOES}),
        uk=("id_proposicao", "sequencia"),
        sub="tramitacoes",
    ),
    DomainType.AUTORES: _spec(
        DomainType.AUTORES,
        None,
        frozenset({DomainType.PROPOSICOES}),
        uk=("id_proposicao", "ordemAssinatura", "nome"),
        sub="autores",
    ),
    DomainType.ORIENTACOES: _spec(
        DomainType.ORIENTACOES,
        None,
        frozenset({DomainType.VOTACOES}),
        uk=("votacao_id", "codPartidoBloco", "codTipoLideranca"),
    ),
    DomainType.ORGAOS_MEMBROS: _spec(
        DomainType.ORGAOS_MEMBROS,
        None,
        frozenset({DomainType.ORGAOS}),
        uk=("id_orgao", "id", "codTitulo", "dataInicio"),
        sub="orgaos_membros",
    ),
    DomainType.FRENTES_MEMBROS: _spec(
        DomainType.FRENTES_MEMBROS,
        None,
        frozenset({DomainType.FRENTES}),
        uk=("id_frente", "id", "codTitulo", "dataInicio"),
        sub="frentes_membros",
    ),
    DomainType.RELACIONADAS: _spec(
        DomainType.RELACIONADAS,
        None,
        frozenset({DomainType.PROPOSICOES}),
        uk=("id_proposicao", "id"),
        sub="relacionadas",
    ),
    DomainType.TEMAS: _spec(
        DomainType.TEMAS,
        None,
        frozenset({DomainType.PROPOSICOES}),
        uk=("id_proposicao", "tema"),
        sub="temas",
    ),
    DomainType.DEPUTADOS_FRENTES: _spec(
        DomainType.DEPUTADOS_FRENTES,
        None,
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "id"),
        sub="deputados_frentes",
    ),
    DomainType.DEPUTADOS_ORGAOS: _spec(
        DomainType.DEPUTADOS_ORGAOS,
        None,
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "id", "dataInicio"),
        sub="deputados_orgaos",
    ),
    DomainType.DEPUTADOS_EVENTOS: _spec(
        DomainType.DEPUTADOS_EVENTOS,
        None,
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "id", "dataInicio"),
        sub="deputados_eventos",
    ),
    DomainType.DEPUTADOS_HISTORICO: _spec(
        DomainType.DEPUTADOS_HISTORICO,
        None,
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "dataStatus", "idLegislatura"),
        sub="deputados_historico",
    ),
    DomainType.MANDATOS_EXTERNOS: _spec(
        DomainType.MANDATOS_EXTERNOS,
        None,
        frozenset({DomainType.DEPUTADOS}),
        uk=("id_deputado", "anoInicio", "cargo", "siglaPartidoEleicao"),
        sub="mandatos_externos",
    ),
    DomainType.EVENTOS_DEPUTADOS: _spec(
        DomainType.EVENTOS_DEPUTADOS,
        None,
        frozenset({DomainType.EVENTOS}),
        uk=("id_evento", "id"),
        sub="eventos_deputados",
    ),
    DomainType.EVENTOS_VOTACOES: _spec(
        DomainType.EVENTOS_VOTACOES,
        None,
        frozenset({DomainType.EVENTOS}),
        uk=("id_evento", "id"),
        sub="eventos_votacoes",
    ),
    DomainType.EVENTOS_PAUTA: _spec(
        DomainType.EVENTOS_PAUTA,
        None,
        frozenset({DomainType.EVENTOS}),
        uk=("id_evento", "ordem"),
        sub="eventos_pauta",
    ),
    DomainType.PARTIDOS_MEMBROS: _spec(
        DomainType.PARTIDOS_MEMBROS,
        None,
        frozenset({DomainType.PARTIDOS}),
        uk=("id_partido", "id"),
        sub="partidos_membros",
    ),
    DomainType.PARTIDOS_LIDERES: _spec(
        DomainType.PARTIDOS_LIDERES,
        None,
        frozenset({DomainType.PARTIDOS}),
        uk=("id_partido", "id", "titulo", "dataInicio"),
        sub="partidos_lideres",
    ),
    DomainType.PROPOSICOES_VOTACOES: _spec(
        DomainType.PROPOSICOES_VOTACOES,
        None,
        frozenset({DomainType.PROPOSICOES}),
        uk=("id_proposicao", "id"),
        sub="proposicoes_votacoes",
    ),
    DomainType.BLOCOS_PARTIDOS: _spec(
        DomainType.BLOCOS_PARTIDOS,
        None,
        frozenset({DomainType.BLOCOS}),
        uk=("id_bloco", "id"),
        sub="blocos_partidos",
    ),
    DomainType.REFERENCIAS: _spec(
        DomainType.REFERENCIAS,
        None,
        uk=("referencia", "cod", "sigla", "nome"),
        stable=True,
    ),
    DomainType.DEPUTADOS_DETALHE: _spec(
        DomainType.DEPUTADOS_DETALHE,
        None,
        frozenset({DomainType.DEPUTADOS}),
        sub="deputados_detalhe",
    ),
    DomainType.ORGAOS_DETALHE: _spec(
        DomainType.ORGAOS_DETALHE,
        None,
        frozenset({DomainType.ORGAOS}),
        sub="orgaos_detalhe",
    ),
    DomainType.EVENTOS_DETALHE: _spec(
        DomainType.EVENTOS_DETALHE,
        None,
        frozenset({DomainType.EVENTOS}),
        sub="eventos_detalhe",
    ),
    DomainType.VOTACOES_DETALHE: _spec(
        DomainType.VOTACOES_DETALHE,
        None,
        frozenset({DomainType.VOTACOES}),
        sub="votacoes_detalhe",
    ),
    DomainType.FRENTES_DETALHE: _spec(
        DomainType.FRENTES_DETALHE,
        None,
        frozenset({DomainType.FRENTES}),
        sub="frentes_detalhe",
    ),
    DomainType.PARTIDOS_DETALHE: _spec(
        DomainType.PARTIDOS_DETALHE,
        None,
        frozenset({DomainType.PARTIDOS}),
        sub="partidos_detalhe",
    ),
    DomainType.GRUPOS_DETALHE: _spec(
        DomainType.GRUPOS_DETALHE,
        None,
        frozenset({DomainType.GRUPOS}),
        sub="grupos_detalhe",
    ),
    DomainType.LEGISLATURAS_DETALHE: _spec(
        DomainType.LEGISLATURAS_DETALHE,
        None,
        frozenset({DomainType.LEGISLATURAS}),
        sub="legislaturas_detalhe",
    ),
    DomainType.BLOCOS_DETALHE: _spec(
        DomainType.BLOCOS_DETALHE,
        None,
        frozenset({DomainType.BLOCOS}),
        sub="blocos_detalhe",
    ),
    DomainType.PROPOSICOES_DETALHE: _spec(
        DomainType.PROPOSICOES_DETALHE,
        None,
        frozenset({DomainType.PROPOSICOES}),
        sub="proposicoes_detalhe",
    ),
    DomainType.EVENTOS_ORGAOS: _spec(
        DomainType.EVENTOS_ORGAOS,
        None,
        frozenset({DomainType.EVENTOS}),
        uk=("id_evento", "id"),
        sub="eventos_orgaos",
    ),
    DomainType.ORGAOS_EVENTOS: _spec(
        DomainType.ORGAOS_EVENTOS,
        None,
        frozenset({DomainType.ORGAOS}),
        uk=("id_orgao", "id", "dataHoraInicio"),
        sub="orgaos_eventos",
    ),
    DomainType.ORGAOS_VOTACOES: _spec(
        DomainType.ORGAOS_VOTACOES,
        None,
        frozenset({DomainType.ORGAOS}),
        uk=("id_orgao", "id"),
        sub="orgaos_votacoes",
    ),
    DomainType.GRUPOS_MEMBROS: _spec(
        DomainType.GRUPOS_MEMBROS,
        None,
        frozenset({DomainType.GRUPOS}),
        uk=("id_grupo", "id"),
        sub="grupos_membros",
    ),
    DomainType.GRUPOS_HISTORICO: _spec(
        DomainType.GRUPOS_HISTORICO,
        None,
        frozenset({DomainType.GRUPOS}),
        uk=("id_grupo", "data", "descricao"),
        sub="grupos_historico",
    ),
    DomainType.LEGISLATURAS_LIDERES: _spec(
        DomainType.LEGISLATURAS_LIDERES,
        None,
        frozenset({DomainType.LEGISLATURAS}),
        uk=("id_legislatura", "id", "titulo", "dataInicio"),
        sub="legislaturas_lideres",
    ),
    DomainType.LEGISLATURAS_MESA: _spec(
        DomainType.LEGISLATURAS_MESA,
        None,
        frozenset({DomainType.LEGISLATURAS}),
        uk=("id_legislatura", "id", "titulo", "dataInicio"),
        sub="legislaturas_mesa",
    ),
    # ── Domínios bulk-only (Fase 3) ────────────────────────────────────────
    DomainType.FUNCIONARIOS: _spec(
        DomainType.FUNCIONARIOS,
        None,
        uk=("ponto",),
        stable=True,
    ),
    DomainType.TECAD_CATEGORIAS: _spec(
        DomainType.TECAD_CATEGORIAS,
        None,
        uk=("codCategoria", "codSubCategoria"),
        stable=True,
    ),
    DomainType.TECAD_TERMOS: _spec(
        DomainType.TECAD_TERMOS,
        None,
        uk=("codTermo",),
        stable=True,
    ),
    # ── Domínios bulk-only de eventos/votações (Fase 3) ──────────────────────
    DomainType.EVENTOS_PRESENCA_DEPUTADOS: _spec(
        DomainType.EVENTOS_PRESENCA_DEPUTADOS,
        None,
        uk=("idEvento", "idDeputado"),
        stable=True,
    ),
    DomainType.EVENTOS_REQUERIMENTOS: _spec(
        DomainType.EVENTOS_REQUERIMENTOS,
        None,
        uk=("idEvento", "tituloRequerimento", "uriRequerimento"),
        stable=True,
    ),
    DomainType.VOTACOES_OBJETOS: _spec(
        DomainType.VOTACOES_OBJETOS,
        None,
        uk=("idVotacao", "proposicao_id"),
        stable=True,
    ),
    DomainType.VOTACOES_PROPOSICOES: _spec(
        DomainType.VOTACOES_PROPOSICOES,
        None,
        uk=("idVotacao", "proposicao_id"),
        stable=True,
    ),
    # ── Domínios bulk-only de licitações (Fase 3) ────────────────────────────
    DomainType.LICITACOES: _spec(
        DomainType.LICITACOES,
        None,
        uk=("idLicitacao",),
        stable=True,
    ),
    DomainType.LICITACOES_CONTRATOS: _spec(
        DomainType.LICITACOES_CONTRATOS,
        None,
        uk=("idLicitacao", "numContrato", "anoContrato"),
        stable=True,
    ),
    DomainType.LICITACOES_ITENS: _spec(
        DomainType.LICITACOES_ITENS,
        None,
        uk=("idLicitacao", "numItem", "numSubitem"),
        stable=True,
    ),
    DomainType.LICITACOES_PEDIDOS: _spec(
        DomainType.LICITACOES_PEDIDOS,
        None,
        uk=("idLicitacao", "numPedido", "anoPedido"),
        stable=True,
    ),
    DomainType.LICITACOES_PROPOSTAS: _spec(
        DomainType.LICITACOES_PROPOSTAS,
        None,
        uk=("idLicitacao", "numItem", "numProposta", "fornecedorCpfCnpj"),
        stable=True,
    ),
    # ── Domínio bulk-only mensal (issue 04) — folha de pagamento consolidada ──
    # NÃO estável: o consolidado é republicado mensalmente com os valores do mês
    # fechado. Anos com 404 (lacuna) são pulados pelo planner via coverage_gap_years.
    DomainType.FOLHA_PAGAMENTO: _spec(
        DomainType.FOLHA_PAGAMENTO,
        None,
        uk=("_source_url", "cargo", "grupo_funcional"),
    ),
    # ── Domínios do Senado (Fase 1) ─────────────────────────────────────────
    DomainType.SENADORES: _spec(DomainType.SENADORES, None),
    DomainType.SENADORES_DETALHE: _spec(
        DomainType.SENADORES_DETALHE,
        None,
        frozenset({DomainType.SENADORES}),
        uk=("codigo",),
    ),
    DomainType.PROCESSOS: _spec(DomainType.PROCESSOS, "dataApresentacao"),
    DomainType.PROCESSOS_DETALHE: _spec(
        DomainType.PROCESSOS_DETALHE, None, frozenset({DomainType.PROCESSOS})
    ),
    DomainType.PROCESSOS_EMENDAS: _spec(
        DomainType.PROCESSOS_EMENDAS, "dataApresentacao", frozenset({DomainType.PROCESSOS})
    ),
    DomainType.PROCESSOS_DOCUMENTOS: _spec(
        DomainType.PROCESSOS_DOCUMENTOS, "data", frozenset({DomainType.PROCESSOS})
    ),
    DomainType.VOTACOES_SENADO: _spec(
        DomainType.VOTACOES_SENADO, "dataSessao", frozenset({DomainType.PROCESSOS})
    ),
    DomainType.VOTOS_SENADO: _spec(
        DomainType.VOTOS_SENADO,
        None,
        frozenset({DomainType.VOTACOES_SENADO}),
        uk=("codigoParlamentar", "votacao_id"),
    ),
    DomainType.VOTACOES_COMISSAO: _spec(
        DomainType.VOTACOES_COMISSAO,
        "dataSessao",
        frozenset({DomainType.PROCESSOS, DomainType.COMISSOES_SENADO}),
    ),
    DomainType.ORCAMENTO_EMENDAS: _spec(DomainType.ORCAMENTO_EMENDAS, None),
    DomainType.ORCAMENTO_OFICIOS: _spec(DomainType.ORCAMENTO_OFICIOS, None),
    DomainType.VETOS_PRESIDENCIAIS: _spec(DomainType.VETOS_PRESIDENCIAIS, None),
    DomainType.VETOS_DETALHE: _spec(
        DomainType.VETOS_DETALHE, None, frozenset({DomainType.VETOS_PRESIDENCIAIS})
    ),
    DomainType.SENADORES_DISCURSOS: _spec(
        DomainType.SENADORES_DISCURSOS, "data", frozenset({DomainType.SENADORES})
    ),
    DomainType.DISCURSOS_PLENARIO: _spec(DomainType.DISCURSOS_PLENARIO, "data"),
    DomainType.DISCURSOS_TEXTO: _spec(
        DomainType.DISCURSOS_TEXTO, None, frozenset({DomainType.DISCURSOS_PLENARIO})
    ),
    DomainType.NOTAS_TAQUIGRAFIA_SESSAO: _spec(
        DomainType.NOTAS_TAQUIGRAFIA_SESSAO, None, frozenset({DomainType.PLENARIO_SESSOES})
    ),
    DomainType.NOTAS_TAQUIGRAFIA_REUNIAO: _spec(
        DomainType.NOTAS_TAQUIGRAFIA_REUNIAO, None, frozenset({DomainType.COMISSOES_REUNIOES})
    ),
    DomainType.COMISSOES_SENADO: _spec(DomainType.COMISSOES_SENADO, None),
    DomainType.COMISSOES_DETALHE: _spec(
        DomainType.COMISSOES_DETALHE, None, frozenset({DomainType.COMISSOES_SENADO})
    ),
    DomainType.COMISSOES_REUNIOES: _spec(
        DomainType.COMISSOES_REUNIOES, "data", frozenset({DomainType.COMISSOES_SENADO})
    ),
    DomainType.COMISSOES_MEMBROS: _spec(
        DomainType.COMISSOES_MEMBROS, None, frozenset({DomainType.COMISSOES_SENADO})
    ),
    DomainType.PLENARIO_AGENDA: _spec(DomainType.PLENARIO_AGENDA, "data"),
    DomainType.PLENARIO_RESULTADOS: _spec(DomainType.PLENARIO_RESULTADOS, "data"),
    DomainType.PLENARIO_SESSOES: _spec(DomainType.PLENARIO_SESSOES, "data"),
    DomainType.BLOCOS_SENADO: _spec(DomainType.BLOCOS_SENADO, None),
    DomainType.LIDERANCAS_SENADO: _spec(DomainType.LIDERANCAS_SENADO, None),
    DomainType.MESA_SENADO: _spec(DomainType.MESA_SENADO, None),
    DomainType.MESA_CONGRESSO: _spec(DomainType.MESA_CONGRESSO, None),
    DomainType.SENADORES_MANDATOS: _spec(
        DomainType.SENADORES_MANDATOS,
        None,
        frozenset({DomainType.SENADORES}),
        uk=("codigo", "codigo_mandato"),
    ),
    DomainType.SENADORES_FILIACOES: _spec(
        DomainType.SENADORES_FILIACOES,
        None,
        frozenset({DomainType.SENADORES}),
        uk=("codigo", "data_filiacao"),
    ),
    DomainType.ORIENTACAO_BANCADA: _spec(
        DomainType.ORIENTACAO_BANCADA,
        "data_sessao",
        frozenset({DomainType.VOTACOES_SENADO}),
        uk=("codigo_votacao", "sigla_partido"),
    ),
    # ── Senado — API administrativa (adm-dadosabertos, issue 07) ─────────────
    # Snapshot (roster completo numa chamada, sem paginação), chave por
    # ``sequencial``. NÃO estável (diferente dos bulk-only estáveis — ex:
    # FUNCIONARIOS/TECAD — que são arquivos publicados imutáveis): o roster é
    # uma visão VIVA do quadro — vínculo/situação mudam e desligados se acumulam
    # (survey: DESLIGADO 12.227 de 22.916) — então o incremental deve re-extrair
    # (não pular), mesmo custo da FOLHA_PAGAMENTO não-estável.
    DomainType.SERVIDORES: _spec(DomainType.SERVIDORES, None, uk=("sequencial",)),
    # ── Senado — API administrativa (adm-dadosabertos, issue 08) ─────────────
    # Bulk mensal nomeado (path ``{ano}/{mes}``): 1 arquivo por (ano, mês),
    # chave por (``_source_url``, ``sequencial``, ``tipo_folha``) — o mesmo
    # servidor pode aparecer em ``Normal`` e ``Suplementar`` no mesmo mês.
    # NÃO estável (mesmo padrão da FOLHA_PAGAMENTO): o incremental re-extrai —
    # a folha pode ser corrigida (ex: folha suplementar) e não há custo de
    # saltar o snapshot. 404 (pré-2013) = ausência permanente; mês corrente não
    # publicado = 200 com lista vazia (ausência temporária) — ver COVERAGE_GAPS.
    DomainType.REMUNERACOES: _spec(
        DomainType.REMUNERACOES,
        None,
        uk=("_source_url", "sequencial", "tipo_folha"),
    ),
    # ── Senado — API administrativa (adm-dadosabertos, issue 09) ─────────────
    # Bulk ANUAL (path ``{ano}`` — 1 job por ano, sem mês no path), mas o
    # payload carrega ``mes`` → granularidade efetiva mês via 1 request por ano.
    # Chave por (``_source_url``, ``id``): o ``id`` é globalmente único na
    # fonte (verificado em 2008 vs 2025) e ``_source_url`` (URL anual) escopa a
    # chave para replay. NÃO estável (mesmo padrão da FOLHA_PAGAMENTO): o ano
    # corrente cresce a cada mês e o incremental re-extrai — o Gold deduplica.
    # 404 (pré-2008) = ausência permanente — ver COVERAGE_GAPS.
    DomainType.DESPESAS_CEAPS: _spec(
        DomainType.DESPESAS_CEAPS,
        None,
        uk=("_source_url", "id"),
    ),
    # ── Portal da Transparência (CGU) — Poder Executivo (ticket 02) ─────────────
    # Snapshot de órgãos SIAPE via API v3 ``/api-de-dados/orgaos-siape`` (a
    # validação real corrigiu a fonte: não existe bulk de órgãos no portal).
    # Chave por ``codigo`` (único na fonte). NÃO estável (mesmo padrão de
    # SERVIDORES): a estrutura do Executivo muda (novos órgãos), então o
    # incremental re-extrai o snapshot — o Gold deduplica.
    DomainType.CG_ORGAOS: _spec(
        DomainType.CG_ORGAOS,
        None,
        uk=("codigo",),
    ),
    # ── Portal da Transparência (CGU) — Poder Executivo (ticket 03) ─────────────
    # Snapshot do agregado ``/servidores/por-orgao`` (API v3 — validado real no
    # ticket 03). Chave por (órgão, situação, tipo de servidor, tipo de vínculo,
    # licença): o agregado tem UMA linha por combinação dessas dimensões
    # (contagens ``qntPessoas``/``qntVinculos``). NÃO estável (mesmo padrão de
    # CG_ORGAOS): as contagens mudam a cada snapshot — o Gold deduplica.
    DomainType.CG_SERVIDORES: _spec(
        DomainType.CG_SERVIDORES,
        None,
        uk=("codOrgaoExercicioSiape", "skSituacao", "skTipoServidor", "skTipoVinculo", "licenca"),
    ),
    # Bulk mensal ``/download-de-dados/servidores/{YYYYMM}`` — ingestão
    # REGISTRADA mas BLOQUEADA pelo WAF/CAPTCHA (validação real do ticket 03).
    # Chave por (``_source_url``, ``id_servidor``, ``mes_ano``) — ``_source_url``
    # escopa o replay para o mês do dump. NÃO estável (mesmo padrão de
    # FOLHA_PAGAMENTO): o mês corrente cresce e o incremental re-extrai — o Gold
    # deduplica. Earliest é placeholder (2017-01) a validar na liberação do WAF.
    DomainType.CG_REMUNERACOES: _spec(
        DomainType.CG_REMUNERACOES,
        None,
        uk=("_source_url", "id_servidor", "mes_ano"),
    ),
    # ── Portal da Transparência (CGU) — Poder Executivo (ticket 04) ─────────────
    # PEPs (Pessoas Expostas Politicamente) — bulk anual `pep`. Validação real:
    # a API exige ≥1 filtro (impossível enumerar) e o dump está INDISPONÍVEL
    # hoje (403 AccessDenied) → contrato provisório derivado do JSON da API.
    # Chave por (cpf, órgão, função, início) — CPF mascarado é estável por
    # pessoa; `_source_url` escopa o replay anual. NÃO estável (mesmo padrão de
    # CG_REMUNERACOES).
    DomainType.CG_PEP: _spec(
        DomainType.CG_PEP,
        None,
        uk=("_source_url", "cpf", "cod_orgao", "sigla_funcao", "dt_inicio_exercicio"),
    ),
    # Viagens de servidores — bulk ANUAL `viagens` (validação real: não há
    # dumps mensais {YYYYMM}; a API exige codigoOrgao+4 datas, inviável
    # enumerar). O CSV real capturado NÃO tem `id` numérico — a chave é o
    # ``identificador_processo_viagem`` (único no dump verificado: 855.805
    # linhas = 855.805 identificadores distintos em 2016), escopada por
    # ``_source_url`` no replay anual. NÃO estável (mesmo padrão de
    # CG_REMUNERACOES).
    DomainType.CG_VIAGENS: _spec(
        DomainType.CG_VIAGENS,
        None,
        uk=("_source_url", "identificador_processo_viagem"),
    ),
    # Cartões de pagamento (CPGF/CPCC/CPDC) — rota dupla (ticket 04): bulk
    # mensal + API v3 em blocos mensais (≤12 meses). O dump bulk NÃO tem `id`.
    # Chave = identidade composta (tipoCartao, mês, data, valor, CPF portador,
    # CNPJ/CPF favorecido, UG) + `id` da API.
    #
    # CORREÇÃO DA VALIDAÇÃO REAL (19/08): a premissa do ticket "risco de
    # colisão ≈ zero (7 campos)" estava errada. Na API, ~5% das linhas/mês (645
    # linhas, 197 grupos em 06/2025) são transações DISTINTAS com documentos
    # mascarados ("SEM INFORMACAO", "NAO SE APLICA", beneficiários CPDC) — a
    # composta sozinha as fundiria, perdendo valor monetário no Gold. O `id` da
    # API é o único discriminador dessas linhas. Com `id` na UK:
    #   - rota API: nunca funde transações distintas (id único);
    #   - rota bulk: id nulo → a composta deduplica os duplicados exatos de
    #     fonte (linhas "Sigiloso" re-publicadas N vezes pelo governo);
    #   - overlap bulk×API NÃO deduplica (id nulo vs real) — limitação
    #     documentada: rodar as duas rotas no mesmo mês duplica no Gold; o
    #     usuário escolhe a estratégia por janela. NÃO estável (CG_SERVIDORES).
    DomainType.CG_CARTOES: _spec(
        DomainType.CG_CARTOES,
        None,
        uk=(
            "tipoCartao_codigo",
            "mesExtrato",
            "dataTransacao",
            "valorTransacao",
            "portador_cpfFormatado",
            "favorecido_cpfCnpj",
            "unidadeGestora_codigo",
            "id",
        ),
    ),
    # Imóveis funcionais da União — snapshot via API v3 (walk livre com pagina;
    # o dump bulk `imoveis-funcionais` está indisponível hoje — 403). Chave por
    # `id` (único na fonte). NÃO estável (mesmo padrão de CG_ORGAOS: a situação
    # do imóvel muda entre snapshots — o Gold deduplica).
    DomainType.CG_IMOVEIS_FUNCIONAIS: _spec(
        DomainType.CG_IMOVEIS_FUNCIONAIS,
        None,
        uk=("id",),
    ),
    # Emendas parlamentares — API v3 POR ANO (param `ano`; "respeita a janela
    # da API por ano" do ticket). O dump bulk `emendas-parlamentares` é um
    # arquivo único que re-publica o histórico inteiro a cada geração — conflita
    # com o append-only → sem rota bulk (padrão CG_SERVIDORES). Chave por
    # `codigoEmenda` (único na fonte — embute o ano). NÃO estável (mesmo padrão
    # de CG_ORGAOS: valores executados mudam — o Gold deduplica).
    DomainType.CG_EMENDAS: _spec(
        DomainType.CG_EMENDAS,
        None,
        uk=("codigoEmenda",),
    ),
}


def bulk_meta_for_domain(domain: DomainType) -> dict:
    return BULK_REGISTRY.get(domain.value, {})


def spec_for(domain: DomainType) -> DomainSpec | None:
    return DOMAIN_SPECS.get(domain)
