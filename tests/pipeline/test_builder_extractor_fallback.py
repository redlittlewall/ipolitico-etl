"""PipelineBuilder: fallback extractor_bulk quando não configurado no YAML."""

import pytest
from ipolitico.core.client import CamaraClient
from ipolitico.core.constants import SinkType, SourceType
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.sinks.datalake_sink import DataLakeSink


@pytest.fixture
def builder():
    client = CamaraClient()
    return PipelineBuilder(client)


def test_builder_fallback_extractor_bulk(builder: PipelineBuilder):
    """builder.build() usa extractor como fallback quando extractor_bulk não está no YAML."""
    domain_cfg = {
        "extractor": ("ipolitico.extractors.camara.api.deputados.DeputadosExtractor"),
        "transformer": (
            "ipolitico.transformers.camara.deputados_transformer.CamaraDeputadosTransformer"
        ),
    }
    components = builder.build(domain_cfg, SinkType.DATALAKE, source_type=SourceType.BULK)
    assert isinstance(components.sink, DataLakeSink)
    from ipolitico.extractors.camara.api.deputados import DeputadosExtractor

    assert isinstance(components.extractor, DeputadosExtractor)


def test_builder_explicit_extractor_bulk_still_works(builder: PipelineBuilder):
    """builder.build() ainda aceita extractor_bulk explícito no YAML."""
    domain_cfg = {
        "extractor": ("ipolitico.extractors.camara.api.deputados.DeputadosExtractor"),
        "extractor_bulk": ("ipolitico.extractors.camara.bulk.base_bulk.BaseBulkExtractor"),
        "transformer": (
            "ipolitico.transformers.camara.deputados_transformer.CamaraDeputadosTransformer"
        ),
    }
    components = builder.build(domain_cfg, SinkType.DATALAKE, source_type=SourceType.BULK)
    assert isinstance(components.sink, DataLakeSink)
    from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor

    assert isinstance(components.extractor, BaseBulkExtractor)
