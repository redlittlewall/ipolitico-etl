"""Ticket 04 — cg_cartoes registrado em todas as superfícies de wiring.

ROTA DUPLA (exigência explícita do ticket): FULL_LOAD → bulk mensal (dumps
``/download-de-dados/{cpgf|cpcc|cpdc}/{YYYYMM}``, CSVs latin-1 flat) e
INCREMENTAL → consulta pontual da API v3 ``/api-de-dados/cartoes`` em blocos
mensais (``mesExtratoInicio/Fim`` de 1 mês ≤ 12 — o filtro de período é
obrigatório, exige ≥1 filtro). O dump bulk NÃO tem ``id``: a chave é a
identidade da transação (7 campos), determinística nas duas rotas — o Gold
deduplica o overlap bulk×API.

Prior art: ``tests/core/test_cg_remuneracoes_domain.py`` (wiring de bulk mensal)
com a diferença crítica no SourceRouter: NÃO é bulk_only — a fonte depende da
estratégia (FULL_LOAD→BULK, INCREMENTAL→API), via o branch
``_PORTAL_MONTHLY_BULK_DOMAINS``.
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
    MonthlyBulkStrategy,
    strategy_for,
)
from ipolitico.pipeline.source_router import SourceRouter

REPO_ROOT = Path(__file__).resolve().parents[2]

# Chave da transação = identidade composta + `id` da API (correção da validação
# real, ticket 04): a composta colide em transações DISTINTAS da API com
# documentos mascarados ("SEM INFORMACAO", CPDC) → `id` é o discriminador. No
# bulk (id nulo) a composta deduplica os duplicados exatos de fonte. Documentada
# no spec (domain_spec.py).
TRANSACTION_UK = (
    "tipoCartao_codigo",
    "mesExtrato",
    "dataTransacao",
    "valorTransacao",
    "portador_cpfFormatado",
    "favorecido_cpfCnpj",
    "unidadeGestora_codigo",
    "id",
)


class TestCgCartoesWiring:
    """Cada superfície de wiring conhece o domínio cg_cartoes."""

    def test_membro_do_enum(self):
        assert DomainType.CG_CARTOES.value == "cg_cartoes"

    def test_no_earliest_date_map(self):
        """Placeholder (2014-01-01) a validar pelo mesExtrato mais antigo."""
        assert DomainType.CG_CARTOES in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.CG_CARTOES] == "2014-01-01"

    def test_sistema_de_origem_portal(self):
        assert (
            DOMAIN_SOURCE_SYSTEM[DomainType.CG_CARTOES.value] == SourceSystem.PORTAL_TRANSPARENCIA
        )

    def test_spec_rota_dupla_nao_estavel(self):
        """Sem watermark; chave = identidade da transação (7 campos)."""
        spec = spec_for(DomainType.CG_CARTOES)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == TRANSACTION_UK
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "2014-01-01"

    def test_estrategia_monthly_bulk(self):
        """Planner gera 1 job por (ano, mês) — servem as duas rotas."""
        assert STRATEGY_REGISTRY[DomainType.CG_CARTOES] is not None
        assert isinstance(strategy_for(DomainType.CG_CARTOES), MonthlyBulkStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_CARTOES in FULL_PIPELINE

    def test_schema_silver_uniao(self):
        """Contrato UNIÃO das duas rotas: campos exclusivos viram nulo na outra."""
        contract = SILVER_SCHEMAS[DomainType.CG_CARTOES.value]
        assert contract["_source_url"] == pl.String
        # Só API (bulk não tem id)
        assert contract["id"] == pl.Int64
        # Comum às duas rotas (normalizado)
        assert contract["mesExtrato"] == pl.String
        assert contract["dataTransacao"] == pl.String
        assert contract["valorTransacao"] == pl.Float64
        assert contract["tipoCartao_id"] == pl.Int64
        assert contract["tipoCartao_codigo"] == pl.String
        assert contract["tipoCartao_descricao"] == pl.String
        # Só API (estabelecimento)
        assert contract["estabelecimento_id"] == pl.Int64
        assert contract["estabelecimento_nome"] == pl.String
        # Unidade gestora (API aninhada; bulk: CÓDIGO UNIDADE GESTORA)
        assert contract["unidadeGestora_codigo"] == pl.String
        assert contract["unidadeGestora_nome"] == pl.String
        assert contract["unidadeGestora_orgaoVinculado_codigoSIAFI"] == pl.String
        assert contract["unidadeGestora_orgaoMaximo_codigo"] == pl.String
        # Portador (ambas)
        assert contract["portador_cpfFormatado"] == pl.String
        assert contract["portador_nome"] == pl.String
        # Só bulk (favorecido/transação)
        assert contract["favorecido_cpfCnpj"] == pl.String
        assert contract["favorecido_nome"] == pl.String
        assert contract["transacao_descricao"] == pl.String

    def test_nao_e_bulk_only(self):
        """ROTA DUPLA: bulk mensal (FULL_LOAD) + API v3 (INCREMENTAL, ≤12 meses)."""
        meta = bulk_meta_for_domain(DomainType.CG_CARTOES)
        assert meta.get("bulk_only") is False
        assert BULK_REGISTRY["cg_cartoes"]["requires_year"] is True
        assert BULK_REGISTRY["cg_cartoes"]["requires_month"] is True
        assert BULK_REGISTRY["cg_cartoes"]["bulk_granularity"] == "month"

    def test_source_router_rota_dupla(self):
        """FULL_LOAD → bulk mensal {YYYYMM}; INCREMENTAL → API (bloco mensal)."""
        full = SourceRouter.plan(
            DomainType.CG_CARTOES, LoadStrategy.FULL_LOAD, "2025-01-01", "2026-12-31"
        )
        assert full.source_type == SourceType.BULK
        assert full.bulk_temporal_column is None

        incr = SourceRouter.plan(
            DomainType.CG_CARTOES, LoadStrategy.INCREMENTAL, "2026-06-01", "2026-07-31"
        )
        assert incr.source_type == SourceType.API

    def test_label_registrado(self):
        assert DomainType.CG_CARTOES in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_cartoes"]
        assert "PortalCartoesBulkExtractor" in config["extractor_bulk"]
        assert "PortalCartoesApiExtractor" in config["extractor"]
        assert "PortalCartoesTransformer" in config["transformer"]
        assert config["extractor_kwargs"]["modules"] == ["cpgf", "cpcc", "cpdc"]
