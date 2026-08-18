"""Issue 09 — DESPESAS_CEAPS registrado em todas as superfícies de wiring.

Garante que o domínio participa de full_load / incremental / resume: enum,
registry de cobertura (earliest 2008-01), spec (bulk anual, não estável),
estratégia (``AnnualWindowStrategy`` — 1 job por ano, path ``{ano}`` da API),
pipeline canônica, schema Silver (14 colunas, ``valorReembolsado`` Float64) e
YAML da fonte adm-dadosabertos.
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
    AnnualWindowStrategy,
    strategy_for,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestDespesasCeapsWiring:
    """Cada superfície de wiring conhece o domínio DESPESAS_CEAPS."""

    def test_membro_do_enum(self):
        """Membro do enum com valor canônico em minúsculas (CLI usa o valor)."""
        assert DomainType.DESPESAS_CEAPS.value == "despesas_ceaps"

    def test_no_earliest_date_map(self):
        """Earliest 2008-01 registrado no registry (início real da série)."""
        assert DomainType.DESPESAS_CEAPS in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.DESPESAS_CEAPS] == "2008-01-01"

    def test_sistema_de_origem_senado(self):
        """Sistema de origem registrado como Senado Federal (adm-dadosabertos)."""
        assert DOMAIN_SOURCE_SYSTEM[DomainType.DESPESAS_CEAPS.value] == SourceSystem.SENADO

    def test_spec_bulk_anual_nao_estavel(self):
        """Bulk anual sem watermark; chave (_source_url, id); earliest 2008."""
        spec = spec_for(DomainType.DESPESAS_CEAPS)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("_source_url", "id")
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "2008-01-01"

    def test_estrategia_annual_window(self):
        """Planner gera 1 job por ano — path {ano} da API, sem mês no path."""
        assert STRATEGY_REGISTRY[DomainType.DESPESAS_CEAPS] is not None
        assert isinstance(strategy_for(DomainType.DESPESAS_CEAPS), AnnualWindowStrategy)

    def test_na_pipeline_canonica(self):
        """Presente na pipeline canônica (ordem de execução do full load)."""
        assert DomainType.DESPESAS_CEAPS in FULL_PIPELINE

    def test_schema_silver_14_campos(self):
        """Contrato Silver: 14 colunas (_source_url + 13), valorReembolsado Float64."""
        contract = SILVER_SCHEMAS[DomainType.DESPESAS_CEAPS.value]
        assert contract["_source_url"] == pl.String
        assert len(contract) == 14
        assert contract["id"] == pl.Int64
        assert contract["ano"] == pl.Int64
        assert contract["mes"] == pl.Int64
        assert contract["codSenador"] == pl.Int64
        assert contract["nomeSenador"] == pl.String
        assert contract["data"] == pl.String
        assert contract["valorReembolsado"] == pl.Float64

    def test_yaml_senado_adm_registra_dominio(self):
        cfg = yaml.safe_load((REPO_ROOT / "configs" / "senado_adm_pipeline.yaml").read_text())
        config = cfg["domain_configs"]["despesas_ceaps"]
        assert (
            "ipolitico.extractors.senado.api.despesas_ceaps.SenadoDespesasCeapsExtractor"
            in config["extractor"]
        )
        assert (
            "ipolitico.transformers.senado.despesas_ceaps_transformer.SenadoDespesasCeapsTransformer"
            in config["transformer"]
        )
