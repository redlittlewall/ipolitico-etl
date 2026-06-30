"""Extrator para o domínio PROCESSOS (lista de matérias legislativas)."""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class SenadoProcessosExtractor(SenadoBaseExtractor):
    """Extrator de processos legislativos do Senado.

    Chama ``/processo`` que retorna um array flat (sem envelope XML).
    O endpoint não aceita filtro temporal — retorna todo o acervo (~10K registros).
    """

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """Extrai a lista completa de processos.

        Args:
            **kwargs: Parâmetros adicionais (start_date/end_date são aceitos
                      mas ignorados — a API não suporta filtro temporal).

        Returns:
            DataFrame com os dados brutos dos processos.
        """
        raw = await self.fetch_flat("processo")

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        return pl.DataFrame(raw, infer_schema_length=None)
