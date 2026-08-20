"""Ticket 04 — cg_imoveis_funcionais registrado em todas as superfícies de wiring.

Correção de fonte da validação real do ticket 04: o dump bulk
``/download-de-dados/imoveis-funcionais`` está INDISPONÍVEL (403 AccessDenied
do S3) → fonte única é a API v3 ``/api-de-dados/imoveis`` (walk livre com
``pagina`` — contrato confirmado, sem exigência de filtro). Snapshot: 1 job sem
parâmetros. Mesmo padrão de cg_orgaos (ticket 02): API-first, sem
``extractor_bulk``.

Prior art: ``tests/core/test_cg_orgaos_domain.py``.
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
    SnapshotWindowStrategy,
    strategy_for,
)
from ipolitico.pipeline.source_router import SourceRouter

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestCgImoveisFuncionaisWiring:
    """Cada superfície de wiring conhece o domínio cg_imoveis_funcionais."""

    def test_membro_do_enum(self):
        assert DomainType.CG_IMOVEIS_FUNCIONAIS.value == "cg_imoveis_funcionais"

    def test_no_earliest_date_map(self):
        """Snapshot — convenção de disponibilidade (cg_orgaos, 1826-04-29)."""
        assert DomainType.CG_IMOVEIS_FUNCIONAIS in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.CG_IMOVEIS_FUNCIONAIS] == "1826-04-29"

    def test_sistema_de_origem_portal(self):
        assert (
            DOMAIN_SOURCE_SYSTEM[DomainType.CG_IMOVEIS_FUNCIONAIS.value]
            == SourceSystem.PORTAL_TRANSPARENCIA
        )

    def test_spec_snapshot_nao_estavel(self):
        """Snapshot sem watermark; chave (id)."""
        spec = spec_for(DomainType.CG_IMOVEIS_FUNCIONAIS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("id",)
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "1826-04-29"

    def test_estrategia_snapshot_1_job_sem_parametros(self):
        """Planner produz 1 job vazio (walk livre do endpoint /imoveis)."""
        assert STRATEGY_REGISTRY[DomainType.CG_IMOVEIS_FUNCIONAIS] is not None
        assert isinstance(strategy_for(DomainType.CG_IMOVEIS_FUNCIONAIS), SnapshotWindowStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_IMOVEIS_FUNCIONAIS in FULL_PIPELINE

    def test_schema_silver(self):
        """Contrato da API: structs achataas; ids de situação/região Int64."""
        contract = SILVER_SCHEMAS[DomainType.CG_IMOVEIS_FUNCIONAIS.value]
        assert contract["_source_url"] == pl.String
        assert contract["id"] == pl.Int64
        assert contract["dataReferencia"] == pl.String
        assert contract["orgaoResponsavel_nome"] == pl.String
        assert contract["orgaoResponsavel_codigoSIAFI"] == pl.String
        assert contract["situacao_id"] == pl.Int64
        assert contract["situacao_descricao"] == pl.String
        assert contract["regiao_id"] == pl.Int64
        assert contract["regiao_descricao"] == pl.String
        assert contract["endereco"] == pl.String
        assert contract["cep"] == pl.String

    def test_nao_e_bulk(self):
        """Sem rota bulk (dump 403): domínio é API-first, não bulk_only."""
        assert bulk_meta_for_domain(DomainType.CG_IMOVEIS_FUNCIONAIS).get("bulk_only") is not True
        assert BULK_REGISTRY.get("cg_imoveis_funcionais", {}).get("bulk_only") is not True

    def test_source_router_sempre_api(self):
        """Sem rota bulk: FULL_LOAD E INCREMENTAL usam a API v3 (imoveis)."""
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(
                DomainType.CG_IMOVEIS_FUNCIONAIS, strategy, "2026-01-01", "2026-12-31"
            )
            assert plan.source_type == SourceType.API

    def test_label_registrado(self):
        assert DomainType.CG_IMOVEIS_FUNCIONAIS in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_imoveis_funcionais"]
        assert "PortalImoveisFuncionaisApiExtractor" in config["extractor"]
        assert "PortalImoveisFuncionaisTransformer" in config["transformer"]
        assert "extractor_bulk" not in config
