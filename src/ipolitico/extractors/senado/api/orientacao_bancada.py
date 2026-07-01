"""Extrator para o domínio ORIENTACAO_BANCADA (orientação de bancada em votações do Senado).

Endpoint: ``GET /plenario/votacao/orientacaoBancada/{inicio}/{fim}``
Retorna como cada líder partidário orientou sua bancada em cada votação nominal.
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class SenadoOrientacaoBancadaExtractor(SenadoBaseExtractor):
    """Extrator de orientação de bancada em votações do plenário do Senado.

    Chama ``GET /plenario/votacao/orientacaoBancada/{inicio}/{fim}``
    que retorna um array flat. Aceita datas no formato ``YYYY-MM-DD`` (ISO)
    e converte internamente para ``YYYYMMDD`` no path da URL (exigência
    da API do Senado).
    """

    async def extract(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai orientações de bancada dentro de uma janela temporal.

        Args:
            start_date: Data inicial no formato ``YYYY-MM-DD``.
            end_date: Data final no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (aceita ``dataInicio``/``dataFim``
                      como fallback para compatibilidade).

        Returns:
            DataFrame com os dados brutos das orientações.
            Retorna DataFrame vazio se a API não retornar dados.
        """
        di = start_date or kwargs.get("dataInicio")
        df = end_date or kwargs.get("dataFim")
        if not di or not df:
            return pl.DataFrame()

        # API do Senado espera YYYYMMDD no path da URL (sem hífens)
        endpoint = f"plenario/votacao/orientacaoBancada/{di.replace('-', '')}/{df.replace('-', '')}"
        raw = await self.fetch_flat(endpoint)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        return pl.DataFrame(raw, infer_schema_length=None)
