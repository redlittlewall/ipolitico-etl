"""Ticket 04 — cg_emendas registrado em todas as superfícies de wiring.

Fonte: API v3 ``/api-de-dados/emendas`` POR ANO (param ``ano`` — "respeita a
janela da API por ano" do ticket; contrato confirmado na validação real).
Sem rota bulk: o dump ``/download-de-dados/emendas-parlamentares`` é um único
ZIP que re-publica o HISTÓRICO inteiro a cada geração (32 MB) — conflita com
append-only (mesmo padrão de cg_servidores no ticket 03). Estratégia anual
(``AnnualWindowStrategy`` — 1 job por ano com mapper ``{"ano"}``).

Prior art: ``tests/core/test_cg_orgaos_domain.py`` (API-first sem
``extractor_bulk``) + ``tests/core/test_senado_emendas_domain.py`` (se existir;
senão o padrão anual de ORCAMENTO_EMENDAS).
"""

from pathlib import Path

import polars as pl
import yaml

from ipolitico.core.constants import (
    DOMAIN_LABELS,
    DOMAIN_SOURCE_SYSTEM,
    EARLIEST_DATE_MAP,
    DomainType,
    LoadStrategy,
    SourceSystem,
    SourceType,
)
from ipolitico.core.domain_spec import bulk_meta_for_domain, spec_for
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY
from ipolitico.pipeline.domain_order import FULL_PIPELINE
from ipolitico.pipeline.planners.strategies import (
    STRATEGY_REGISTRY,
    AnnualWindowStrategy,
    strategy_for,
)
from ipolitico.pipeline.source_router import SourceRouter

REPO_ROOT = Path(__file__).resolve().parents[2]

# Valores monetários da emenda — strings vírgula-decimal com separador de
# milhar na API → Float64 via br_locale (convert_br_currency_columns).
MONETARY_COLUMNS = {
    "valorEmpenhado",
    "valorLiquidado",
    "valorPago",
    "valorRestoInscrito",
    "valorRestoCancelado",
    "valorRestoPago",
}


class TestCgEmendasWiring:
    """Cada superfície de wiring conhece o domínio cg_emendas."""

    def test_membro_do_enum(self):
        assert DomainType.CG_EMENDAS.value == "cg_emendas"

    def test_no_earliest_date_map(self):
        """Placeholder (2012-01-01) a validar pelo ano mais antigo."""
        assert DomainType.CG_EMENDAS in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.CG_EMENDAS] == "2012-01-01"

    def test_sistema_de_origem_portal(self):
        assert (
            DOMAIN_SOURCE_SYSTEM[DomainType.CG_EMENDAS.value] == SourceSystem.PORTAL_TRANSPARENCIA
        )

    def test_spec_anual_nao_estavel(self):
        """Anual sem watermark; chave (codigoEmenda — embute o ano)."""
        spec = spec_for(DomainType.CG_EMENDAS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("codigoEmenda",)
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "2012-01-01"

    def test_estrategia_anual_api(self):
        """Planner gera 1 job por ano com mapper {"ano"} (param `ano` da API)."""
        assert STRATEGY_REGISTRY[DomainType.CG_EMENDAS] is not None
        assert isinstance(strategy_for(DomainType.CG_EMENDAS), AnnualWindowStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_EMENDAS in FULL_PIPELINE

    def test_schema_silver(self):
        """Contrato da API: codigoEmenda String, ano Int64, valor* Float64."""
        contract = SILVER_SCHEMAS[DomainType.CG_EMENDAS.value]
        assert contract["_source_url"] == pl.String
        assert contract["codigoEmenda"] == pl.String
        assert contract["ano"] == pl.Int64
        assert contract["tipoEmenda"] == pl.String
        assert contract["autor"] == pl.String
        assert contract["nomeAutor"] == pl.String
        assert contract["numeroEmenda"] == pl.String
        assert contract["localidadeDoGasto"] == pl.String
        assert contract["funcao"] == pl.String
        assert contract["subfuncao"] == pl.String
        for col in MONETARY_COLUMNS:
            assert contract[col] == pl.Float64

    def test_nao_e_bulk(self):
        """Sem rota bulk (dump único re-publica o histórico): API-first."""
        assert bulk_meta_for_domain(DomainType.CG_EMENDAS).get("bulk_only") is not True
        assert BULK_REGISTRY.get("cg_emendas", {}).get("bulk_only") is not True

    def test_source_router_sempre_api(self):
        """Sem rota bulk: FULL_LOAD E INCREMENTAL usam a API v3 (emendas)."""
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(DomainType.CG_EMENDAS, strategy, "2024-01-01", "2026-12-31")
            assert plan.source_type == SourceType.API

    def test_label_registrado(self):
        assert DomainType.CG_EMENDAS in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_emendas"]
        assert "PortalEmendasApiExtractor" in config["extractor"]
        assert "PortalEmendasTransformer" in config["transformer"]
        assert "extractor_bulk" not in config
