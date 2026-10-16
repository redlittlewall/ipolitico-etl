"""Issue: quarentena de recursos 500 da API da Câmara — fast-skip no runner.

Um job cujo ``extract()`` sobe ``ResourceQuarantinedError`` deve ser pulado
imediatamente: sem as 5 tentativas externas do runner, contando como processado
para o progresso andar.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from ipolitico.core.constants import DomainType, MedallionLayer
from ipolitico.core.exceptions import ResourceQuarantinedError
from ipolitico.pipeline.builder import PipelineComponents
from ipolitico.pipeline.runner import PipelineRunner


@pytest.mark.asyncio
async def test_runner_skips_quarantined_job(caplog):
    """extract() em quarentena → runner retorna 0 dados, 1 chamada, sem retry."""
    extractor = MagicMock()
    extractor.extract = AsyncMock(
        side_effect=ResourceQuarantinedError("Recurso em quarentena: deputados/1/discursos")
    )
    transformer = MagicMock()
    sink = MagicMock()
    sink.save = AsyncMock()
    sink.flush = AsyncMock()

    components = PipelineComponents(extractor=extractor, transformer=transformer, sink=sink)
    runner = PipelineRunner(max_workers=1)

    with caplog.at_level(logging.WARNING, logger="ipolitico.pipeline.runner"):
        result = await runner.execute(
            components=components,
            items=[{"deputado_id": 1, "start_date": "2015-02-01", "end_date": "2019-01-31"}],
            extract_kwargs_mapper=lambda job: job,
            table_name=DomainType.DISCURSOS.value,
            layer=MedallionLayer.SILVER,
        )

    assert result == 0  # nenhum dado produzido
    assert extractor.extract.await_count == 1  # SEM as 5 tentativas externas
    assert sink.save.await_count == 0  # nada foi gravado
    assert any(
        "quarentena" in r.message.lower() for r in caplog.records
    ), "deve logar linha distinta de skip por quarentena"
