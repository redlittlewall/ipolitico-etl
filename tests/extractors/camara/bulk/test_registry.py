"""
Testes estruturais do BULK_REGISTRY e seus schema_overrides.
"""

import polars as pl
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

# 5 legados + 13 domínios institucionais + 3 bulk-only (Fase 3) = 21
REQUIRED_SCHEMA_OVERRIDE_DOMAINS = {
    "deputados",
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
    "orgaos",
    "deputados_orgaos",
    "deputados_frentes",
    "ocupacoes",
    "profissoes",
    "orientacoes",
    # Fase 3 — Domínios bulk-only (sem rota API)
    "funcionarios",
    "tecad_categorias",
    "tecad_termos",
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
        "orgaos",
        "deputados_orgaos",
        "deputados_frentes",
        "ocupacoes",
        "profissoes",
        # Fase 3 — bulk-only snapshot
        "funcionarios",
        "tecad_categorias",
        "tecad_termos",
    }
)

YEARLY_DOMAINS = frozenset({"eventos", "orientacoes"})


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
        assert isinstance(
            entry["schema_overrides"], dict
        ), f"{domain}.schema_overrides deve ser um dict"


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


def test_snapshot_domains_no_filter_date_column():
    """
    [FILTRO] Domínios snapshot não devem ter bulk_filter_date_column (é None)
    pois não há data para filtrar.
    """
    for domain in SNAPSHOT_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert (
            entry["bulk_filter_date_column"] is None
        ), f"{domain} não deveria ter bulk_filter_date_column"


def test_yearly_domains_have_filter_date_column():
    """
    [FILTRO] Domínios anuais com bulk_granularity='year' devem ter
    bulk_filter_date_column definida.
    """
    for domain in YEARLY_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert (
            entry["bulk_filter_date_column"] is not None
        ), f"{domain} deveria ter bulk_filter_date_column"


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


def test_deputados_schema_overrides_types():
    """deputados: colunas numéricas conhecidas têm override Int64."""
    overrides = BULK_REGISTRY["deputados"]["schema_overrides"]
    assert overrides.get("Id") == pl.Int64
    assert overrides.get("idLegislatura") == pl.Int64


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
