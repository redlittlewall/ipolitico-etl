"""Metadados declarativos por domínio (watermark, dependências, unique_keys, granularidade bulk)."""

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
    unique_keys: tuple[str, ...] = ("id",)
    sub_domain: str | None = None
    bulk_granularity: str | None = None
    stable: bool = False


def _spec(
    domain: DomainType,
    wm: str | None,
    deps: FrozenSet[DomainType] = frozenset(),
    uk: tuple[str, ...] = ("id",),
    sub: str | None = None,
    stable: bool = False,
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
}


def bulk_meta_for_domain(domain: DomainType) -> dict:
    return BULK_REGISTRY.get(domain.value, {})


def spec_for(domain: DomainType) -> DomainSpec | None:
    return DOMAIN_SPECS.get(domain)
