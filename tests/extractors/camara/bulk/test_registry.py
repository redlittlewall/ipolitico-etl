"""
Testes estruturais do BULK_REGISTRY e seus schema_overrides.
"""

import polars as pl

from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

# 4 legados + 13 institucionais + 3 funcionarios/tecad + 5 licitacoes + 4 eventos = 29
# NOTA: deputados removido — não há Bulk CSV compatível (dados cadastrais, não políticos)
REQUIRED_SCHEMA_OVERRIDE_DOMAINS = {
    "despesas",
    "proposicoes",
    "votacoes",
    "votos",
    # Expansão — domínios institucionais com dump Bulk
    "eventos",
    "frentes",
    "grupos",
    "grupos_membros",
    "grupos_historico",
    "legislaturas",
    "legislaturas_mesa",
    # NOTA: orgaos removido intencionalmente — CSV bulk não tem id numérica
    "deputados_orgaos",
    "deputados_frentes",
    # NOTA: profissoes e ocupacoes removidos — CSVs são catálogos de tipos,
    # sem id_deputado. Não servem como fonte para dados por-deputado.
    "orientacoes",
    # Fase 3 — Domínios bulk-only (sem rota API)
    "funcionarios",
    "tecad_categorias",
    "tecad_termos",
    # Fase 3 — bulk-only licitações (anuais)
    "licitacoes",
    "licitacoes_contratos",
    "licitacoes_itens",
    "licitacoes_pedidos",
    "licitacoes_propostas",
    # Fase 3 — bulk-only eventos/votações (anuais)
    "eventos_presenca_deputados",
    "eventos_requerimentos",
    "votacoes_objetos",
    "votacoes_proposicoes",
    # Issue 04 — folha de pagamento (consolidado mensal)
    "folha_pagamento",
}

REQUIRED_KEYS = frozenset(
    {
        "requires_year",
        "url_template",
        "bulk_granularity",
        "bulk_filter_date_column",
        "schema_overrides",
    }
)

SNAPSHOT_DOMAINS = frozenset(
    {
        "frentes",
        "grupos",
        "grupos_membros",
        "grupos_historico",
        "legislaturas",
        "legislaturas_mesa",
        # NOTA: orgaos removido — Bulk CSV inviável
        "deputados_orgaos",
        "deputados_frentes",
        # NOTA: profissoes e ocupacoes removidos — CSVs sem id_deputado.
        "funcionarios",
        "tecad_categorias",
        "tecad_termos",
    }
)

YEARLY_DOMAINS = frozenset(
    {
        "eventos",
        "orientacoes",
        # Fase 3 — bulk-only licitações (anuais)
        "licitacoes",
        "licitacoes_contratos",
        "licitacoes_itens",
        "licitacoes_pedidos",
        "licitacoes_propostas",
        # Fase 3 — bulk-only eventos/votações (anuais)
        "eventos_presenca_deputados",
        "eventos_requerimentos",
        "votacoes_objetos",
        "votacoes_proposicoes",
    }
)

# Domínios anuais que NÃO possuem coluna de data para filtro temporal
YEARLY_DOMAINS_NO_FILTER = frozenset(
    {
        "licitacoes_itens",
        "eventos_requerimentos",
    }
)

# Issue 04 — domínios bulk-only mensais (1 arquivo por ano/mês)
MONTHLY_DOMAINS = frozenset({"folha_pagamento"})


def test_all_bulk_domains_have_schema_overrides():
    """
    [BLINDAGEM ESTRUTURAL] Todo domínio no BULK_REGISTRY deve ter um campo
    ``schema_overrides`` (mesmo que vazio), garantindo que o ``BaseBulkExtractor``
    sempre encontre o campo ao chamar ``config.get("schema_overrides")``.
    """
    registered = set(BULK_REGISTRY.keys())
    missing = REQUIRED_SCHEMA_OVERRIDE_DOMAINS - registered
    assert not missing, f"Domínios faltando no BULK_REGISTRY: {missing}"

    for domain in REQUIRED_SCHEMA_OVERRIDE_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert "schema_overrides" in entry, f"{domain} falta schema_overrides"
        assert isinstance(entry["schema_overrides"], dict), (
            f"{domain}.schema_overrides deve ser um dict"
        )


def test_all_bulk_domains_have_required_keys():
    """
    [COMPLETUDE] Todo domínio no BULK_REGISTRY deve ter todas as chaves
    obrigatórias: requires_year, url_template, bulk_granularity,
    bulk_filter_date_column e schema_overrides.
    """
    for domain in REQUIRED_SCHEMA_OVERRIDE_DOMAINS:
        entry = BULK_REGISTRY[domain]
        missing_keys = REQUIRED_KEYS - entry.keys()
        assert not missing_keys, f"{domain} faltando chaves: {missing_keys}"


def test_new_snapshot_domains_granularity():
    """
    [GRANULARIDADE] Domínios snapshot devem ter bulk_granularity='snapshot'
    e requires_year=False.
    """
    for domain in SNAPSHOT_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert entry["bulk_granularity"] == "snapshot", f"{domain} deveria ser snapshot"
        assert entry["requires_year"] is False, f"{domain} deveria ter requires_year=False"


