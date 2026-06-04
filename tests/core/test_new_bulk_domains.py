"""Testes para os novos domínios bulk-only (funcionarios, tecadCategorias, tecadTermos)."""

import polars as pl
from ipolitico.core.constants import DomainType, LoadStrategy
from ipolitico.core.domain_spec import DOMAIN_SPECS
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY
from ipolitico.pipeline.source_router import SourceRouter


class TestNewBulkDomainTypes:
    """DomainType constants existem para os 3 novos domínios bulk-only."""

    def test_domain_type_funcionarios_exists(self):
        assert DomainType.FUNCIONARIOS.value == "funcionarios"

    def test_domain_type_tecad_categorias_exists(self):
        assert DomainType.TECAD_CATEGORIAS.value == "tecad_categorias"

    def test_domain_type_tecad_termos_exists(self):
        assert DomainType.TECAD_TERMOS.value == "tecad_termos"


class TestNewBulkSchemas:
    """SILVER_SCHEMAS entries para os 3 novos domínios."""

    def test_funcionarios_schema_exists(self):
        schema = SILVER_SCHEMAS.get(DomainType.FUNCIONARIOS.value)
        assert schema is not None
        assert "ponto" in schema
        assert "codGrupo" in schema
        assert schema["ponto"] == pl.String
        assert schema["codGrupo"] == pl.Int64

    def test_tecad_categorias_schema_exists(self):
        schema = SILVER_SCHEMAS.get(DomainType.TECAD_CATEGORIAS.value)
        assert schema is not None
        assert "codCategoria" in schema
        assert "categoria" in schema
        assert schema["codCategoria"] == pl.Int64
        assert schema["categoria"] == pl.String

    def test_tecad_termos_schema_exists(self):
        schema = SILVER_SCHEMAS.get(DomainType.TECAD_TERMOS.value)
        assert schema is not None
        assert "codTermo" in schema
        assert "termo" in schema
        assert schema["codTermo"] == pl.Int64
        assert schema["termo"] == pl.String


class TestNewBulkRegistry:
    """BULK_REGISTRY entries para os 3 novos domínios."""

    def test_funcionarios_registry_exists(self):
        entry = BULK_REGISTRY.get("funcionarios")
        assert entry is not None
        assert entry["bulk_granularity"] == "snapshot"
        assert entry["requires_year"] is False
        assert "funcionarios" in entry["url_template"]
        assert entry["bulk_only"] is True

    def test_tecad_categorias_registry_exists(self):
        entry = BULK_REGISTRY.get("tecad_categorias")
        assert entry is not None
        assert entry["bulk_granularity"] == "snapshot"
        assert entry["requires_year"] is False
        assert "tecadCategorias" in entry["url_template"]
        assert entry["bulk_only"] is True

    def test_tecad_termos_registry_exists(self):
        entry = BULK_REGISTRY.get("tecad_termos")
        assert entry is not None
        assert entry["bulk_granularity"] == "snapshot"
        assert entry["requires_year"] is False
        assert "tecadTermos" in entry["url_template"]
        assert entry["bulk_only"] is True

    def test_new_bulk_domains_no_filter_date(self):
        """Domínios snapshot não têm coluna de filtro temporal."""
        for key in ("funcionarios", "tecad_categorias", "tecad_termos"):
            entry = BULK_REGISTRY[key]
            assert entry["bulk_filter_date_column"] is None


class TestNewBulkDomainSpecs:
    """DomainSpec entries para os 3 novos domínios."""

    def test_funcionarios_spec_exists(self):
        spec = DOMAIN_SPECS.get(DomainType.FUNCIONARIOS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.unique_keys == ("ponto",)
        assert spec.sub_domain is None

    def test_tecad_categorias_spec_exists(self):
        spec = DOMAIN_SPECS.get(DomainType.TECAD_CATEGORIAS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.unique_keys == ("codCategoria", "codSubCategoria")
        assert spec.sub_domain is None

    def test_tecad_termos_spec_exists(self):
        spec = DOMAIN_SPECS.get(DomainType.TECAD_TERMOS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.unique_keys == ("codTermo",)
        assert spec.sub_domain is None


class TestNewBulkSourceRouter:
    """SourceRouter sempre retorna BULK para domínios bulk_only."""

    def test_funcionarios_always_bulk_full_load(self):
        plan = SourceRouter.plan(
            DomainType.FUNCIONARIOS,
            LoadStrategy.FULL_LOAD,
            "2025-01-01",
            "2025-12-31",
        )
        assert plan.source_type.value == "bulk"

    def test_tecad_categorias_always_bulk(self):
        plan = SourceRouter.plan(
            DomainType.TECAD_CATEGORIAS,
            LoadStrategy.INCREMENTAL,
            "2025-01-01",
            "2025-12-31",
        )
        assert plan.source_type.value == "bulk"

    def test_tecad_termos_always_bulk(self):
        plan = SourceRouter.plan(
            DomainType.TECAD_TERMOS,
            LoadStrategy.INCREMENTAL,
            "2025-01-01",
            "2025-12-31",
        )
        assert plan.source_type.value == "bulk"
