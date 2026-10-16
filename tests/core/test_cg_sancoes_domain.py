"""Fatia 1 CGU — Sanções, Cadastros Restritivos e Acordos de Leniência.

Testes de wiring e contratos para os domínios:
- cg_ceis (CEIS - Empresas Inidôneas e Suspensas)
- cg_cnep (CNEP - Empresas Punidas)
- cg_cepim (CEPIM - Entidades Impedidas)
- cg_ceaf (CEAF - Expulsões da Administração Federal)
- cg_acordos_leniencia (Acordos de Leniência)
"""

from pathlib import Path
import polars as pl
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

SANCOES_DOMAINS = (
    DomainType.CG_CEIS,
    DomainType.CG_CNEP,
    DomainType.CG_CEPIM,
    DomainType.CG_CEAF,
    DomainType.CG_ACORDOS_LENIENCIA,
)


class TestCgSancoesWiring:
    """Cada superfície de wiring conhece os 5 domínios da Fatia 1 (Sanções)."""

    @pytest.mark.parametrize("domain,expected_value", [
        (DomainType.CG_CEIS, "cg_ceis"),
        (DomainType.CG_CNEP, "cg_cnep"),
        (DomainType.CG_CEPIM, "cg_cepim"),
        (DomainType.CG_CEAF, "cg_ceaf"),
        (DomainType.CG_ACORDOS_LENIENCIA, "cg_acordos_leniencia"),
    ])
    def test_membro_do_enum(self, domain: DomainType, expected_value: str):
        assert domain.value == expected_value

    @pytest.mark.parametrize("domain", SANCOES_DOMAINS)
    def test_no_earliest_date_map(self, domain: DomainType):
        """Snapshot — convenção de disponibilidade (1826-04-29)."""
        assert domain in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[domain] == "1826-04-29"

    @pytest.mark.parametrize("domain", SANCOES_DOMAINS)
    def test_sistema_de_origem_portal(self, domain: DomainType):
        assert DOMAIN_SOURCE_SYSTEM[domain.value] == SourceSystem.PORTAL_TRANSPARENCIA

    @pytest.mark.parametrize("domain,expected_uk", [
        (DomainType.CG_CEIS, ("id",)),
        (DomainType.CG_CNEP, ("id",)),
        (DomainType.CG_CEPIM, ("id",)),
        (DomainType.CG_CEAF, ("id",)),
        (DomainType.CG_ACORDOS_LENIENCIA, ("id", "cnpjEmpresa")),
    ])
    def test_spec_snapshot_nao_estavel(self, domain: DomainType, expected_uk: tuple[str, ...]):
        spec = spec_for(domain)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == expected_uk
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "1826-04-29"

    @pytest.mark.parametrize("domain", SANCOES_DOMAINS)
    def test_estrategia_snapshot_1_job_sem_parametros(self, domain: DomainType):
        assert STRATEGY_REGISTRY[domain] is not None
        assert isinstance(strategy_for(domain), SnapshotWindowStrategy)

    @pytest.mark.parametrize("domain", SANCOES_DOMAINS)
    def test_na_pipeline_canonica(self, domain: DomainType):
        assert domain in FULL_PIPELINE

    @pytest.mark.parametrize("domain", SANCOES_DOMAINS)
    def test_nao_e_bulk(self, domain: DomainType):
        assert bulk_meta_for_domain(domain).get("bulk_only") is not True
        assert BULK_REGISTRY.get(domain.value, {}).get("bulk_only") is not True

    @pytest.mark.parametrize("domain", SANCOES_DOMAINS)
    def test_source_router_sempre_api(self, domain: DomainType):
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(domain, strategy, "2026-01-01", "2026-12-31")
            assert plan.source_type == SourceType.API

    @pytest.mark.parametrize("domain", SANCOES_DOMAINS)
    def test_label_registrado(self, domain: DomainType):
        assert domain in DOMAIN_LABELS

    @pytest.mark.parametrize("domain_name,expected_extractor,expected_transformer", [
        ("cg_ceis", "PortalCeisApiExtractor", "PortalCeisTransformer"),
        ("cg_cnep", "PortalCnepApiExtractor", "PortalCnepTransformer"),
        ("cg_cepim", "PortalCepimApiExtractor", "PortalCepimTransformer"),
        ("cg_ceaf", "PortalCeafApiExtractor", "PortalCeafTransformer"),
        ("cg_acordos_leniencia", "PortalAcordosLenienciaApiExtractor", "PortalAcordosLenienciaTransformer"),
    ])
    def test_yaml_portal_registra_dominio(self, domain_name: str, expected_extractor: str, expected_transformer: str):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"][domain_name]
        assert expected_extractor in config["extractor"]
        assert expected_transformer in config["transformer"]
        assert "extractor_bulk" not in config

    def test_schema_silver_ceis(self):
        contract = SILVER_SCHEMAS[DomainType.CG_CEIS.value]
        assert contract["_source_url"] == pl.String
        assert contract["id"] == pl.Int64
        assert contract["dataReferencia"] == pl.String
        assert contract["dataInicioSancao"] == pl.String
        assert contract["dataFimSancao"] == pl.String
        assert contract["dataPublicacaoSancao"] == pl.String
        assert contract["dataTransitadoJulgado"] == pl.String
        assert contract["dataOrigemInformacao"] == pl.String
        assert contract["tipoSancao_descricaoResumida"] == pl.String
        assert contract["tipoSancao_descricaoPortal"] == pl.String
        assert contract["fonteSancao_nomeExibicao"] == pl.String
        assert contract["fonteSancao_telefoneContato"] == pl.String
        assert contract["fonteSancao_enderecoContato"] == pl.String
        assert contract["orgaoSancionador_nome"] == pl.String
        assert contract["orgaoSancionador_siglaUf"] == pl.String
        assert contract["orgaoSancionador_poder"] == pl.String
        assert contract["orgaoSancionador_esfera"] == pl.String
        assert contract["sancionado_nome"] == pl.String
        assert contract["sancionado_codigoFormatado"] == pl.String
        assert contract["pessoa_id"] == pl.Int64
        assert contract["pessoa_cpfFormatado"] == pl.String
        assert contract["pessoa_cnpjFormatado"] == pl.String
        assert contract["pessoa_numeroInscricaoSocial"] == pl.String
        assert contract["pessoa_nome"] == pl.String
        assert contract["pessoa_razaoSocialReceita"] == pl.String
        assert contract["pessoa_nomeFantasiaReceita"] == pl.String
        assert contract["pessoa_tipo"] == pl.String
        assert contract["textoPublicacao"] == pl.String
        assert contract["linkPublicacao"] == pl.String
        assert contract["detalhamentoPublicacao"] == pl.String
        assert contract["numeroProcesso"] == pl.String
        assert contract["abrangenciaDefinidaDecisaoJudicial"] == pl.String
        assert contract["informacoesAdicionaisDoOrgaoSancionador"] == pl.String
        assert contract["fundamentacao"] == pl.String

    def test_schema_silver_cnep(self):
        contract = SILVER_SCHEMAS[DomainType.CG_CNEP.value]
        assert contract["_source_url"] == pl.String
        assert contract["id"] == pl.Int64
        assert contract["valorMulta"] == pl.Float64
        assert contract["sancionado_nome"] == pl.String
        assert contract["sancionado_codigoFormatado"] == pl.String
        assert contract["fundamentacao"] == pl.String

    def test_schema_silver_cepim(self):
        contract = SILVER_SCHEMAS[DomainType.CG_CEPIM.value]
        assert contract["_source_url"] == pl.String
        assert contract["id"] == pl.Int64
        assert contract["dataReferencia"] == pl.String
        assert contract["motivo"] == pl.String
        assert contract["orgaoSuperior_nome"] == pl.String
        assert contract["orgaoSuperior_codigoSIAFI"] == pl.String
        assert contract["orgaoSuperior_cnpj"] == pl.String
        assert contract["orgaoSuperior_sigla"] == pl.String
        assert contract["orgaoSuperior_descricaoPoder"] == pl.String
        assert contract["pessoaJuridica_id"] == pl.Int64
        assert contract["pessoaJuridica_cpfFormatado"] == pl.String
        assert contract["pessoaJuridica_cnpjFormatado"] == pl.String
        assert contract["pessoaJuridica_numeroInscricaoSocial"] == pl.String
        assert contract["pessoaJuridica_nome"] == pl.String
        assert contract["pessoaJuridica_razaoSocialReceita"] == pl.String
        assert contract["pessoaJuridica_nomeFantasiaReceita"] == pl.String
        assert contract["pessoaJuridica_tipo"] == pl.String
        assert contract["convenio_codigo"] == pl.String
        assert contract["convenio_objeto"] == pl.String
        assert contract["convenio_numero"] == pl.String

    def test_schema_silver_ceaf(self):
        contract = SILVER_SCHEMAS[DomainType.CG_CEAF.value]
        assert contract["_source_url"] == pl.String
        assert contract["id"] == pl.Int64
        assert contract["dataPublicacao"] == pl.String
        assert contract["dataReferencia"] == pl.String
        assert contract["punicao_cpfPunidoFormatado"] == pl.String
        assert contract["punicao_nomePunido"] == pl.String
        assert contract["punicao_portaria"] == pl.String
        assert contract["punicao_processo"] == pl.String
        assert contract["punicao_paginaDOU"] == pl.String
        assert contract["punicao_secaoDOU"] == pl.String
        assert contract["tipoPunicao_descricao"] == pl.String
        assert contract["pessoa_id"] == pl.Int64
        assert contract["pessoa_cpfFormatado"] == pl.String
        assert contract["pessoa_cnpjFormatado"] == pl.String
        assert contract["pessoa_numeroInscricaoSocial"] == pl.String
        assert contract["pessoa_nome"] == pl.String
        assert contract["pessoa_razaoSocialReceita"] == pl.String
        assert contract["pessoa_nomeFantasiaReceita"] == pl.String
        assert contract["pessoa_tipo"] == pl.String
        assert contract["orgaoLotacao_siglaDaPasta"] == pl.String
        assert contract["orgaoLotacao_sigla"] == pl.String
        assert contract["orgaoLotacao_nome"] == pl.String
        assert contract["orgaoLotacao_nomeSemAcento"] == pl.String
        assert contract["ufLotacaoPessoa_codigoIBGE"] == pl.String
        assert contract["ufLotacaoPessoa_codigoCNPJEstado"] == pl.String
        assert contract["ufLotacaoPessoa_populacao"] == pl.Int64
        assert contract["cargoEfetivo"] == pl.String
        assert contract["codigoCargoComissao"] == pl.String
        assert contract["cargoComissao"] == pl.String
        assert contract["fundamentacao"] == pl.String

    def test_schema_silver_acordos_leniencia(self):
        contract = SILVER_SCHEMAS[DomainType.CG_ACORDOS_LENIENCIA.value]
        assert contract["_source_url"] == pl.String
        assert contract["id"] == pl.Int64
        assert contract["dataInicioAcordo"] == pl.String
        assert contract["dataFimAcordo"] == pl.String
        assert contract["orgaoResponsavel"] == pl.String
        assert contract["situacaoAcordo"] == pl.String
        assert contract["quantidade"] == pl.Int64
        assert contract["cnpjEmpresa"] == pl.String
        assert contract["cnpjFormatadoEmpresa"] == pl.String
        assert contract["razaoSocialEmpresa"] == pl.String
        assert contract["nomeFantasiaEmpresa"] == pl.String
        assert contract["nomeInformadoOrgaoResponsavel"] == pl.String