def test_new_yearly_domains_granularity():
    """
    [GRANULARIDADE] Domínios anuais devem ter bulk_granularity='year'
    e requires_year=True.
    """
    for domain in YEARLY_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert entry["bulk_granularity"] == "year", f"{domain} deveria ser year"
        assert entry["requires_year"] is True, f"{domain} deveria ter requires_year=True"


def test_new_monthly_domains_granularity():
    """
    [GRANULARIDADE] Domínios mensais (folha_pagamento) devem ter
    bulk_granularity='month', requires_year e requires_month True, encoding
    ISO-8859-1 (latin1) e bulk_only.
    """
    for domain in MONTHLY_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert entry["bulk_granularity"] == "month", f"{domain} deveria ser month"
        assert entry["requires_year"] is True, f"{domain} deveria ter requires_year=True"
        assert entry["requires_month"] is True, f"{domain} deveria ter requires_month=True"
        assert entry["encoding"] == "latin1", f"{domain} deveria ser latin1 (ISO-8859-1)"
        assert entry["bulk_only"] is True, f"{domain} deveria ser bulk_only"


def test_snapshot_domains_no_filter_date_column():
    """
    [FILTRO] Domínios snapshot não devem ter bulk_filter_date_column (é None)
    pois não há data para filtrar.
    """
    for domain in SNAPSHOT_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert entry["bulk_filter_date_column"] is None, (
            f"{domain} não deveria ter bulk_filter_date_column"
        )


def test_yearly_domains_have_filter_date_column():
    """
    [FILTRO] Domínios anuais com bulk_granularity='year' devem ter
    bulk_filter_date_column definida (exceto aqueles sem coluna de data).
    """
    for domain in YEARLY_DOMAINS:
        if domain in YEARLY_DOMAINS_NO_FILTER:
            continue
        entry = BULK_REGISTRY[domain]
        assert entry["bulk_filter_date_column"] is not None, (
            f"{domain} deveria ter bulk_filter_date_column"
        )


def test_eventos_filter_date_column():
    """
    [FILTRO EVENTOS] eventos usa dataHoraInicio como coluna de filtro temporal.
    """
    entry = BULK_REGISTRY["eventos"]
    assert entry["bulk_filter_date_column"] == "dataHoraInicio"


def test_orientacoes_filter_date_column():
    """
    [FILTRO ORIENTACOES] orientacoes não possui coluna de data no CSV.
    """
    entry = BULK_REGISTRY["orientacoes"]
    assert entry["bulk_filter_date_column"] is not None


def test_despesas_currency_columns_stay_utf8():
    """
    despesas: colunas de moeda BR (vlrLiquido, vlrDocumento, vlrGlosa)
    permanecem como pl.Utf8 para processamento pelo helper de locale BR.
    """
    overrides = BULK_REGISTRY["despesas"]["schema_overrides"]
    assert overrides.get("vlrLiquido") == pl.Utf8
    assert overrides.get("vlrDocumento") == pl.Utf8
    assert overrides.get("vlrGlosa") == pl.Utf8


def test_despesas_numeric_overrides():
    """despesas: colunas CEAP inteiras têm override Int64."""
    overrides = BULK_REGISTRY["despesas"]["schema_overrides"]
    for col in ("nuDeputadoId", "ideCadastro", "numParcela", "numAno", "numMes", "ideDocumento"):
        assert overrides.get(col) == pl.Int64, f"{col} deveria ser Int64"


def test_proposicoes_schema_overrides_types():
    """proposicoes: colunas numéricas conhecidas têm override Int64."""
    overrides = BULK_REGISTRY["proposicoes"]["schema_overrides"]
    assert overrides.get("id") == pl.Int64
    assert overrides.get("numero") == pl.Int64
    assert overrides.get("ano") == pl.Int64


def test_votacoes_schema_overrides_types():
    """votacoes: colunas com tipos conhecidos têm override."""
    overrides = BULK_REGISTRY["votacoes"]["schema_overrides"]
    assert overrides.get("aprovacao") == pl.Int64


def test_votos_schema_overrides_types():
    """votos: colunas numéricas conhecidas têm override Int64."""
    overrides = BULK_REGISTRY["votos"]["schema_overrides"]
    assert overrides.get("idDeputado") == pl.Int64


def test_orgaos_not_in_bulk_registry():
    """
    [RENAME MAP] orgaos não está no BULK_REGISTRY — o CSV bulk não tem
    coluna id numérica e o campo uri contém dados corrompidos. Usar sempre API.
    """
    assert "orgaos" not in BULK_REGISTRY


def test_grupos_rename_map():
    """
    [RENAME MAP] grupos deve ter rename_map de idGrupo → id
    para compatibilidade com SILVER_SCHEMAS e domínios filhos.
    """
    entry = BULK_REGISTRY["grupos"]
    assert "rename_map" in entry
    assert entry["rename_map"] == {"idGrupo": "id"}
