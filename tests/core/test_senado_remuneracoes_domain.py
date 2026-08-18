"""Issue 08 — REMUNERACOES registrado em todas as superfícies de wiring.

Garante que o domínio participa de full_load / incremental / resume: enum,
registry de cobertura (earliest 2013-01), spec (bulk mensal, não estável),
estratégia (``MonthlyBulkStrategy`` — 1 job por (ano, mês)), pipeline canônica,
schema Silver (20 campos, 15 monetários Float64) e YAML da fonte adm-dadosabertos.
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
    MonthlyBulkStrategy,
    strategy_for,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# 15 campos monetários do payload (string BR → Float64 na Silver).
MONETARY_COLUMNS = {
    "remuneracao_basica",
    "vantagens_pessoais",
    "funcao_comissionada",
    "gratificacao_natalina",
    "horas_extras",
    "outras_eventuais",
    "abono_permanencia",
    "reversao_teto_constitucional",
    "imposto_renda",
    "previdencia",
    "faltas",
    "remuneracao_liquida",
    "diarias",
    "auxilios",
    "vantagens_indenizatorias",
}


class TestRemuneracoesWiring:
    """Cada superfície de wiring conhece o domínio REMUNERACOES."""

    def test_membro_do_enum(self):
        assert DomainType.REMUNERACOES.value == "remuneracoes"

    def test_no_earliest_date_map(self):
        """Earliest 2013-01 registrado no registry (início real da série)."""
        assert DomainType.REMUNERACOES in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.REMUNERACOES] == "2013-01-01"

    def test_sistema_de_origem_senado(self):
        assert DOMAIN_SOURCE_SYSTEM[DomainType.REMUNERACOES.value] == SourceSystem.SENADO

    def test_spec_bulk_mensal_nao_estavel(self):
        """Bulk mensal sem watermark; chave (_source_url, sequencial, tipo_folha)."""
        spec = spec_for(DomainType.REMUNERACOES)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("_source_url", "sequencial", "tipo_folha")
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "2013-01-01"

    def test_estrategia_monthly_bulk(self):
        """Planner gera 1 job por (ano, mês) — path {ano}/{mes} da API."""
        assert STRATEGY_REGISTRY[DomainType.REMUNERACOES] is not None
        assert isinstance(strategy_for(DomainType.REMUNERACOES), MonthlyBulkStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.REMUNERACOES in FULL_PIPELINE

    def test_schema_silver_20_campos(self):
        """Contrato Silver: 21 colunas (_source_url + 20), monetários Float64."""
        contract = SILVER_SCHEMAS[DomainType.REMUNERACOES.value]
        assert contract["_source_url"] == pl.String
        assert len(contract) == 21
        assert contract["sequencial"] == pl.Int64
        assert contract["nome"] == pl.String
        assert contract["mes"] == pl.Int64
        assert contract["ano"] == pl.Int64
        assert contract["tipo_folha"] == pl.String
        for col in MONETARY_COLUMNS:
            assert contract[col] == pl.Float64

    def test_yaml_senado_adm_registra_dominio(self):
        cfg = yaml.safe_load((REPO_ROOT / "configs" / "senado_adm_pipeline.yaml").read_text())
        config = cfg["domain_configs"]["remuneracoes"]
        assert (
            "ipolitico.extractors.senado.api.remuneracoes.SenadoRemuneracoesExtractor"
            in config["extractor"]
        )
        assert (
            "ipolitico.transformers.senado.remuneracoes_transformer.SenadoRemuneracoesTransformer"
            in config["transformer"]
        )
