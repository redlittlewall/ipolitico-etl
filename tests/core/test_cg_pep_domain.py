"""Ticket 04 — cg_pep registrado em todas as superfícies de wiring.

PEPs = Pessoas Expostas Politicamente (ocupantes de cargo público — MINISTRO,
SECRETARIO, VEREADOR), NÃO patrimônio. Correções de fonte da validação real do
ticket 04: a API v3 ``/peps`` exige ≥1 filtro (pagina sozinho → 400 — impossível
enumerar) e o dump bulk ``/download-de-dados/pep/{YYYY}`` está INDISPONÍVEL
(403 AccessDenied do S3) → o cliente trata 403-AccessDenied como ausência (job
vazio gracioso, não cai). Contrato Silver PROVISIONAL derivado do JSON da API
(mesmo status documentado de cg_remuneracoes no ticket 03); a validação real
reabre quando o dump publicar.

Prior art: ``tests/core/test_cg_remuneracoes_domain.py`` — bulk anual com o
mesmo padrão de wiring: enum, spec (``unique_keys``), estratégia
(``PortalAnnualBulkStrategy`` — 1 job por ano com mapper ``{"year"}``),
pipeline canônica, schema Silver, SourceRouter (bulk_only → sempre BULK) e YAML.
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
    PortalAnnualBulkStrategy,
    strategy_for,
)
from ipolitico.pipeline.source_router import SourceRouter

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestCgPepWiring:
    """Cada superfície de wiring conhece o domínio cg_pep."""

    def test_membro_do_enum(self):
        assert DomainType.CG_PEP.value == "cg_pep"

    def test_no_earliest_date_map(self):
        """Placeholder (2013-01-01) a validar quando o dump publicar."""
        assert DomainType.CG_PEP in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.CG_PEP] == "2013-01-01"

    def test_sistema_de_origem_portal(self):
        assert DOMAIN_SOURCE_SYSTEM[DomainType.CG_PEP.value] == SourceSystem.PORTAL_TRANSPARENCIA

    def test_spec_bulk_anual_nao_estavel(self):
        """Bulk anual sem watermark; chave (cpf, órgão, função, início)."""
        spec = spec_for(DomainType.CG_PEP)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == (
            "_source_url",
            "cpf",
            "cod_orgao",
            "sigla_funcao",
            "dt_inicio_exercicio",
        )
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "2013-01-01"

    def test_estrategia_bulk_anual(self):
        """Planner gera 1 job por ano com mapper {"year"} (path {YYYY} do portal)."""
        assert STRATEGY_REGISTRY[DomainType.CG_PEP] is not None
        assert isinstance(strategy_for(DomainType.CG_PEP), PortalAnnualBulkStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_PEP in FULL_PIPELINE

    def test_schema_silver_provisional(self):
        """Contrato PROVISIONAL (dump indisponível): todos String (API shape)."""
        contract = SILVER_SCHEMAS[DomainType.CG_PEP.value]
        assert contract["_source_url"] == pl.String
        assert contract["cpf"] == pl.String
        assert contract["nome"] == pl.String
        assert contract["sigla_funcao"] == pl.String
        assert contract["nivel_funcao"] == pl.String
        assert contract["cod_orgao"] == pl.String
        assert contract["nome_orgao"] == pl.String
        assert contract["dt_inicio_exercicio"] == pl.String
        assert contract["dt_fim_exercicio"] == pl.String
        assert contract["dt_fim_carencia"] == pl.String
        # Contrato inteiro é String (datas ISO, CPF mascarado, códigos com zeros)
        assert all(dtype == pl.String for dtype in contract.values())

    def test_e_bulk_only(self):
        """Sem rota API (exige filtro, impossível enumerar): bulk_only."""
        meta = bulk_meta_for_domain(DomainType.CG_PEP)
        assert meta.get("bulk_only") is True
        assert BULK_REGISTRY["cg_pep"]["requires_year"] is True
        assert BULK_REGISTRY["cg_pep"]["requires_month"] is False
        assert BULK_REGISTRY["cg_pep"]["bulk_granularity"] == "year"

    def test_source_router_sempre_bulk(self):
        """bulk_only: FULL_LOAD E INCREMENTAL usam o dump anual {YYYY}."""
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(DomainType.CG_PEP, strategy, "2024-01-01", "2026-12-31")
            assert plan.source_type == SourceType.BULK

    def test_label_registrado(self):
        assert DomainType.CG_PEP in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_pep"]
        assert "PortalTransparenciaBulkExtractor" in config["extractor_bulk"]
        assert "PortalPepTransformer" in config["transformer"]
        assert config["extractor_kwargs"]["module"] == "pep"
