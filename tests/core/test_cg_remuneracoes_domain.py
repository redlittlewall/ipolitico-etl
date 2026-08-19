"""Ticket 03 — cg_remuneracoes registrado em todas as superfícies de wiring.

Prior art: ``tests/core/test_senado_remuneracoes_domain.py`` — o domínio de
remunerações do Executivo segue o mesmo padrão de bulk mensal: enum, spec
(``unique_keys=("_source_url", "id_servidor", "mes_ano")``), estratégia
(``MonthlyBulkStrategy`` — 1 job por (ano, mês)), pipeline canônica, schema
Silver (identidade + buckets do ``RemuneracaoDTO``) e YAML da fonte
``portaldatransparencia`` com ``extractor_bulk`` + ``module: servidores``.

BLOQUEIO documentado (validação real do ticket 03): o host de dumps
(``portaldatransparencia.gov.br/download-de-dados``) responde 403 AWS WAF +
desafio JS (CAPTCHA) a clientes não-browser — a ingestão está REGISTRADA e a
máquina de bulk TESTADA com fixtures, mas o job real só roda quando o WAF
liberar. O earliest ``2017-01-01`` é um placeholder documentado a validar na
liberação (a CGU publica remunerações do Executivo desde ~2017 nos dumps).
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
    MonthlyBulkStrategy,
    strategy_for,
)
from ipolitico.pipeline.source_router import SourceRouter

REPO_ROOT = Path(__file__).resolve().parents[2]

# Campos do RemuneracaoDTO (API v3, dumps mensais do módulo servidores) que
# existem apenas pós-2020 (a folha do Executivo passou a publicar o detalhe
# completo de rubricas em 2020). Rows pré-2020 → nulo via transformer.
POST_2020_MONETARY_COLUMNS = {
    "gratificacao_natalina",
    "ferias",
    "outras_remuneracoes_eventuais",
    "pensao_militar",
    "fundo_saude",
    "taxa_ocupacao_imovel_funcional",
    "verbas_indenizatorias_civil",
    "verbas_indenizatorias_militar",
    "verbas_indenizatorias_referentes_pdv",
}


class TestCgRemuneracoesWiring:
    """Cada superfície de wiring conhece o domínio cg_remuneracoes."""

    def test_membro_do_enum(self):
        assert DomainType.CG_REMUNERACOES.value == "cg_remuneracoes"

    def test_no_earliest_date_map(self):
        """Placeholder documentado (2017-01-01) a validar quando o WAF liberar."""
        assert DomainType.CG_REMUNERACOES in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.CG_REMUNERACOES] == "2017-01-01"

    def test_sistema_de_origem_portal(self):
        assert (
            DOMAIN_SOURCE_SYSTEM[DomainType.CG_REMUNERACOES.value]
            == SourceSystem.PORTAL_TRANSPARENCIA
        )

    def test_spec_bulk_mensal_nao_estavel(self):
        """Bulk mensal sem watermark; chave (_source_url, id_servidor, mes_ano)."""
        spec = spec_for(DomainType.CG_REMUNERACOES)
        assert spec is not None
        assert spec.watermark_column is None
        assert spec.stable is False
        assert spec.unique_keys == ("_source_url", "id_servidor", "mes_ano")
        assert spec.depends_on == frozenset()
        assert spec.earliest_iso == "2017-01-01"

    def test_estrategia_monthly_bulk(self):
        """Planner gera 1 job por (ano, mês) — path {YYYYMM} do portal."""
        assert STRATEGY_REGISTRY[DomainType.CG_REMUNERACOES] is not None
        assert isinstance(strategy_for(DomainType.CG_REMUNERACOES), MonthlyBulkStrategy)

    def test_na_pipeline_canonica(self):
        assert DomainType.CG_REMUNERACOES in FULL_PIPELINE

    def test_schema_silver_provisional(self):
        """Contrato PROVISIONAL (WAF bloqueado): identidade + buckets pós-2020."""
        contract = SILVER_SCHEMAS[DomainType.CG_REMUNERACOES.value]
        assert contract["_source_url"] == pl.String
        assert contract["id_servidor"] == pl.Int64
        assert contract["nome"] == pl.String
        assert contract["cpf"] == pl.String
        assert contract["matricula"] == pl.String
        assert contract["cod_orgao_lotacao"] == pl.String
        assert contract["nome_orgao_lotacao"] == pl.String
        assert contract["cod_orgao_exercicio"] == pl.String
        assert contract["nome_orgao_exercicio"] == pl.String
        assert contract["mes_ano"] == pl.String
        for col in POST_2020_MONETARY_COLUMNS:
            assert contract[col] == pl.Float64
        for col in (
            "remuneracao_basica",
            "imposto_retido_na_fonte",
            "previdencia_oficial",
            "outras_deducoes_obrigatorias",
            "verbas_indenizatorias",
            "remuneracao_apos_deducoes",
        ):
            assert contract[col] == pl.Float64

    def test_e_bulk_only(self):
        """Sem rota API individual viável: domínio é bulk mensal, bulk_only."""
        meta = bulk_meta_for_domain(DomainType.CG_REMUNERACOES)
        assert meta.get("bulk_only") is True
        assert BULK_REGISTRY["cg_remuneracoes"]["requires_year"] is True
        assert BULK_REGISTRY["cg_remuneracoes"]["requires_month"] is True

    def test_source_router_sempre_bulk(self):
        """bulk_only: FULL_LOAD E INCREMENTAL usam o dump mensal {YYYYMM}."""
        for strategy in (LoadStrategy.FULL_LOAD, LoadStrategy.INCREMENTAL):
            plan = SourceRouter.plan(
                DomainType.CG_REMUNERACOES, strategy, "2026-01-01", "2026-12-31"
            )
            assert plan.source_type == SourceType.BULK

    def test_label_registrado(self):
        assert DomainType.CG_REMUNERACOES in DOMAIN_LABELS

    def test_yaml_portal_registra_dominio(self):
        cfg = yaml.safe_load(
            (REPO_ROOT / "configs" / "portal_transparencia_pipeline.yaml").read_text()
        )
        config = cfg["domain_configs"]["cg_remuneracoes"]
        assert "PortalTransparenciaBulkExtractor" in config["extractor_bulk"]
        assert "PortalRemuneracoesBulkTransformer" in config["transformer"]
        assert config["extractor_kwargs"]["module"] == "servidores"
