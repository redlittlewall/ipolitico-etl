"""Rota filha de /blocos/{id}/partidos."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class BlocoPartidosExtractor(CamaraBaseExtractor):
    """Extrator de /blocos/{id}/partidos.

    Coleta os partidos de cada bloco e adiciona colunas de auditoria
    (``id_bloco`` e ``_source_url``).
    """

    async def extract(self, bloco_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai partidos de cada bloco informado.

        Args:
            bloco_ids: Lista de IDs dos blocos a consultar.

        Returns:
            pl.DataFrame: DataFrame com os dados brutos acrescidos de
                          ``id_bloco`` e ``_source_url``, ou vazio.
        """
        if not bloco_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for bid in bloco_ids:
            endpoint = f"{ApiRoutes.BLOCOS.value}/{bid}/partidos"
            url = self.build_source_url(endpoint)
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_bloco": int(bid), "_source_url": url})
            except Exception as e:
                logger.warning("Erro em partidos do bloco %s: %s", bid, e)

        if not rows:
            return pl.DataFrame()
        df = pl.DataFrame(rows, infer_schema_length=None)
        return df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])
