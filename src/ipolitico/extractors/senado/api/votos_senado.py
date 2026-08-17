"""Extrator para o domínio VOTOS_SENADO (votos individuais em plenário).

Os votos estão embutidos na resposta de ``/votacao?ano=YYYY`` como o
array ``votos[]`` dentro de cada registro de votação. Este extrator
achata a estrutura, adicionando o ID da votação (``codigoSessaoVotacao``)
como chave estrangeira em cada voto.
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class SenadoVotosExtractor(SenadoBaseExtractor):
    """Extrator de votos individuais do plenário do Senado.

    Extrai votos do array ``votos[]`` embutido em cada votação.
    Cada voto recebe o ``codigoSessaoVotacao`` da votação pai.
    """

    async def extract(self, year: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai votos de um ano específico.

        Args:
            year: Ano para filtrar (ex: 2025). Se omitido, usa ano corrente.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com um registro por voto, incluindo o campo
            ``codigoSessaoVotacao`` do pai e os campos do voto.
        """
        if year is None:
            from datetime import datetime

            year = datetime.now().year

        params = {"ano": str(year)}
        raw = await self.fetch_flat("votacao", params=params)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        all_votos: list[dict[str, Any]] = []
        for votacao in raw:
            votos = votacao.get("votos")
            if not votos or not isinstance(votos, list):
                continue
            votacao_id = votacao.get("codigoSessaoVotacao")
            for voto in votos:
                voto["codigoSessaoVotacao"] = votacao_id
                all_votos.append(voto)

        if not all_votos:
            return pl.DataFrame()

        df = pl.DataFrame(all_votos, infer_schema_length=None)
        return self._inject_source_url(df, "votacao", params=params)
