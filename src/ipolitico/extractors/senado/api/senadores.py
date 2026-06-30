"""Extrator para o domínio SENADORES (lista por legislatura)."""

import logging
from typing import Any, Optional

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)

# Caminho para navegar no envelope XML-heritage da API.
# A resposta tem a estrutura:
#   { "ListaParlamentarLegislatura": {
#       "Parlamentares": {
#         "Parlamentar": [...]   ← array alvo
#     }}
_DATA_PATH = [
    "ListaParlamentarLegislatura",
    "Parlamentares",
    "Parlamentar",
]


class SenadoSenadoresExtractor(SenadoBaseExtractor):
    """Extrator da lista de senadores por legislatura.

    Chama ``/senador/lista/legislatura/{legislatura_id}`` e achata o
    envelope XML-heritage para obter o array de parlamentares.
    """

    async def extract(
        self,
        legislatura_id: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai senadores de uma legislatura específica.

        Args:
            legislatura_id: Número da legislatura (ex: 57). Se omitido,
                            usa a legislatura atual via endpoint ``/atual``.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos dos senadores, incluindo os
            dicionários aninhados ``IdentificacaoParlamentar`` e
            ``Mandatos``. Retorna DataFrame vazio se a API não retornar dados.
        """
        if legislatura_id is None:
            endpoint = "senador/lista/atual"
            data_path = ["ListaParlamentarEmExercicio", "Parlamentares", "Parlamentar"]
        else:
            endpoint = f"senador/lista/legislatura/{legislatura_id}"
            data_path = _DATA_PATH

        raw = await self.fetch_flat(endpoint)
        records = self.flatten_response(raw, data_path)

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)
