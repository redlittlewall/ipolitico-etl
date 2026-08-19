"""Ticket 02 — cg_orgaos registrado em todas as superfícies de wiring.

Prior art: ``tests/core/test_senado_servidores_domain.py`` — o tracer bullet do
Portal da Transparência segue o mesmo padrão: enum, spec (snapshot,
``unique_keys=("codigo",)``), estratégia (``SnapshotWindowStrategy`` — 1 job sem
parâmetros), pipeline canônica, schema Silver, SourceRouter (sempre API) e YAML
da fonte ``portaldatransparencia``.

Correção de fonte (validação real do ticket 02): o portal NÃO tem módulo bulk
``/download-de-dados/orgaos`` (HTTP 500); a fonte real de órgãos SIAPE é a API
v3 ``/api-de-dados/orgaos-siape`` (640 registros, contrato ``codigo``/``descricao``).
O domínio é API-first, não bulk-only — a rota bulk ficaria em ``ceis``/``viagens``
num ticket futuro.
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


class TestCgOrgaosWiring:
    """Cada superfície de wiring conhece o domínio cg_orgaos."""

    def test_membro_do_enum(self):
        assert DomainType.CG_ORGAOS.value == "cg_orgaos"

    def test_no_earliest_date_map(self):
        assert DomainType.CG_ORGAOS in EARLIEST_DATE_MAP

    def test_sistema_de_origem_portal(self):
        assert DOMAIN_SOURCE_SYSTEM[DomainType.CG_ORGAOS.value] == SourceSystem.PORTAL_TRANSPARENCIA

    def test_spec_snapshot_nao_estavel(self):
        """Snapshot sem watermark; órgãos mudam → stable=False (incremental re-fetch)."""
        spec = spec_for(DomainType.CG_ORGAOS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("codigo",)
        assert spec.depends_on == frozenset()

    def test_estrategia_snapshot_1_job_sem_parametros(self):
        """Planner produz 1 job vazio (dump único de órgãos, sem janela)."""
        assert STRATEGY_REGISTRY[DomainType.CG_ORGAOS] is not None
        assert isinstance(strategy_for(DomainType.CG_ORGAOS), SnapshotWindowStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_ORGAOS in FULL_PIPELINE

    def test_schema_silver(self):
        """Contrato da API v3 orgaos-siape: codigo/descricao como String."""
        contract = SILVER_SCHEMAS[DomainType.CG_ORGAOS.value]
        assert contract["_source_url"] == pl.String
        assert contract["codigo"] == pl.String
        assert contract["descricao"] == pl.String

    def test_nao_e_bulk(self):
        """Sem módulo bulk de órgãos: domínio é API-first, não bulk_only."""
        assert bulk_meta_for_domain(DomainType.CG_ORGAOS).get("bulk_only") is not True
        assert BULK_REGISTRY.get("cg_orgaos", {}).get("bulk_only") is not True

    def test_source_router_sempre_api(self):
        """Sem rota bulk: FULL_LOAD E INCREMENTAL usam a API v3 (orgaos-siape)."""
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(DomainType.CG_ORGAOS, strategy, "2026-01-01", "2026-12-31")
            assert plan.source_type == SourceType.API

    def test_label_registrado(self):
        assert DomainType.CG_ORGAOS in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_orgaos"]
        assert "PortalOrgaosApiExtractor" in config["extractor"]
        assert "PortalOrgaosTransformer" in config["transformer"]
        assert "extractor_bulk" not in config
