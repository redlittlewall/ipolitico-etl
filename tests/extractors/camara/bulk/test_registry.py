"""
Testes estruturais do BULK_REGISTRY e seus schema_overrides.
"""

import polars as pl
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

REQUIRED_SCHEMA_OVERRIDE_DOMAINS = {"deputados", "despesas", "proposicoes", "votacoes", "votos"}


def test_all_bulk_domains_have_schema_overrides():
    """
    [BLINDAGEM ESTRUTURAL] Todo domínio no BULK_REGISTRY deve ter um campo
    ``schema_overrides`` (mesmo que vazio), garantindo que o ``BaseBulkExtractor``
    sempre encontre o campo ao chamar ``config.get("schema_overrides")``.
    """
    registered = set(BULK_REGISTRY.keys())
    assert REQUIRED_SCHEMA_OVERRIDE_DOMAINS.issubset(registered)

    for domain in REQUIRED_SCHEMA_OVERRIDE_DOMAINS:
        entry = BULK_REGISTRY[domain]
        assert "schema_overrides" in entry, f"{domain} falta schema_overrides"
        assert isinstance(
            entry["schema_overrides"], dict
        ), f"{domain}.schema_overrides deve ser um dict"


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
