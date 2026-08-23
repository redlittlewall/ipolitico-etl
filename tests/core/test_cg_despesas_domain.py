"""Testes de contrato e wiring dos domínios da Fatia 4 da CGU (Despesas, Empenhos e Pagamentos).

Verifica que:
1. Os domínios (cg_despesas_empenhos, cg_despesas_pagamentos) existem em DomainType.
2. Estão mapeados em EARLIEST_DATE_MAP com a convenção de snapshot 1826-04-29.
3. Estão associados ao SourceSystem.PORTAL_TRANSPARENCIA.
4. Possuem DomainSpec registrada em DOMAIN_SPECS com unique_keys corretas.
5. Estão presentes em FULL_PIPELINE na ordem canônica correta.
6. Estão mapeados em STRATEGY_REGISTRY para SnapshotWindowStrategy.
7. O SourceRouter planeja extração via API.
8. Possuem labels descritivos em DOMAIN_LABELS.
9. Possuem contratos Silver estritos definidos em SILVER_SCHEMAS.
10. O portal_transparencia_pipeline.yaml declara extrator e transformador para cada domínio.
"""

from pathlib import Path
import pytest
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
from ipolitico.core.domain_spec import BULK_REGISTRY, bulk_meta_for_domain, spec_for
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.pipeline.domain_order import FULL_PIPELINE
from ipolitico.pipeline.planners.strategies import (
    STRATEGY_REGISTRY,
    SnapshotWindowStrategy,
    strategy_for,
)
from ipolitico.pipeline.source_router import SourceRouter

REPO_ROOT = Path(__file__).resolve().parents[2]

DESPESAS_DOMAINS = (
    DomainType.CG_DESPESAS_EMPENHOS,
    DomainType.CG_DESPESAS_PAGAMENTOS,
)


class TestCgDespesasWiring:
    """Cada superfície de wiring conhece os 2 domínios da Fatia 4 (Despesas Públicas)."""

    @pytest.mark.parametrize("domain,expected_value", [
        (DomainType.CG_DESPESAS_EMPENHOS, "cg_despesas_empenhos"),
        (DomainType.CG_DESPESAS_PAGAMENTOS, "cg_despesas_pagamentos"),
    ])
    def test_membro_do_enum(self, domain: DomainType, expected_value: str):
        assert domain.value == expected_value

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_no_earliest_date_map(self, domain: DomainType):
        """Snapshot — convenção de disponibilidade (1826-04-29)."""
        assert domain in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[domain] == "1826-04-29"

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_sistema_de_origem_portal(self, domain: DomainType):
        assert DOMAIN_SOURCE_SYSTEM[domain.value] == SourceSystem.PORTAL_TRANSPARENCIA

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_spec_snapshot_nao_estavel(self, domain: DomainType):
        spec = spec_for(domain)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("documento",)
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "1826-04-29"

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_estrategia_snapshot_1_job_sem_parametros(self, domain: DomainType):
        assert STRATEGY_REGISTRY[domain] is not None
        assert isinstance(strategy_for(domain), SnapshotWindowStrategy)

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_na_pipeline_canonica(self, domain: DomainType):
        assert domain in FULL_PIPELINE

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_nao_e_bulk(self, domain: DomainType):
        assert bulk_meta_for_domain(domain).get("bulk_only") is not True
        assert BULK_REGISTRY.get(domain.value, {}).get("bulk_only") is not True

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_source_router_sempre_api(self, domain: DomainType):
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(domain, strategy, "2026-01-01", "2026-12-31")
            assert plan.source_type == SourceType.API

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_label_registrado(self, domain: DomainType):
        assert domain in DOMAIN_LABELS

    @pytest.mark.parametrize("domain_name,expected_extractor,expected_transformer", [
        (
            "cg_despesas_empenhos",
            "ipolitico.extractors.portal_transparencia.api.despesas_empenhos_extractor.PortalDespesasEmpenhosApiExtractor",
            "ipolitico.transformers.portal_transparencia.despesas_empenhos_transformer.PortalDespesasEmpenhosTransformer",
        ),
        (
            "cg_despesas_pagamentos",
            "ipolitico.extractors.portal_transparencia.api.despesas_pagamentos_extractor.PortalDespesasPagamentosApiExtractor",
            "ipolitico.transformers.portal_transparencia.despesas_pagamentos_transformer.PortalDespesasPagamentosTransformer",
        ),
    ])
    def test_declarado_no_yaml(self, domain_name: str, expected_extractor: str, expected_transformer: str):
        cfg_path = REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        configs = cfg.get("domain_configs", {})
        assert domain_name in configs
        assert configs[domain_name].get("extractor") == expected_extractor
        assert configs[domain_name].get("transformer") == expected_transformer


class TestDespesasSilverSchemas:
    """Testes dos schemas Silver da Fatia 4."""

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_silver_schema_exists(self, domain: DomainType):
        assert domain.value in SILVER_SCHEMAS
        schema = SILVER_SCHEMAS[domain.value]
        assert "_source_url" in schema

    @pytest.mark.parametrize("domain", DESPESAS_DOMAINS)
    def test_despesas_schema_fields(self, domain: DomainType):
        schema = SILVER_SCHEMAS[domain.value]
        expected_cols = [
            "_source_url",
            "data",
            "documento",
            "documentoResumido",
            "observacao",
            "funcao",
            "subfuncao",
            "programa",
            "acao",
            "subTitulo",
            "localizadorGasto",
            "fase",
            "especie",
            "favorecido",
            "codigoFavorecido",
            "nomeFavorecido",
            "ufFavorecido",
            "valor",
            "codigoUg",
            "ug",
            "codigoUo",
            "uo",
            "codigoOrgao",
            "orgao",
            "codigoOrgaoSuperior",
            "orgaoSuperior",
            "categoria",
            "grupo",
            "elemento",
            "modalidade",
            "numeroProcesso",
            "planoOrcamentario",
            "autor",
            "favorecidoIntermediario",
            "favorecidoListaFaturas",
        ]
        for col in expected_cols:
            assert col in schema
