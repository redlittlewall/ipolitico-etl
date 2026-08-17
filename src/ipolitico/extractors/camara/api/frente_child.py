"""Rota filha de /frentes/{id}/membros."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class FrenteMembrosExtractor(CamaraBaseExtractor):
    """Extrator de /frentes/{id}/membros.

    Coleta os membros de cada frente e adiciona colunas de auditoria
    (``id_frente`` e ``_source_url``).
    """

    async def extract(self, frente_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai membros de cada frente informada.

        Args:
            frente_ids: Lista de IDs das frentes a consultar.

        Returns:
            pl.DataFrame: DataFrame com os dados brutos acrescidos de
                          ``id_frente`` e ``_source_url``, ou vazio.
        """
        if not frente_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for fid in frente_ids:
            endpoint = f"{ApiRoutes.FRENTES.value}/{fid}/membros"
            url = self.build_source_url(endpoint)
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_frente": int(fid), "_source_url": url})
            except Exception as e:
                logger.warning("Erro em membros da frente %s: %s", fid, e)

        if not rows:
            return pl.DataFrame()
        df = pl.DataFrame(rows, infer_schema_length=None)
        return df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])
