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
    e não em cada registro.

    Nota: O envelope varia por endpoint. ``_attach_codigo`` usa o caminho
    do envelope fornecido pela subclasse (``_codigo_envelope_path``) para
    extrair o código do senador.
    """

    _codigo_envelope_path: list[str] = ["MembroParlamentar", "IdentificacaoParlamentar"]

    @classmethod
    def _attach_codigo(
        cls,
        records: list[dict[str, Any]],
        raw: dict[str, Any],
        column_name: str,
    ) -> list[dict[str, Any]]:
        """Anexa o codigo do senador a cada registro filho.

        Procura o código no envelope seguindo o caminho definido por
        ``_codigo_envelope_path``, tentando os campos ``CodigoParlamentar``
        e ``Codigo`` (fallback para envelopes mais recentes da API).

        Args:
            records: Lista de registros extraídos do envelope aninhado.
            raw: Resposta bruta da API (contém identificação do senador).
            column_name: Nome da coluna a injetar nos registros
                         (ex: ``"CodigoParlamentar"``).

        Returns:
            Lista de registros com ``column_name`` injetado.
        """
        if not records or not isinstance(raw, dict):
            return records

        codigo = _deep_get(raw, cls._codigo_envelope_path + ["CodigoParlamentar"])
        if codigo is None:
            codigo = _deep_get(raw, cls._codigo_envelope_path + ["Codigo"])
        if codigo is not None:
            for record in records:
                record[column_name] = codigo
        return records


def _deep_get(d: dict[str, Any], path: list[str]) -> Any:
    """Navega por um dicionário seguindo o caminho de chaves."""
    current: Any = d
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


class SenadoMandatosExtractor(SenadoBaseExtractor, _SenadorChildMixin):
    """Extrator de mandatos parlamentares de um senador.

    Chama ``GET /senador/{codigo}/mandatos`` e achata o envelope XML-heritage
    para obter a lista de mandatos (legislaturas, partido, UF, período),
    injetando o ``CodigoParlamentar`` em cada registro.

    A resposta tem a estrutura::

        { "MandatoParlamentar": {
            "Parlamentar": {
                "Codigo": ...,
                "Mandatos": {
                    "Mandato": [...]   ← array alvo
                }
            }
        }}
    """

    _DATA_PATH_MANDATOS = ["MandatoParlamentar", "Parlamentar", "Mandatos", "Mandato"]
    _codigo_envelope_path = ["MandatoParlamentar", "Parlamentar"]

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

        # Normaliza Partidos.Partido: XML-heritage retorna struct (1 item) ou
        # list (2+). Garante que seja sempre lista para consistência.
        for record in records:
            partidos = record.get("Partidos")
            if isinstance(partidos, dict):
                partido = partidos.get("Partido")
                if isinstance(partido, dict):
                    partidos["Partido"] = [partido]

        return pl.DataFrame(records, infer_schema_length=None)


class SenadoFiliacoesExtractor(SenadoBaseExtractor, _SenadorChildMixin):
    """Extrator de filiações partidárias de um senador.

    Chama ``GET /senador/{codigo}/filiacoes`` e achata o envelope XML-heritage
    para obter a lista de filiações (partido, data filiação, data desfiliação),
    injetando o ``CodigoParlamentar`` em cada registro.

    A resposta tem a estrutura::

        { "FiliacaoParlamentar": {
            "Parlamentar": {
                "Codigo": ...,
                "Filiacoes": {
                    "Filiacao": [...]   ← array alvo
                }
            }
        }}

    Nota: Cada ``Filiacao`` contém um objeto ``Partido`` aninhado com
    ``SiglaPartido``, ``DataFiliacao`` e opcionalmente ``DataDesfiliacao``.
    O achatamento destes campos é feito no transformer.
    """

    _DATA_PATH_FILIACOES = ["FiliacaoParlamentar", "Parlamentar", "Filiacoes", "Filiacao"]
    _codigo_envelope_path = ["FiliacaoParlamentar", "Parlamentar"]

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
