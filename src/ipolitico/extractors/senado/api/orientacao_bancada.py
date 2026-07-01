"""Extrator para o domínio ORIENTACAO_BANCADA (orientação de bancada em votações do Senado).

Endpoint: ``GET /plenario/votacao/orientacaoBancada/{inicio}/{fim}``
Retorna um envelope ``{"votacoes": [...]}`` — o extrator desenvelopa e retorna
o array bruto de votações, cada uma com o campo ``orientacoesLideranca``
(explodido no transformer para 1 registro por (votação, partido)).
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class SenadoOrientacaoBancadaExtractor(SenadoBaseExtractor):
    """Extrator de orientação de bancada em votações do plenário do Senado.

    Chama ``GET /plenario/votacao/orientacaoBancada/{inicio}/{fim}``
    que retorna ``{"votacoes": [...]}``. O extrator desenvelopa a chave
    ``votacoes`` e retorna o array como DataFrame.

    Aceita datas no formato ``YYYY-MM-DD`` (ISO) e converte internamente
    para ``YYYYMMDD`` no path da URL (exigência da API do Senado).
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
            DataFrame com os dados brutos das votações (cada linha é uma
            votação, com o campo ``orientacoesLideranca`` como array de structs).
            Retorna DataFrame vazio se a API não retornar dados.
        """
        di = start_date or kwargs.get("dataInicio")
        df = end_date or kwargs.get("dataFim")
        if not di or not df:
            return pl.DataFrame()

        # API do Senado espera YYYYMMDD no path da URL (sem hífens)
        endpoint = f"plenario/votacao/orientacaoBancada/{di.replace('-', '')}/{df.replace('-', '')}"
        raw = await self.fetch_flat(endpoint)

        # A API retorna {"votacoes": [...]} — extrai o array
        if not isinstance(raw, dict):
            return pl.DataFrame()
        records = raw.get("votacoes", [])
        if not isinstance(records, list) or not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)
