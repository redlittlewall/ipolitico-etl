"""PipelineBuilder: fallback de sink quando sinks não está no YAML."""

import pytest

from ipolitico.core.camara_client import CamaraClient
from ipolitico.core.constants import SinkType
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.sinks.datalake_sink import DataLakeSink


@pytest.fixture
def builder():
    client = CamaraClient()
    return PipelineBuilder(client)


def test_builder_default_sink_when_not_configured(builder: PipelineBuilder):
    """builder.build() usa DataLakeSink como fallback quando sinks não está configurado."""
    domain_cfg = {
        "extractor": ("ipolitico.extractors.camara.api.deputados.DeputadosExtractor"),
        "transformer": (
            "ipolitico.transformers.camara.deputados_transformer.CamaraDeputadosTransformer"
        ),
    }
    components = builder.build(domain_cfg, SinkType.DATALAKE)
    assert isinstance(components.sink, DataLakeSink)


def test_builder_custom_sink_still_works(builder: PipelineBuilder):
    """builder.build() ainda aceita sink explícito no YAML."""
    domain_cfg = {
        "extractor": ("ipolitico.extractors.camara.api.deputados.DeputadosExtractor"),
        "transformer": (
            "ipolitico.transformers.camara.deputados_transformer.CamaraDeputadosTransformer"
        ),
        "sinks": {
            "datalake": "ipolitico.sinks.datalake_sink.DataLakeSink",
        },
    }
    components = builder.build(domain_cfg, SinkType.DATALAKE)
    assert isinstance(components.sink, DataLakeSink)
