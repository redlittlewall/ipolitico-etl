"""Extrator para o domínio VOTACOES_SENADO (votações nominais em plenário)."""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class SenadoVotacoesExtractor(SenadoBaseExtractor):
    """Extrator de votações nominais do plenário do Senado.

    Chama ``/votacao?ano=YYYY`` que retorna um array flat.
    Aceita filtro opcional por ano.
    """

    async def extract(self, year: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai votações de um ano específico ou do ano corrente.

        Args:
            year: Ano para filtrar (ex: 2025). Se omitido, usa ano corrente.
            **kwargs: Parâmetros adicionais (start_date/end_date são aceitos
                      mas o endpoint só suporta filtro por ano).

        Returns:
            DataFrame com os dados brutos das votações.
        """
        if year is None:
            from datetime import datetime

            year = datetime.now().year

        params = {"ano": str(year)}
        raw = await self.fetch_flat("votacao", params=params)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, "votacao", params=params)
