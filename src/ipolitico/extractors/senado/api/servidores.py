"""Extrator para o domínio SERVIDORES (roster do Senado, API adm-dadosabertos).

Chama ``GET /servidores/servidores`` uma única vez — a API **não pagina**: o
parâmetro ``pagina`` é ignorado e os ~22,9 mil registros (~10 MB) vêm de uma
só resposta em lista top-level. Diferente dos extratores da API legis (herança
XML com envelope), aqui não há envelope a aplainar: a lista é o payload.
"""

import logging
from typing import Any

import polars as pl

from ipolitico.core.senado_adm_client import SenadoAdmClient
from ipolitico.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

# Rota da coleção: o ``_source_url`` aponta para ela (não há página para apontar).
_ROSTER_ENDPOINT = "servidores/servidores"


class SenadoServidoresExtractor(BaseExtractor):
    """Extrator do roster de servidores do Senado.

    Executa uma única requisição à coleção ``/servidores/servidores`` e devolve
    o payload JSON como veio (lista top-level), com os aninhamentos
    ``lotacao``/``categoria``/``cedido`` preservados — o achatamento é
    responsabilidade do transformer, não do extrator (SRP).
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
        Extrai o roster completo de servidores (coleção, sem paginação).

        Args:
            **kwargs: Parâmetros adicionais (ignorados — nenhum filtro ou janela
                é aplicado; a API devolve o snapshot completo de uma vez).

        Returns:
            DataFrame com os registros brutos (aninhamentos preservados) e
            ``_source_url`` apontando para a URL da coleção. DataFrame vazio se
            a API responder 404 (ausência) ou lista vazia.
        """
        raw = await self.client.fetch(_ROSTER_ENDPOINT)

        if not raw:
            logger.debug("Roster de servidores vazio/ausente (404). Assumindo lista vazia.")
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, _ROSTER_ENDPOINT)
