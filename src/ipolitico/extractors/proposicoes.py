import polars as pl

from ipolitico.core.config import LEGISLATURA_ATUAL
from ipolitico.extractors.base import BaseExtractor


class ProposicoesExtractor(BaseExtractor):
    """
    Extrator de proposições legislativas com suporte a carga incremental.
    """

    async def extract(self, data_inicio: str = None) -> pl.DataFrame:
        """
        Extrai proposições. Se data_inicio for omitida, busca no banco o
        último registro de 'dataApresentacao'.
        """
        if not data_inicio:
            # O método _get_last_watermark vem da BaseExtractor
            data_inicio = (
                self._get_last_watermark("proposicoes", "dataApresentacao") or "2023-02-01"
            )

        params = {
            "idLegislatura": LEGISLATURA_ATUAL,
            "dataInicio": data_inicio,
            "ordem": "ASC",
            "ordenarPor": "id",
        }

        dados = await self.client.fetch("proposicoes", params=params)
        return pl.DataFrame(dados)
