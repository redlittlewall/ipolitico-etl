"""Extrator para o domínio REMUNERACOES (folha do Senado, API adm-dadosabertos).

Chama ``GET /servidores/remuneracoes/{ano}/{mes}`` — 1 chamada por (ano, mês),
sem paginação (a API devolve a lista top-level completa de ~10,7 mil registros
em 2026-07). Valores monetários vêm como string BR (``"1.234,56"``) — a
conversão é responsabilidade do transformer, não do extrator (SRP).

Regra dupla de cobertura (survey 05):
- **404** (ex: 2012-12, mês anterior ao início da série) → ausência permanente,
  lista vazia (não exceção) — o ``SenadoAdmClient`` já devolve ``[]``.
- **HTTP 200 com lista vazia** (``[\n\n]``) = mês corrente ainda não publicado →
  ausência temporária, também lista vazia. Não confundir com 404.
"""

import logging
from typing import Any

import polars as pl

from ipolitico.core.senado_adm_client import SenadoAdmClient
from ipolitico.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

# Rota base da coleção mensal — o ano/mês é interpolado por chamada e o
# ``_source_url`` aponta para a URL completa (replayável até o arquivo mensal).
_MONTHLY_ENDPOINT = "servidores/remuneracoes"


class SenadoRemuneracoesExtractor(BaseExtractor):
    """Extrator da folha de remuneração do Senado (1 chamada por ano/mês).

    Executa uma requisição a ``/servidores/remuneracoes/{ano}/{mes}`` e devolve
    o payload JSON como veio (lista top-level de 20 campos), com ``_source_url``
    apontando para a URL mensal. Tanto o 404 (mês pré-série) quanto o
    200-com-lista-vazia (mês corrente ainda não publicado) viram DataFrame vazio
    — ausência, não erro; a distinção permanente/temporária fica registrada no
    registry de cobertura (``COVERAGE_GAPS``), não em exceção.
    """

    def __init__(self, client: SenadoAdmClient):
        """
        Inicializa o extrator com o cliente da API adm-dadosabertos.

        Args:
            client: Cliente HTTP resiliente (``SenadoAdmClient``) que expõe
                ``BASE_URL`` — base usada para montar o ``_source_url``.
        """
        self.client = client
        self.base_url = client.BASE_URL if client else ""

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai a folha de remuneração de um (ano, mês).

        Args:
            **kwargs: Deve conter ``year`` (int) e ``month`` (int) — o planner
                mensal (``MonthlyBulkStrategy``) passa um job por (ano, mês).

        Returns:
            DataFrame com os registros brutos do mês e ``_source_url`` apontando
            para a URL ``.../servidores/remuneracoes/{ano}/{mes}``. DataFrame
            vazio se a API responder 404 (mês pré-série) ou 200 com lista vazia
            (mês corrente ainda não publicado).

        Raises:
            ValueError: Se ``year`` ou ``month`` estiverem ausentes (domínio
                mensal exige os dois).
        """
        year = kwargs.get("year")
        month = kwargs.get("month")
        if year is None or month is None:
            raise ValueError(
                f"Remunerações exigem 'year' e 'month' (recebidos: year={year}, month={month})."
            )

        endpoint = f"{_MONTHLY_ENDPOINT}/{year}/{month}"
        raw = await self.client.fetch(endpoint)

        if not raw:
            logger.debug(
                "Remunerações %s/%s vazio/ausente (404 ou mês não publicado). "
                "Assumindo lista vazia.",
                year,
                month,
            )
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, endpoint)
