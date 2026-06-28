import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class VotosExtractor(CamaraBaseExtractor):
    """
    Extrator responsável exclusivamente por Votos Nominais.
    Lida com o Problema N+1 recebendo lotes de IDs.
    """

    async def extract(self, votacao_ids: list[str] = None, **kwargs: Any) -> pl.DataFrame:
        if not votacao_ids:
            return pl.DataFrame()

        all_votos = []
        for v_id in votacao_ids:
            endpoint = f"{ApiRoutes.VOTACOES.value}/{v_id}/{ApiRoutes.VOTOS.value}"
            try:
                data = await self.client.fetch(endpoint)
                if data:
                    for item in data:
                        item["votacao_id"] = v_id
                    all_votos.extend(data)
            except Exception as e:
                logger.warning(f"Erro ao extrair votos da votação {v_id}: {e}")
                continue

        return pl.DataFrame(all_votos) if all_votos else pl.DataFrame()
