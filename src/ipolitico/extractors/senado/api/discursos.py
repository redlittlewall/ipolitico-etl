"""Extratores para os domínios de discursos e notas taquigráficas do Senado.

Inclui:
- ``DiscursosPlenarioExtractor`` — lista de discursos em plenário por período
- ``DiscursosSenadorExtractor`` — discursos de um senador específico (XML-heritage)
- ``DiscursosTextoExtractor`` — texto integral de um discurso
- ``NotasTaquigrafiaSessaoExtractor`` — notas taquigráficas de uma sessão
- ``NotasTaquigrafiaReuniaoExtractor`` — notas taquigráficas de uma reunião de comissão

Nota: ``DiscursosPlenarioExtractor`` aceita datas ``YYYY-MM-DD`` (ISO) como
entrada e converte internamente para ``YYYYMMDD`` no path da URL (exigência
da API do Senado). Os demais extratores usam query params e aceitam
``YYYY-MM-DD``.
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)

# Caminho para navegar no envelope XML-heritage de discursos por senador.
# A resposta tem a estrutura:
#   { "Parlamentar": {
#       "IdentificacaoParlamentar": { ... },
#       "Pronunciamentos": {
#         "Pronunciamento": [...]   ← array alvo
#     }}
_DATA_PATH_SENADOR = [
    "Parlamentar",
    "Pronunciamentos",
    "Pronunciamento",
]


class DiscursosPlenarioExtractor(SenadoBaseExtractor):
    """Extrator da lista de discursos em plenário por período.

    Chama ``GET /plenario/lista/discursos/{inicio}/{fim}`` que retorna
    um array flat (sem envelope XML). 1 job por janela mensal.

    Nota: Aceita datas no formato ``YYYY-MM-DD`` (ISO) e converte
    internamente para ``YYYYMMDD`` no path da URL (exigência da API
    do Senado).
    """

    async def extract(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai discursos em plenário dentro de uma janela temporal.

        Args:
            start_date: Data inicial no formato ``YYYY-MM-DD``.
            end_date: Data final no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (aceita ``dataInicio``/``dataFim``
                      como fallback para compatibilidade).

        Returns:
            DataFrame com os dados brutos dos discursos.
            Retorna DataFrame vazio se a API não retornar dados.
        """
        di = start_date or kwargs.get("dataInicio")
        df = end_date or kwargs.get("dataFim")
        if not di or not df:
            return pl.DataFrame()

        # API do Senado espera YYYYMMDD no path da URL (sem hífens)
        endpoint = f"plenario/lista/discursos/{di.replace('-', '')}/{df.replace('-', '')}"
        raw = await self.fetch_flat(endpoint)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        return pl.DataFrame(raw, infer_schema_length=None)


class DiscursosSenadorExtractor(SenadoBaseExtractor):
    """Extrator de discursos de um senador específico com janela temporal.

    Chama ``GET /senador/{codigo}/discursos`` com parâmetros opcionais
    ``dataInicio``/``dataFim`` e aplaina o envelope XML-heritage
    ``Parlamentar.Pronunciamentos.Pronunciamento``.
    """

    async def extract(
        self,
        codigo: int | None = None,
        dataInicio: str | None = None,
        dataFim: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai discursos de um senador em uma janela temporal.

        Args:
            codigo: Código do senador. Se omitido, retorna DataFrame vazio.
            dataInicio: Data inicial no formato ``YYYY-MM-DD``.
            dataFim: Data final no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com dados achatados dos discursos (sem envelopes XML).
            Retorna DataFrame vazio se o código não for informado ou a API
            não retornar dados.
        """
        if codigo is None:
            return pl.DataFrame()

        params: dict[str, str] = {}
        if dataInicio:
            params["dataInicio"] = dataInicio
        if dataFim:
            params["dataFim"] = dataFim

        raw = await self.fetch_flat(f"senador/{codigo}/discursos", params=params or None)
        records = self.flatten_response(raw, _DATA_PATH_SENADOR)

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)


class DiscursosTextoExtractor(SenadoBaseExtractor):
    """Extrator de texto integral de um discurso.

    Chama ``GET /discurso/texto-integral/{codigo}`` para cada código de
    discurso e retorna o texto integral. Usa o pattern de ``entity_ids``
    (igual ``SenadoSenadoresDetalheExtractor``).
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai texto integral de um ou mais discursos.

        Args:
            entity_ids: Lista de códigos de discurso. Se vazio, retorna
                        DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos do texto integral (dict flat).
        """
        if not entity_ids:
            return pl.DataFrame()

        all_records: list[dict[str, Any]] = []
        for codigo in entity_ids:
            raw = await self.fetch_flat(f"discurso/texto-integral/{codigo}")
            if isinstance(raw, dict):
                all_records.append(raw)

        if not all_records:
            return pl.DataFrame()

        return pl.DataFrame(all_records, infer_schema_length=None)


class NotasTaquigrafiaSessaoExtractor(SenadoBaseExtractor):
    """Extrator de notas taquigráficas de uma sessão do plenário.

    Chama ``GET /taquigrafia/notas/sessao/{idSessao}`` para cada ID de
    sessão. Usa o pattern de ``entity_ids``.
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai notas taquigráficas de uma ou mais sessões.

        Args:
            entity_ids: Lista de IDs de sessão. Se vazio, retorna
                        DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos das notas (dict flat).
        """
        if not entity_ids:
            return pl.DataFrame()

        all_records: list[dict[str, Any]] = []
        for sessao_id in entity_ids:
            raw = await self.fetch_flat(f"taquigrafia/notas/sessao/{sessao_id}")
            if isinstance(raw, dict):
                all_records.append(raw)

        if not all_records:
            return pl.DataFrame()

        return pl.DataFrame(all_records, infer_schema_length=None)


class NotasTaquigrafiaReuniaoExtractor(SenadoBaseExtractor):
    """Extrator de notas taquigráficas de uma reunião de comissão.

    Chama ``GET /taquigrafia/notas/reuniao/{idReuniao}`` para cada ID de
    reunião. Usa o pattern de ``entity_ids``.
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai notas taquigráficas de uma ou mais reuniões de comissão.

        Args:
            entity_ids: Lista de IDs de reunião. Se vazio, retorna
                        DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos das notas (dict flat).
        """
        if not entity_ids:
            return pl.DataFrame()

        all_records: list[dict[str, Any]] = []
        for reuniao_id in entity_ids:
            raw = await self.fetch_flat(f"taquigrafia/notas/reuniao/{reuniao_id}")
            if isinstance(raw, dict):
                all_records.append(raw)

        if not all_records:
            return pl.DataFrame()

        return pl.DataFrame(all_records, infer_schema_length=None)
