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


class _SenadorChildMixin:
    """Mixin para extratores que iteram sobre filhos de um senador.

    Injeta o ``CodigoParlamentar`` do senador em cada registro filho, pois
    a API do Senado retorna a identificação do senador no envelope externo
    (``MembroParlamentar.IdentificacaoParlamentar``) e não em cada registro.
    """

    @staticmethod
    def _attach_codigo(
        records: list[dict[str, Any]], raw: dict[str, Any], api_name: str
    ) -> list[dict[str, Any]]:
        """Anexa o codigo do senador a cada registro filho.

        Args:
            records: Lista de registros extraídos do envelope aninhado.
            raw: Resposta bruta da API (contém IdentificacaoParlamentar).
            api_name: Nome do campo no envelope externo (ex: ``"CodigoParlamentar"``).

        Returns:
            Lista de registros com ``CodigoParlamentar`` injetado.
        """
        if not records or not isinstance(raw, dict):
            return records

        identificacao = raw.get("MembroParlamentar", {}).get("IdentificacaoParlamentar", {})
        codigo = identificacao.get(api_name)
        if codigo is not None:
            for record in records:
                record[api_name] = codigo
        return records


class SenadoMandatosExtractor(SenadoBaseExtractor, _SenadorChildMixin):
    """Extrator de mandatos parlamentares de um senador.

    Chama ``GET /senador/{codigo}/mandatos`` e achata o envelope XML-heritage
    para obter a lista de mandatos (legislaturas, partido, UF, período),
    injetando o ``CodigoParlamentar`` em cada registro.

    A resposta tem a estrutura::

        { "MembroParlamentar": {
            "IdentificacaoParlamentar": { ... },
            "Mandatos": {
                "Mandato": [...]   ← array alvo
            }
        }}
    """

    _DATA_PATH_MANDATOS = ["MembroParlamentar", "Mandatos", "Mandato"]

    async def extract(
        self,
        codigo: int | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai o histórico completo de mandatos de um senador.

        Args:
            codigo: Código do senador. Se omitido, retorna DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos dos mandatos, incluindo
            ``CodigoParlamentar`` injetado, ou DataFrame vazio se o código
            não for informado ou a API não retornar dados.
        """
        if codigo is None:
            return pl.DataFrame()

        raw = await self.fetch_flat(f"senador/{codigo}/mandatos")
        records = self.flatten_response(raw, self._DATA_PATH_MANDATOS)
        records = self._attach_codigo(records, raw, "CodigoParlamentar")

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)


class SenadoFiliacoesExtractor(SenadoBaseExtractor, _SenadorChildMixin):
    """Extrator de filiações partidárias de um senador.

    Chama ``GET /senador/{codigo}/filiacoes`` e achata o envelope XML-heritage
    para obter a lista de filiações (partido, data filiação, data desfiliação),
    injetando o ``CodigoParlamentar`` em cada registro.

    A resposta tem a estrutura::

        { "MembroParlamentar": {
            "IdentificacaoParlamentar": { ... },
            "Filiacoes": {
                "Filiacao": [...]   ← array alvo
            }
        }}
    """

    _DATA_PATH_FILIACOES = ["MembroParlamentar", "Filiacoes", "Filiacao"]

    async def extract(
        self,
        codigo: int | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai o histórico completo de filiações partidárias de um senador.

        Args:
            codigo: Código do senador. Se omitido, retorna DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos das filiações, incluindo
            ``CodigoParlamentar`` injetado, ou DataFrame vazio se o código
            não for informado ou a API não retornar dados.
        """
        if codigo is None:
            return pl.DataFrame()

        raw = await self.fetch_flat(f"senador/{codigo}/filiacoes")
        records = self.flatten_response(raw, self._DATA_PATH_FILIACOES)
        records = self._attach_codigo(records, raw, "CodigoParlamentar")

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)
