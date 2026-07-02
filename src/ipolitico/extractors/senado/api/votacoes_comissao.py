"""Extrator para o domínio VOTACOES_COMISSAO (votações em comissões do Senado)."""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class SenadoVotacoesComissaoExtractor(SenadoBaseExtractor):
    """Extrator de votações em comissões do Senado.

    Chama ``/votacaoComissao/comissao/{siglaComissao}`` com parâmetros opcionais
    ``dataInicio``/``dataFim`` para janela temporal. Aceita ``sigla_comissao``
    como parâmetro obrigatório.
    """

    async def extract(
        self,
        sigla_comissao: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai votações de uma comissão dentro de uma janela temporal.

        Args:
            sigla_comissao: Sigla da comissão (ex: "CAE", "CCJ"). Obrigatório.
            start_date: Data inicial no formato ``YYYY-MM-DD`` (opcional).
            end_date: Data final no formato ``YYYY-MM-DD`` (opcional).
            **kwargs: Parâmetros adicionais (aceita ``dataInicio``/``dataFim``
                      como fallback para compatibilidade com o orquestrador).

        Returns:
            DataFrame com os dados brutos das votações da comissão,
            ou DataFrame vazio se a API retornar resposta inválida.
        """
        sigla = sigla_comissao or kwargs.get("sigla_comissao")
        if not sigla:
            return pl.DataFrame()

        params: dict[str, str] = {}
        di = start_date or kwargs.get("dataInicio")
        df = end_date or kwargs.get("dataFim")
        if di:
            params["dataInicio"] = di
        if df:
            params["dataFim"] = df

        endpoint = f"votacaoComissao/comissao/{sigla}"
        raw = await self.fetch_flat(endpoint, params=params or None)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, endpoint, params=params or None)
