"""Extratores para os domínios de orçamento do Senado.

Inclui:
- ``OrcamentoEmendasExtractor`` — lotes de emendas (``/orcamento/lista``)
- ``OrcamentoOficiosExtractor`` — ofícios orçamentários (``/orcamento/oficios``)
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)

# Caminho para navegar no envelope XML-heritage da API de emendas.
# A resposta tem a estrutura:
#   { "ListaLoteEmendas": {
#       "LotesEmendasOrcamento": {
#         "LoteEmendasOrcamento": [...]   ← array alvo
#     }}
_DATA_PATH_EMENDAS = [
    "ListaLoteEmendas",
    "LotesEmendasOrcamento",
    "LoteEmendasOrcamento",
]


class OrcamentoEmendasExtractor(SenadoBaseExtractor):
    """Extrator de lotes de emendas ao orçamento.

    Chama ``/orcamento/lista?ano=YYYY`` e aplaina o envelope XML-heritage
    para obter o array de lotes de emendas. 1 job por ano.
    """

    async def extract(self, ano: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai lotes de emendas de um ano específico.

        Args:
            ano: Ano para filtrar (ex: 2025). Se omitido, usa o parâmetro
                 ``start_date`` extraído do kwargs (compatibilidade com
                 orquestrador que passa janela temporal).
            **kwargs: Parâmetros adicionais (aceita ``start_date``/``end_date``
                      como fallback, mas o endpoint só suporta filtro por ano).

        Returns:
            DataFrame com os dados brutos dos lotes de emendas.
            Retorna DataFrame vazio se a API não retornar dados.
        """
        if ano is None:
            sd = kwargs.get("start_date")
            ano = int(sd.split("-")[0]) if sd else None

        params = {"ano": str(ano)} if ano else None
        raw = await self.fetch_flat("orcamento/lista", params=params)
        records = self.flatten_response(raw, _DATA_PATH_EMENDAS)

        if not records:
            return pl.DataFrame()

        df = pl.DataFrame(records, infer_schema_length=None)
        return self._inject_source_url(df, "orcamento/lista", params=params)


class OrcamentoOficiosExtractor(SenadoBaseExtractor):
    """Extrator de ofícios orçamentários.

    Chama ``/orcamento/oficios?ano=YYYY`` que retorna um array flat
    (sem envelope XML-heritage). 1 job por ano.
    """

    async def extract(self, ano: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai ofícios orçamentários de um ano específico.

        Args:
            ano: Ano para filtrar (ex: 2024). Se omitido, usa o parâmetro
                 ``start_date`` extraído do kwargs (compatibilidade com
                 orquestrador que passa janela temporal).
            **kwargs: Parâmetros adicionais (aceita ``start_date``/``end_date``
                      como fallback, mas o endpoint só suporta filtro por ano).

        Returns:
            DataFrame com os dados brutos dos ofícios, incluindo o campo
            ``emendas`` (lista de dicts) que precisa ser serializado pelo
            transformer. Retorna DataFrame vazio se a API não retornar dados.
        """
        if ano is None:
            sd = kwargs.get("start_date")
            ano = int(sd.split("-")[0]) if sd else None

        params = {"ano": str(ano)} if ano else None
        raw = await self.fetch_flat("orcamento/oficios", params=params)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, "orcamento/oficios", params=params)
