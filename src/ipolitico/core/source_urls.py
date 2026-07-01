"""Padrões de URL de referência por domínio para auditabilidade.

Cada domínio mapeia para um template de URL que aponta para o recurso
correspondente na API oficial (Câmara ou Senado). A coluna ``_source_url``
é adicionada a todo registro na camada Silver, permitindo que qualquer
cidadão verifique a fonte oficial dos dados.

Domínios bulk-only (CSV) não possuem URL de API por registro individual.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl

from ipolitico.core.config import CAMARA_API_BASE_URL, SENADO_API_BASE_URL
from ipolitico.core.constants import DomainType

_CAMARA_BASE = CAMARA_API_BASE_URL.rstrip("/")
_SENADO_BASE = SENADO_API_BASE_URL.rstrip("/")

# ── Conjunto de domínios do Senado (para rotear base URL) ─────────────────────
_SENADO_DOMAINS: frozenset[DomainType] = frozenset(
    {
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
    }
)

# ── Domínios bulk-only (sem URL de API por registro) ──────────────────────────
_BULK_ONLY_DOMAINS: frozenset[DomainType] = frozenset(
    {
        DomainType.FUNCIONARIOS,
        DomainType.TECAD_CATEGORIAS,
        DomainType.TECAD_TERMOS,
        DomainType.EVENTOS_PRESENCA_DEPUTADOS,
        DomainType.EVENTOS_REQUERIMENTOS,
        DomainType.VOTACOES_OBJETOS,
        DomainType.VOTACOES_PROPOSICOES,
        DomainType.LICITACOES,
        DomainType.LICITACOES_CONTRATOS,
        DomainType.LICITACOES_ITENS,
        DomainType.LICITACOES_PEDIDOS,
        DomainType.LICITACOES_PROPOSTAS,
    }
)

# ── Templates de URL por domínio ──────────────────────────────────────────────
# O placeholder ``{base}`` é resolvido automaticamente para a base da API
# correta (Câmara ou Senado). Os demais placeholders ``{coluna}`` são
# resolvidos a partir dos valores das colunas de cada registro.
SOURCE_URL_TEMPLATES: dict[DomainType, str] = {
    # ── Câmara — Entidades raiz ────────────────────────────────────────────────
    DomainType.DEPUTADOS: "{base}/deputados/{id}",
    DomainType.PROPOSICOES: "{base}/proposicoes/{id}",
    DomainType.VOTACOES: "{base}/votacoes/{id}",
    DomainType.ORGAOS: "{base}/orgaos/{id}",
    DomainType.PARTIDOS: "{base}/partidos/{id}",
    DomainType.EVENTOS: "{base}/eventos/{id}",
    DomainType.BLOCOS: "{base}/blocos/{id}",
    DomainType.FRENTES: "{base}/frentes/{id}",
    DomainType.GRUPOS: "{base}/grupos/{id}",
    DomainType.LEGISLATURAS: "{base}/legislaturas/{id}",
    # ── Câmara — Detalhe ───────────────────────────────────────────────────────
    DomainType.DEPUTADOS_DETALHE: "{base}/deputados/{id}",
    DomainType.ORGAOS_DETALHE: "{base}/orgaos/{id}",
    DomainType.EVENTOS_DETALHE: "{base}/eventos/{id}",
    DomainType.VOTACOES_DETALHE: "{base}/votacoes/{id}",
    DomainType.FRENTES_DETALHE: "{base}/frentes/{id}",
    DomainType.PARTIDOS_DETALHE: "{base}/partidos/{id}",
    DomainType.GRUPOS_DETALHE: "{base}/grupos/{id}",
    DomainType.LEGISLATURAS_DETALHE: "{base}/legislaturas/{id}",
    DomainType.BLOCOS_DETALHE: "{base}/blocos/{id}",
    DomainType.PROPOSICOES_DETALHE: "{base}/proposicoes/{id}",
    # ── Câmara — Filhos de Deputados ───────────────────────────────────────────
    DomainType.DESPESAS: "{base}/deputados/{id_deputado}/despesas",
    DomainType.DISCURSOS: "{base}/deputados/{id_deputado}/discursos",
    DomainType.PROFISSÕES: "{base}/deputados/{id_deputado}/profissoes",
    DomainType.OCUPACOES: "{base}/deputados/{id_deputado}/ocupacoes",
    DomainType.DEPUTADOS_FRENTES: "{base}/deputados/{id_deputado}/frentes",
    DomainType.DEPUTADOS_ORGAOS: "{base}/deputados/{id_deputado}/orgaos",
    DomainType.DEPUTADOS_EVENTOS: "{base}/deputados/{id_deputado}/eventos",
    DomainType.DEPUTADOS_HISTORICO: "{base}/deputados/{id_deputado}/historico",
    DomainType.MANDATOS_EXTERNOS: "{base}/deputados/{id_deputado}/mandatosExternos",
    # ── Câmara — Filhos de Proposições ────────────────────────────────────────
    DomainType.TRAMITACOES: "{base}/proposicoes/{id_proposicao}/tramitacoes",
    DomainType.AUTORES: "{base}/proposicoes/{id_proposicao}/autores",
    DomainType.RELACIONADAS: "{base}/proposicoes/{id_proposicao}/relacionadas",
    DomainType.TEMAS: "{base}/proposicoes/{id_proposicao}/temas",
    DomainType.PROPOSICOES_VOTACOES: "{base}/proposicoes/{id_proposicao}/votacoes",
    # ── Câmara — Filhos de Votações ────────────────────────────────────────────
    DomainType.VOTOS: "{base}/votacoes/{votacao_id}/votos",
    DomainType.ORIENTACOES: "{base}/votacoes/{votacao_id}/orientacoes",
    # ── Câmara — Filhos de Eventos ─────────────────────────────────────────────
    DomainType.EVENTOS_DEPUTADOS: "{base}/eventos/{id_evento}/deputados",
    DomainType.EVENTOS_VOTACOES: "{base}/eventos/{id_evento}/votacoes",
    DomainType.EVENTOS_PAUTA: "{base}/eventos/{id_evento}/pauta",
    DomainType.EVENTOS_ORGAOS: "{base}/eventos/{id_evento}/orgaos",
    # ── Câmara — Filhos de Órgãos ──────────────────────────────────────────────
    DomainType.ORGAOS_MEMBROS: "{base}/orgaos/{id_orgao}/membros",
    DomainType.ORGAOS_EVENTOS: "{base}/orgaos/{id_orgao}/eventos",
    DomainType.ORGAOS_VOTACOES: "{base}/orgaos/{id_orgao}/votacoes",
    # ── Câmara — Filhos de Partidos ────────────────────────────────────────────
    DomainType.PARTIDOS_MEMBROS: "{base}/partidos/{id_partido}/membros",
    DomainType.PARTIDOS_LIDERES: "{base}/partidos/{id_partido}/lideres",
    # ── Câmara — Filhos de Blocos ──────────────────────────────────────────────
    DomainType.BLOCOS_PARTIDOS: "{base}/blocos/{id_bloco}/partidos",
    # ── Câmara — Filhos de Grupos ───────────────────────────────────────────────
    DomainType.GRUPOS_MEMBROS: "{base}/grupos/{id_grupo}/membros",
    DomainType.GRUPOS_HISTORICO: "{base}/grupos/{id_grupo}/historico",
    # ── Câmara — Filhos de Legislaturas ─────────────────────────────────────────
    DomainType.LEGISLATURAS_LIDERES: "{base}/legislaturas/{id_legislatura}/lideres",
    DomainType.LEGISLATURAS_MESA: "{base}/legislaturas/{id_legislatura}/mesa",
    # ── Câmara — Referências ────────────────────────────────────────────────────
    DomainType.REFERENCIAS: "{base}/referencias/{referencia}",
    # ── Senado — Entidades raiz ─────────────────────────────────────────────────
    DomainType.SENADORES: "{base}/senador/{codigo}",
    DomainType.SENADORES_DETALHE: "{base}/senador/{codigo}",
    DomainType.PROCESSOS: "{base}/materia/{id}",
    DomainType.PROCESSOS_DETALHE: "{base}/materia/{id}",
    DomainType.VOTACOES_SENADO: "{base}/votacao/{votacao_id}",
    DomainType.VOTACOES_COMISSAO: "{base}/votacao/{votacao_id}",
    DomainType.COMISSOES_SENADO: "{base}/colegiado/{codigo}",
    DomainType.COMISSOES_DETALHE: "{base}/colegiado/{codigo}",
    DomainType.BLOCOS_SENADO: "{base}/bloco/{codigo}",
    DomainType.LIDERANCAS_SENADO: "{base}/lideranca/{codigo}",
    # ── Senado — Filhos de Processos ────────────────────────────────────────────
    DomainType.PROCESSOS_EMENDAS: "{base}/materia/{id_processo}/emendas",
    DomainType.PROCESSOS_DOCUMENTOS: "{base}/materia/{id_processo}/documentos",
    # ── Senado — Filhos de Votações ─────────────────────────────────────────────
    DomainType.VOTOS_SENADO: "{base}/votacao/{votacao_id}/votos",
    DomainType.ORIENTACAO_BANCADA: "{base}/votacao/{codigo_votacao}/orientacaoBancada",
    # ── Senado — Filhos de Senadores ────────────────────────────────────────────
    DomainType.SENADORES_DISCURSOS: "{base}/senador/{codigo}/discursos",
    DomainType.SENADORES_MANDATOS: "{base}/senador/{codigo}/mandatos",
    DomainType.SENADORES_FILIACOES: "{base}/senador/{codigo}/filiacoes",
    # ── Senado — Discursos ──────────────────────────────────────────────────────
    DomainType.DISCURSOS_PLENARIO: "{base}/discursos/{codigo}",
    DomainType.DISCURSOS_TEXTO: "{base}/discursos/{codigo}",
    # ── Senado — Notas Taquigráficas ────────────────────────────────────────────
    DomainType.NOTAS_TAQUIGRAFIA_SESSAO: "{base}/sessao/{id_sessao}/notas",
    DomainType.NOTAS_TAQUIGRAFIA_REUNIAO: "{base}/reuniao/{id_reuniao}/notas",
    # ── Senado — Comissões ──────────────────────────────────────────────────────
    DomainType.COMISSOES_REUNIOES: "{base}/colegiado/{codigo_colegiado}/reunioes",
    DomainType.COMISSOES_MEMBROS: "{base}/colegiado/{codigo_comissao}/membros",
    # ── Senado — Plenário (diário — sem URL por registro) ───────────────────────
    DomainType.PLENARIO_AGENDA: "{base}/plenario/agenda/dia/{data}",
    DomainType.PLENARIO_RESULTADOS: "{base}/plenario/resultados",
    DomainType.PLENARIO_SESSOES: "{base}/plenario/sessoes",
    # ── Senado — Mesa (colegiado único — sem URL por registro) ──────────────────
    DomainType.MESA_SENADO: "{base}/mesa/senado",
    DomainType.MESA_CONGRESSO: "{base}/mesa/congresso",
    # ── Senado — Orçamento ──────────────────────────────────────────────────────
    DomainType.ORCAMENTO_EMENDAS: "{base}/orcamento/emendas",
    DomainType.ORCAMENTO_OFICIOS: "{base}/orcamento/oficios/{id}",
    # ── Senado — Vetos ──────────────────────────────────────────────────────────
    DomainType.VETOS_PRESIDENCIAIS: "{base}/veto/{codigo}",
    DomainType.VETOS_DETALHE: "{base}/veto/{codigo}",
}

# Compila padrão de extração de placeholders
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _resolve_url(template: str, base: str, row: dict[str, Any]) -> str:
    """Resolve um template de URL com os valores de uma linha.

    Args:
        template: Template com placeholders ``{campo}``.
        base: Base URL já resolvida (Câmara ou Senado).
        row: Dicionário com os valores das colunas do registro.

    Returns:
        URL resolvida, ou string vazia se faltar campo obrigatório.
    """
    merged: dict[str, Any] = {"base": base}
    for k, v in row.items():
        merged[k] = v if v is not None else ""
    try:
        return template.format(**merged)
    except (KeyError, ValueError):
        return ""


def add_source_url_column(df: pl.DataFrame, domain: DomainType) -> pl.DataFrame:
    """Adiciona a coluna ``_source_url`` a um DataFrame Silver.

    A URL é construída a partir do template do domínio e dos valores
    de cada linha. Domínios bulk-only recebem string vazia.

    Args:
        df: DataFrame já transformado (camada Silver).
        domain: Tipo do domínio para resolver o template correto.

    Returns:
        DataFrame com coluna ``_source_url`` adicionada.
    """
    if df.is_empty():
        return df.with_columns(pl.lit("").alias("_source_url"))

    if domain in _BULK_ONLY_DOMAINS:
        return df.with_columns(pl.lit("").alias("_source_url"))

    template = SOURCE_URL_TEMPLATES.get(domain)
    if not template:
        return df.with_columns(pl.lit("").alias("_source_url"))

    base = _SENADO_BASE if domain in _SENADO_DOMAINS else _CAMARA_BASE

    # Constrói a URL linha a linha via expressão Polars
    urls = [_resolve_url(template, base, row) for row in df.iter_rows(named=True)]
    return df.with_columns(pl.Series(urls).alias("_source_url"))
