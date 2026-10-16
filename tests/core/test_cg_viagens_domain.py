"""Ticket 04 — cg_viagens registrado em todas as superfícies de wiring.

Correção de fonte da validação real do ticket 04: NÃO há dumps mensais de
viagens — ``{YYYYMM}`` responde 404; a cobertura é o dump ANUAL
``/download-de-dados/viagens/{YYYY}`` (2025 ≈ 155 MB). A API v3 exige 6
parâmetros (4 datas + codigoOrgao + pagina — impossível enumerar) → bulk_only.

Contrato Silver travado no CSV REAL CAPTURADO (passo 0): o ZIP anual tem 4 CSVs
heterogêneos (Pagamento/Passagem/Trecho/Viagem) e a entidade-pai é o
``*_Viagem.csv`` — 22 colunas, latin-1, ponto-e-vírgula, ``identificador_processo
_viagem`` ÚNICO (855.805 linhas = 855.805 distintos em 2016) → chave
``("_source_url", "identificador_processo_viagem")``. O ``rename_map`` do
registry renomeia as colunas antes do transformer.

Prior art: ``tests/core/test_cg_remuneracoes_domain.py`` — mesmo padrão de
wiring de bulk anual: enum, spec (``unique_keys``), estratégia
(``PortalAnnualBulkStrategy``), pipeline canônica, schema Silver, SourceRouter
(bulk_only → sempre BULK) e YAML.
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

# Campos monetários do CSV real — string BR vírgula-decimal ("8.791,50") →
# Float64 via transformer (convert_br_currency_columns).
MONETARY_COLUMNS = {
    "valor_diarias",
    "valor_passagens",
    "valor_devolucao",
    "valor_outros_gastos",
}


class TestCgViagensWiring:
    """Cada superfície de wiring conhece o domínio cg_viagens."""

    def test_membro_do_enum(self):
        assert DomainType.CG_VIAGENS.value == "cg_viagens"

    def test_no_earliest_date_map(self):
        """Confirmado na validação real: arquivos anuais de 2013 em diante."""
        assert DomainType.CG_VIAGENS in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.CG_VIAGENS] == "2013-01-01"

    def test_sistema_de_origem_portal(self):
        assert (
            DOMAIN_SOURCE_SYSTEM[DomainType.CG_VIAGENS.value] == SourceSystem.PORTAL_TRANSPARENCIA
        )

    def test_spec_bulk_anual_nao_estavel(self):
        """Bulk anual sem watermark; chave (_source_url, identificador)."""
        spec = spec_for(DomainType.CG_VIAGENS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("_source_url", "identificador_processo_viagem")
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "2013-01-01"

    def test_estrategia_bulk_anual(self):
        """Planner gera 1 job por ano com mapper {"year"} (path {YYYY} do portal)."""
        assert STRATEGY_REGISTRY[DomainType.CG_VIAGENS] is not None
        assert isinstance(strategy_for(DomainType.CG_VIAGENS), PortalAnnualBulkStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_VIAGENS in FULL_PIPELINE

    def test_schema_silver(self):
        """Contrato do CSV real capturado; monetário → Float64, datas String."""
        contract = SILVER_SCHEMAS[DomainType.CG_VIAGENS.value]
        assert contract["_source_url"] == pl.String
        assert contract["identificador_processo_viagem"] == pl.String
        assert contract["numero_pcdp"] == pl.String
        assert contract["situacao"] == pl.String
        assert contract["cpf_viajante"] == pl.String
        assert contract["nome_viajante"] == pl.String
        assert contract["data_inicio"] == pl.String
        assert contract["destinos"] == pl.String
        assert contract["motivo"] == pl.String
        for col in MONETARY_COLUMNS:
            assert contract[col] == pl.Float64

    def test_e_bulk_only(self):
        """Sem rota API viável (6 parâmetros obrigatórios): bulk_only."""
        meta = bulk_meta_for_domain(DomainType.CG_VIAGENS)
        assert meta.get("bulk_only") is True
        assert BULK_REGISTRY["cg_viagens"]["requires_year"] is True
        assert BULK_REGISTRY["cg_viagens"]["requires_month"] is False
        assert BULK_REGISTRY["cg_viagens"]["bulk_granularity"] == "year"
        # rename_map do CSV real → contrato (aplicado no _read_single_csv).
        assert BULK_REGISTRY["cg_viagens"]["rename_map"]["Identificador do processo de viagem"] == (
            "identificador_processo_viagem"
        )
        assert BULK_REGISTRY["cg_viagens"]["rename_map"]["Valor diárias"] == "valor_diarias"

    def test_source_router_sempre_bulk(self):
        """bulk_only: FULL_LOAD E INCREMENTAL usam o dump anual {YYYY}."""
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(DomainType.CG_VIAGENS, strategy, "2024-01-01", "2026-12-31")
            assert plan.source_type == SourceType.BULK

    def test_label_registrado(self):
        assert DomainType.CG_VIAGENS in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_viagens"]
        assert "PortalViagensBulkExtractor" in config["extractor_bulk"]
        assert "PortalViagensTransformer" in config["transformer"]
        assert config["extractor_kwargs"]["module"] == "viagens"
