"""Extratores para os domínios de vetos presidenciais do Senado.

Inclui:
- ``VetosPresidenciaisExtractor`` — lista de vetos por ano (``/materia/vetos/{ano}``)
- ``VetosDetalheExtractor`` — detalhes de um veto específico (``/plenario/resultado/veto/{codigo}``)
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)

# Caminho para navegar no envelope XML-heritage da API de veto.
# A resposta tem a estrutura:
#   { "MateriaVetos": {
#       "Vetos": {
#         "Veto": [...]   ← array alvo
#     }}
_DATA_PATH_PRESIDENCIAIS = [
    "MateriaVetos",
    "Vetos",
    "Veto",
]

# Caminho para navegar no envelope XML-heritage da API de detalhe do veto.
# A resposta tem a estrutura:
#   { "PlenarioVeto": {
#       "Veto": { ... }   ← objeto alvo (normalizado para lista)
#     }}
_DATA_PATH_DETALHE = [
    "PlenarioVeto",
    "Veto",
]


class VetosPresidenciaisExtractor(SenadoBaseExtractor):
    """Extrator da lista de vetos presidenciais por ano.

    Chama ``/materia/vetos/{ano}`` e aplaina o envelope XML-heritage
    para obter o array de vetos. 1 job por ano.
    """

    async def extract(self, ano: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai vetos presidenciais de um ano específico.

        Args:
            ano: Ano para filtrar (ex: 2020). Se omitido, usa o parâmetro
                 ``start_date`` extraído do kwargs (compatibilidade com
                 orquestrador que passa janela temporal).
            **kwargs: Parâmetros adicionais (aceita ``start_date``/``end_date``
                      como fallback).

        Returns:
            DataFrame com os dados brutos dos vetos do ano.
            Retorna DataFrame vazio se a API não retornar dados.
        """
        if ano is None:
            sd = kwargs.get("start_date")
            ano = int(sd.split("-")[0]) if sd else None

        endpoint = f"materia/vetos/{ano}" if ano else "materia/vetos/1995"
        raw = await self.fetch_flat(endpoint)
        records = self.flatten_response(raw, _DATA_PATH_PRESIDENCIAIS)

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)


class VetosDetalheExtractor(SenadoBaseExtractor):
    """Extrator de detalhes de um ou mais vetos presidenciais.

    Chama ``/plenario/resultado/veto/{codigo}`` para cada código e
    aplaina o envelope XML-heritage. Usa o pattern de ``entity_ids``
    (igual ``SenadoSenadoresDetalheExtractor``).
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai detalhes de um ou mais vetos.

        Args:
            entity_ids: Lista de códigos de veto. Se omitido ou vazio,
                        retorna DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos do(s) veto(s), incluindo os
            campos flat retornados pela API do plenário.
        """
        if not entity_ids:
            return pl.DataFrame()

        all_records: list[dict[str, Any]] = []
        for codigo in entity_ids:
            raw = await self.fetch_flat(f"plenario/resultado/veto/{codigo}")
            records = self.flatten_response(raw, _DATA_PATH_DETALHE)
            all_records.extend(records)

        if not all_records:
            return pl.DataFrame()

        return pl.DataFrame(all_records, infer_schema_length=None)
