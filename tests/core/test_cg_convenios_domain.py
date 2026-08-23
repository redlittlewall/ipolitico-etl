"""Testes de contrato e wiring dos domínios da Fatia 3 da CGU (Convênios e Repasses).

Verifica que:
1. Os domínios (cg_convenios, cg_convenios_aditivos) existem em DomainType.
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

CONVENIOS_DOMAINS = (
    DomainType.CG_CONVENIOS,
    DomainType.CG_CONVENIOS_ADITIVOS,
)


class TestCgConveniosWiring:
    """Cada superfície de wiring conhece os 2 domínios da Fatia 3 (Convênios)."""

    @pytest.mark.parametrize("domain,expected_value", [
        (DomainType.CG_CONVENIOS, "cg_convenios"),
        (DomainType.CG_CONVENIOS_ADITIVOS, "cg_convenios_aditivos"),
    ])
    def test_membro_do_enum(self, domain: DomainType, expected_value: str):
        assert domain.value == expected_value

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_no_earliest_date_map(self, domain: DomainType):
        """Snapshot — convenção de disponibilidade (1826-04-29)."""
        assert domain in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[domain] == "1826-04-29"

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_sistema_de_origem_portal(self, domain: DomainType):
        assert DOMAIN_SOURCE_SYSTEM[domain.value] == SourceSystem.PORTAL_TRANSPARENCIA

    @pytest.mark.parametrize("domain,expected_uk", [
        (DomainType.CG_CONVENIOS, ("id",)),
        (DomainType.CG_CONVENIOS_ADITIVOS, ("idConvenio", "numero")),
    ])
    def test_spec_snapshot_nao_estavel(self, domain: DomainType, expected_uk: tuple[str, ...]):
        spec = spec_for(domain)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == expected_uk
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "1826-04-29"

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_estrategia_snapshot_1_job_sem_parametros(self, domain: DomainType):
        assert STRATEGY_REGISTRY[domain] is not None
        assert isinstance(strategy_for(domain), SnapshotWindowStrategy)

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_na_pipeline_canonica(self, domain: DomainType):
        assert domain in FULL_PIPELINE

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_nao_e_bulk(self, domain: DomainType):
        assert bulk_meta_for_domain(domain).get("bulk_only") is not True
        assert BULK_REGISTRY.get(domain.value, {}).get("bulk_only") is not True

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_source_router_sempre_api(self, domain: DomainType):
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(domain, strategy, "2026-01-01", "2026-12-31")
            assert plan.source_type == SourceType.API

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_label_registrado(self, domain: DomainType):
        assert domain in DOMAIN_LABELS

    @pytest.mark.parametrize("domain_name,expected_extractor,expected_transformer", [
        (
            "cg_convenios",
            "ipolitico.extractors.portal_transparencia.api.convenios_extractor.PortalConveniosApiExtractor",
            "ipolitico.transformers.portal_transparencia.convenios_transformer.PortalConveniosTransformer",
        ),
        (
            "cg_convenios_aditivos",
            "ipolitico.extractors.portal_transparencia.api.convenios_aditivos_extractor.PortalConveniosAditivosApiExtractor",
            "ipolitico.transformers.portal_transparencia.convenios_aditivos_transformer.PortalConveniosAditivosTransformer",
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


class TestConveniosSilverSchemas:
    """Testes dos schemas Silver da Fatia 3."""

    @pytest.mark.parametrize("domain", CONVENIOS_DOMAINS)
    def test_silver_schema_exists(self, domain: DomainType):
        assert domain.value in SILVER_SCHEMAS
        schema = SILVER_SCHEMAS[domain.value]
        assert "_source_url" in schema

    def test_convenios_schema_fields(self):
        schema = SILVER_SCHEMAS[DomainType.CG_CONVENIOS.value]
        expected_cols = [
            "_source_url",
            "id",
            "dataReferencia",
            "dataInicioVigencia",
            "dataFinalVigencia",
            "dataPublicacao",
            "dataUltimaLiberacao",
            "dataConclusao",
            "situacao",
            "numeroProcesso",
            "valor",
            "valorLiberado",
            "valorContrapartida",
            "valorDaUltimaLiberacao",
            "dimConvenio_codigo",
            "dimConvenio_objeto",
            "dimConvenio_numero",
            "convenente_id",
            "convenente_cpfFormatado",
            "convenente_cnpjFormatado",
            "convenente_numeroInscricaoSocial",
            "convenente_nome",
            "convenente_razaoSocialReceita",
            "convenente_nomeFantasiaReceita",
            "convenente_tipo",
            "municipioConvenente_codigoIBGE",
            "municipioConvenente_nomeIBGE",
            "municipioConvenente_codigoRegiao",
            "municipioConvenente_nomeRegiao",
            "municipioConvenente_pais",
            "municipioConvenente_uf_sigla",
            "municipioConvenente_uf_nome",
            "orgao_codigoSIAFI",
            "orgao_nome",
            "orgao_cnpj",
            "orgao_sigla",
            "orgao_descricaoPoder",
            "unidadeGestora_codigo",
            "unidadeGestora_nome",
            "unidadeGestora_descricaoPoder",
            "tipoInstrumento_codigo",
            "tipoInstrumento_descricao",
        ]
        for col in expected_cols:
            assert col in schema

    def test_convenios_aditivos_schema_fields(self):
        schema = SILVER_SCHEMAS[DomainType.CG_CONVENIOS_ADITIVOS.value]
        expected_cols = [
            "_source_url",
            "idConvenio",
            "numero",
            "dataPublicacao",
            "objetoAditivo",
            "valorAditivo",
        ]
        for col in expected_cols:
            assert col in schema
