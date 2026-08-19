"""Ticket 03 — cg_servidores registrado em todas as superfícies de wiring.

Prior art: ``tests/core/test_cg_orgaos_domain.py`` — o domínio de servidores do
Poder Executivo segue o mesmo padrão de snapshot da API v3: enum, spec
(``unique_keys=("codOrgaoExercicioSiape", "skSituacao", "skTipoServidor",
"skTipoVinculo", "licenca")``), estratégia (``SnapshotWindowStrategy`` — 1 job
sem parâmetros), pipeline canônica, schema Silver (13 campos do agregado
``/servidores/por-orgao``) e YAML da fonte ``portaldatransparencia``.

Correção de fonte (validação real do ticket 03): o roster completo
``/servidores`` exige filtro de órgão (HTTP 400 sem ele) e a remuneração
individual exige CPF por servidor — inviável enumerar. A fonte real do snapshot
é o agregado ``/api-de-dados/servidores/por-orgao`` (validado hoje com a chave
do usuário): contagens por (órgão, situação, tipo de vínculo, tipo de servidor,
licença). O domínio é API-first, não bulk-only — a rota bulk fica em
``cg_remuneracoes`` (WAF bloqueado no ticket 03).
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


class TestCgServidoresWiring:
    """Cada superfície de wiring conhece o domínio cg_servidores."""

    def test_membro_do_enum(self):
        assert DomainType.CG_SERVIDORES.value == "cg_servidores"

    def test_no_earliest_date_map(self):
        """Snapshot de existência do órgão — mesma convenção de CG_ORGAOS."""
        assert DomainType.CG_SERVIDORES in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.CG_SERVIDORES] == "1826-04-29"

    def test_sistema_de_origem_portal(self):
        assert (
            DOMAIN_SOURCE_SYSTEM[DomainType.CG_SERVIDORES.value]
            == SourceSystem.PORTAL_TRANSPARENCIA
        )

    def test_spec_snapshot_nao_estavel(self):
        """Agregado sem watermark; contagens mudam → stable=False (incremental re-fetch)."""
        spec = spec_for(DomainType.CG_SERVIDORES)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == (
            "codOrgaoExercicioSiape",
            "skSituacao",
            "skTipoServidor",
            "skTipoVinculo",
            "licenca",
        )
        assert spec.depends_on == frozenset()

    def test_estrategia_snapshot_1_job_sem_parametros(self):
        """Planner produz 1 job vazio (agregado por-orgao completo, sem janela)."""
        assert STRATEGY_REGISTRY[DomainType.CG_SERVIDORES] is not None
        assert isinstance(strategy_for(DomainType.CG_SERVIDORES), SnapshotWindowStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_SERVIDORES in FULL_PIPELINE

    def test_schema_silver_13_campos(self):
        """Contrato real do agregado por-orgao: contagens Int, dimensões String."""
        contract = SILVER_SCHEMAS[DomainType.CG_SERVIDORES.value]
        assert contract["_source_url"] == pl.String
        assert len(contract) == 14  # _source_url + 13 campos do DTO
        for col in ("qntPessoas", "qntVinculos", "skSituacao", "skTipoVinculo",
                    "skTipoServidor", "licenca"):
            assert contract[col] == pl.Int64
        for col in ("descSituacao", "descTipoVinculo", "descTipoServidor",
                    "codOrgaoExercicioSiape", "nomOrgaoExercicioSiape",
                    "codOrgaoSuperiorExercicioSiape", "nomOrgaoSuperiorExercicioSiape"):
            assert contract[col] == pl.String

    def test_nao_e_bulk(self):
        """Sem módulo bulk de servidores por-orgao: domínio é API-first, não bulk_only."""
        assert bulk_meta_for_domain(DomainType.CG_SERVIDORES).get("bulk_only") is not True
        assert BULK_REGISTRY.get("cg_servidores", {}).get("bulk_only") is not True

    def test_source_router_sempre_api(self):
        """Sem rota bulk: FULL_LOAD E INCREMENTAL usam a API v3 (por-orgao)."""
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(
                DomainType.CG_SERVIDORES, strategy, "2026-01-01", "2026-12-31"
            )
            assert plan.source_type == SourceType.API

    def test_label_registrado(self):
        assert DomainType.CG_SERVIDORES in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_servidores"]
        assert "PortalServidoresPorOrgaoApiExtractor" in config["extractor"]
        assert "PortalServidoresPorOrgaoTransformer" in config["transformer"]
        assert "extractor_bulk" not in config
