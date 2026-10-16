"""Testes de contrato e wiring dos domínios da Fatia 2 da CGU (Compras Públicas).

Verifica que:
1. Os domínios (cg_licitacoes, cg_contratos, cg_contratos_aditivos) existem em DomainType.
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

COMPRAS_DOMAINS = (
    DomainType.CG_LICITACOES,
    DomainType.CG_CONTRATOS,
    DomainType.CG_CONTRATOS_ADITIVOS,
)


class TestCgComprasWiring:
    """Cada superfície de wiring conhece os 3 domínios da Fatia 2 (Compras Públicas)."""

    @pytest.mark.parametrize("domain,expected_value", [
        (DomainType.CG_LICITACOES, "cg_licitacoes"),
        (DomainType.CG_CONTRATOS, "cg_contratos"),
        (DomainType.CG_CONTRATOS_ADITIVOS, "cg_contratos_aditivos"),
    ])
    def test_membro_do_enum(self, domain: DomainType, expected_value: str):
        assert domain.value == expected_value

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_no_earliest_date_map(self, domain: DomainType):
        """Snapshot — convenção de disponibilidade (1826-04-29)."""
        assert domain in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[domain] == "1826-04-29"

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_sistema_de_origem_portal(self, domain: DomainType):
        assert DOMAIN_SOURCE_SYSTEM[domain.value] == SourceSystem.PORTAL_TRANSPARENCIA

    @pytest.mark.parametrize("domain,expected_uk", [
        (DomainType.CG_LICITACOES, ("id",)),
        (DomainType.CG_CONTRATOS, ("id",)),
        (DomainType.CG_CONTRATOS_ADITIVOS, ("idContrato", "numero")),
    ])
    def test_spec_snapshot_nao_estavel(self, domain: DomainType, expected_uk: tuple[str, ...]):
        spec = spec_for(domain)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == expected_uk
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "1826-04-29"

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_estrategia_snapshot_1_job_sem_parametros(self, domain: DomainType):
        assert STRATEGY_REGISTRY[domain] is not None
        assert isinstance(strategy_for(domain), SnapshotWindowStrategy)

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_na_pipeline_canonica(self, domain: DomainType):
        assert domain in FULL_PIPELINE

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_nao_e_bulk(self, domain: DomainType):
        assert bulk_meta_for_domain(domain).get("bulk_only") is not True
        assert BULK_REGISTRY.get(domain.value, {}).get("bulk_only") is not True

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_source_router_sempre_api(self, domain: DomainType):
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(domain, strategy, "2026-01-01", "2026-12-31")
            assert plan.source_type == SourceType.API

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_label_registrado(self, domain: DomainType):
        assert domain in DOMAIN_LABELS

    @pytest.mark.parametrize("domain_name,expected_extractor,expected_transformer", [
        (
            "cg_licitacoes",
            "ipolitico.extractors.portal_transparencia.api.licitacoes_extractor.PortalLicitacoesApiExtractor",
            "ipolitico.transformers.portal_transparencia.licitacoes_transformer.PortalLicitacoesTransformer",
        ),
        (
            "cg_contratos",
            "ipolitico.extractors.portal_transparencia.api.contratos_extractor.PortalContratosApiExtractor",
            "ipolitico.transformers.portal_transparencia.contratos_transformer.PortalContratosTransformer",
        ),
        (
            "cg_contratos_aditivos",
            "ipolitico.extractors.portal_transparencia.api.contratos_aditivos_extractor.PortalContratosAditivosApiExtractor",
            "ipolitico.transformers.portal_transparencia.contratos_aditivos_transformer.PortalContratosAditivosTransformer",
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


class TestComprasSilverSchemas:
    """Testes dos schemas Silver da Fatia 2."""

    @pytest.mark.parametrize("domain", COMPRAS_DOMAINS)
    def test_silver_schema_exists(self, domain: DomainType):
        assert domain.value in SILVER_SCHEMAS
        schema = SILVER_SCHEMAS[domain.value]
        assert "_source_url" in schema

    def test_licitacoes_schema_fields(self):
        schema = SILVER_SCHEMAS[DomainType.CG_LICITACOES.value]
        expected_cols = [
            "_source_url",
            "id",
            "dataResultadoCompra",
            "dataAbertura",
            "dataReferencia",
            "dataPublicacao",
            "situacaoCompra",
            "modalidadeLicitacao",
            "instrumentoLegal",
            "valor",
            "licitacao_numero",
            "licitacao_objeto",
            "licitacao_numeroProcesso",
            "licitacao_contatoResponsavel",
            "municipio_codigoIBGE",
            "municipio_nomeIBGE",
            "municipio_codigoRegiao",
            "municipio_nomeRegiao",
            "municipio_pais",
            "municipio_uf_sigla",
            "municipio_uf_nome",
            "unidadeGestora_codigo",
            "unidadeGestora_nome",
            "unidadeGestora_descricaoPoder",
            "unidadeGestora_orgaoVinculado_codigoSIAFI",
            "unidadeGestora_orgaoVinculado_nome",
            "unidadeGestora_orgaoVinculado_sigla",
            "unidadeGestora_orgaoMaximo_codigo",
            "unidadeGestora_orgaoMaximo_nome",
            "unidadeGestora_orgaoMaximo_sigla",
        ]
        for col in expected_cols:
            assert col in schema

    def test_contratos_schema_fields(self):
        schema = SILVER_SCHEMAS[DomainType.CG_CONTRATOS.value]
        expected_cols = [
            "_source_url",
            "id",
            "numero",
            "objeto",
            "numeroProcesso",
            "fundamentoLegal",
            "situacaoContrato",
            "modalidadeCompra",
            "dataAssinatura",
            "dataPublicacaoDOU",
            "dataInicioVigencia",
            "dataFimVigencia",
            "valorInicialCompra",
            "valorFinalCompra",
            "compra_numero",
            "compra_objeto",
            "compra_numeroProcesso",
            "compra_contatoResponsavel",
            "unidadeGestora_codigo",
            "unidadeGestora_nome",
            "unidadeGestora_descricaoPoder",
            "unidadeGestora_orgaoVinculado_codigoSIAFI",
            "unidadeGestora_orgaoVinculado_nome",
            "unidadeGestora_orgaoVinculado_sigla",
            "unidadeGestora_orgaoMaximo_codigo",
            "unidadeGestora_orgaoMaximo_nome",
            "unidadeGestora_orgaoMaximo_sigla",
            "unidadeGestoraCompras_codigo",
            "unidadeGestoraCompras_nome",
            "unidadeGestoraCompras_descricaoPoder",
            "fornecedor_id",
            "fornecedor_cpfFormatado",
            "fornecedor_cnpjFormatado",
            "fornecedor_numeroInscricaoSocial",
            "fornecedor_nome",
            "fornecedor_razaoSocialReceita",
            "fornecedor_nomeFantasiaReceita",
            "fornecedor_tipo",
        ]
        for col in expected_cols:
            assert col in schema

    def test_contratos_aditivos_schema_fields(self):
        schema = SILVER_SCHEMAS[DomainType.CG_CONTRATOS_ADITIVOS.value]
        expected_cols = [
            "_source_url",
            "idContrato",
            "numero",
            "dataPublicacao",
            "objetoAditivo",
        ]
        for col in expected_cols:
            assert col in schema
