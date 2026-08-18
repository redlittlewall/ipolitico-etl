"""Extrator para o domínio DESPESAS_CEAPS (Senado, API adm-dadosabertos).

Chama ``GET /senadores/despesas_ceaps/{ano}`` — 1 chamada por ano, sem
paginação (a API devolve a lista top-level completa do ano: 2.449–26.055
registros). O path é **anual** (``{ano}``), mas o payload carrega ``mes`` →
granularidade efetiva mês via 1 request por ano. ``valorReembolsado`` vem como
número (API real) ou string BR — a conversão é responsabilidade do transformer,
não do extrator (SRP).
"""

import logging
from typing import Any

import polars as pl

from ipolitico.core.senado_adm_client import SenadoAdmClient
from ipolitico.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

# Rota base da coleção anual — o ano é interpolado por chamada e o
# ``_source_url`` aponta para a URL completa (replayável até o arquivo anual).
_ANNUAL_ENDPOINT = "senadores/despesas_ceaps"


class SenadoDespesasCeapsExtractor(BaseExtractor):
    """Extrator de despesas CEAP do Senado (1 chamada por ano).

    Executa uma requisição a ``/senadores/despesas_ceaps/{ano}`` e devolve o
    payload JSON como veio (lista top-level de 13 campos), com ``_source_url``
    apontando para a URL anual. Tanto o 404 (ano pré-série, ex: 2007) quanto o
    200-com-lista-vazia viram DataFrame vazio — ausência, não erro; a cobertura
    (início 2008) fica registrada no registry de cobertura (``COVERAGE_GAPS``).
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

    async def extract(self, ano: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai as despesas CEAP de um ano.

        Args:
            ano: Ano das despesas (ex: 2025). O planner anual
                (``AnnualWindowStrategy``) passa 1 job por ano.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os registros brutos do ano e ``_source_url`` apontando
            para a URL ``.../senadores/despesas_ceaps/{ano}``. DataFrame vazio
            se a API responder 404 (ano pré-série) ou 200 com lista vazia.

        Raises:
            ValueError: Se ``ano`` estiver ausente (domínio anual exige o ano).
        """
        if ano is None:
            raise ValueError(f"Despesas CEAP exigem 'ano' (recebidos: ano={ano}).")

        endpoint = f"{_ANNUAL_ENDPOINT}/{ano}"
        raw = await self.client.fetch(endpoint)

        if not raw:
            logger.debug(
                "Despesas CEAP %s vazio/ausente (404 ou ano sem registros). Assumindo lista vazia.",
                ano,
            )
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, endpoint)
