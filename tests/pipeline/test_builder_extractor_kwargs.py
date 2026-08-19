"""PipelineBuilder: merge de ``extractor_kwargs`` declarados no YAML (ticket 02).

O portal constrói a URL por convenção de segmento (``/download-de-dados/{module}``),
mas o ``domain_name`` do runner é o domínio do pipeline (``cg_servidores``). O
YAML declara ``extractor_kwargs: {module: servidores}`` e o builder injeta
``domain_name`` à parte — sem isso, o extrator montaria
``/download-de-dados/cg_servidores`` (404). O teste usa ``servidores`` (módulo
bulk real do portal); o tracer bullet do ticket 02 (``cg_orgaos``) acabou sendo
API v3, mas o mecanismo serve aos módulos bulk das próximas fatias.
"""

from ipolitico.core.constants import SinkType, SourceType
from ipolitico.core.portal_transparencia_client import PortalTransparenciaClient
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.transformers.portal_transparencia.orgaos_transformer import (
    PortalOrgaosTransformer,
)


def test_builder_merge_extractor_kwargs_module():
    """``extractor_kwargs.module`` do YAML + ``domain_name`` do runner → ambos injetados."""
    builder = PipelineBuilder(PortalTransparenciaClient(api_key="chave-de-teste"))
    domain_cfg = {
        "extractor_bulk": (
            "ipolitico.extractors.portal_transparencia.bulk.bulk_extractor."
            "PortalTransparenciaBulkExtractor"
        ),
        "transformer": (
            "ipolitico.transformers.portal_transparencia.orgaos_transformer.PortalOrgaosTransformer"
        ),
        "extractor_kwargs": {"module": "servidores"},
    }
    components = builder.build(
        domain_cfg, SinkType.DATALAKE, source_type=SourceType.BULK, domain_name="cg_servidores"
    )

    ext = components.extractor
    assert ext.module == "servidores"
    assert ext.domain_name == "cg_servidores"
    assert isinstance(components.transformer, PortalOrgaosTransformer)
