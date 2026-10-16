"""Testes de integração do domínio camara_gabinete_assessores no pipeline."""

from pathlib import Path

import yaml

from ipolitico.core.camara_client import CamaraClient
from ipolitico.core.constants import DomainType, SinkType
from ipolitico.core.domain_spec import DOMAIN_SPECS
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.extractors.camara.scraper.pessoal_gabinete import (
    CamaraPessoalGabineteExtractor,
)
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.domain_order import (
    DOMAIN_UPSTREAM_REQUIREMENTS,
    FULL_PIPELINE,
    expand_domains_with_dependencies,
)
from ipolitico.transformers.camara.pessoal_gabinete_transformer import (
    CamaraPessoalGabineteTransformer,
)


def test_camara_gabinete_assessores_domain_registrations():
    """Garante registro completo nos contratos e orquestração do ETL."""
    domain = DomainType.CAMARA_GABINETE_ASSESSORES

    assert domain in DOMAIN_SPECS
    spec = DOMAIN_SPECS[domain]
    assert spec.domain == domain
    assert DomainType.DEPUTADOS in spec.depends_on
    assert spec.unique_keys == ("deputado_id", "nome_assessor", "cargo")

    assert domain.value in SILVER_SCHEMAS
    schema = SILVER_SCHEMAS[domain.value]
    expected_cols = [
        "_source_url",
        "deputado_id",
        "nome_assessor",
        "cargo",
        "grupo_funcional",
        "data_exercicio",
        "captured_at",
    ]
    assert list(schema.keys()) == expected_cols

    assert domain in FULL_PIPELINE
    assert domain in DOMAIN_UPSTREAM_REQUIREMENTS
    assert DomainType.DEPUTADOS in DOMAIN_UPSTREAM_REQUIREMENTS[domain]

    expanded = expand_domains_with_dependencies([domain])
    assert DomainType.DEPUTADOS in expanded
    assert expanded.index(DomainType.DEPUTADOS) < expanded.index(domain)


def test_camara_gabinete_assessores_builder():
    """Garante que o PipelineBuilder constrói extractor e transformer a partir do YAML."""
    config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "camara_pipeline.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    domain_key = DomainType.CAMARA_GABINETE_ASSESSORES.value
    assert domain_key in config["domain_configs"]
    domain_cfg = config["domain_configs"][domain_key]

    builder = PipelineBuilder(client=CamaraClient())
    components = builder.build(domain_cfg, SinkType.DATALAKE)

    assert isinstance(components.extractor, CamaraPessoalGabineteExtractor)
    assert isinstance(components.transformer, CamaraPessoalGabineteTransformer)
