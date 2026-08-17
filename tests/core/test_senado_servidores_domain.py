"""Issue 07 — SERVIDORES registrado em todas as superfícies de wiring.

Garante que o domínio participa de full_load / incremental / resume: enum,
registry de cobertura, spec (snapshot, ``unique_keys=("sequencial",)``), estratégia
(``SnapshotWindowStrategy`` — 1 job sem parâmetros), pipeline canônica e YAML da
fonte adm-dadosabertos.
"""

from pathlib import Path

import polars as pl
import yaml

from ipolitico.core.constants import (
    DOMAIN_SOURCE_SYSTEM,
    EARLIEST_DATE_MAP,
    DomainType,
    SourceSystem,
)
from ipolitico.core.domain_spec import spec_for
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.pipeline.domain_order import FULL_PIPELINE
from ipolitico.pipeline.planners.strategies import (
    STRATEGY_REGISTRY,
    SnapshotWindowStrategy,
    strategy_for,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestServidoresWiring:
    """Cada superfície de wiring conhece o domínio SERVIDORES."""

    def test_membro_do_enum(self):
        assert DomainType.SERVIDORES.value == "servidores"

    def test_no_earliest_date_map(self):
        assert DomainType.SERVIDORES in EARLIEST_DATE_MAP

    def test_sistema_de_origem_senado(self):
        assert DOMAIN_SOURCE_SYSTEM[DomainType.SERVIDORES.value] == SourceSystem.SENADO

    def test_spec_snapshot_nao_estavel(self):
        """Snapshot sem watermark; roster muda → stable=False (incremental re-fetch)."""
        spec = spec_for(DomainType.SERVIDORES)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("sequencial",)
        assert spec.depends_on == frozenset()

    def test_estrategia_snapshot_1_job_sem_parametros(self):
        """Planner produz 1 job vazio (roster completo numa chamada, sem janela)."""
        assert STRATEGY_REGISTRY[DomainType.SERVIDORES] is not None
        assert isinstance(strategy_for(DomainType.SERVIDORES), SnapshotWindowStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.SERVIDORES in FULL_PIPELINE

    def test_schema_silver_preserva_sequencial_e_nome(self):
        contract = SILVER_SCHEMAS[DomainType.SERVIDORES.value]
        assert contract["_source_url"] == pl.String
        assert "sequencial" in contract
        assert "nome" in contract
        assert contract["sequencial"] == pl.Int64
        assert contract["nome"] == pl.String

    def test_yaml_senado_adm_registra_dominio(self):
        cfg = yaml.safe_load((REPO_ROOT / "configs" / "senado_adm_pipeline.yaml").read_text())
        config = cfg["domain_configs"]["servidores"]
        assert (
            "ipolitico.extractors.senado.api.servidores.SenadoServidoresExtractor"
            in config["extractor"]
        )
        assert (
            "ipolitico.transformers.senado.servidores_transformer.SenadoServidoresTransformer"
            in config["transformer"]
        )
