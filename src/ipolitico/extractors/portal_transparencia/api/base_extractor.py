"""Base dos extratores da API v3 do Portal da Transparência (CGU).

Espelha o papel do ``CamaraBaseExtractor``: uma ponte entre o motor assíncrono
genérico (``BaseExtractor``) e as particularidades da API v3 do portal —
autenticação por chave do usuário (``chave-api-dados``), resposta como lista
top-level (sem envelope) e paginação por ``pagina`` com page_size fixo em 15
(a API ignora tentativas de ``itens``/``limit``/``paginaTamanho`` — verificado
na validação real do ticket 02). Sem estado e sem regras de negócio (SRP:
extratores só fazem I/O).
"""

from __future__ import annotations

import logging
from typing import Any

from ipolitico.core.portal_transparencia_client import PortalTransparenciaClient
from ipolitico.extractors.base import SOURCE_PAGE_COL, BaseExtractor

logger = logging.getLogger(__name__)


class PortalTransparenciaBaseExtractor(BaseExtractor):
    """
    Base dos extratores da API v3 do Portal da Transparência (CGU).

    Fornece a paginação comum (``fetch_paginated``), marcando em cada registro a
    página de origem (``_source_page``) para a URL de auditoria ser replayável
    até o registro — mesmo contrato do ``CamaraBaseExtractor`` (issue 01).
    """

    def __init__(self, client: PortalTransparenciaClient):
        """
        Inicializa o extrator base da API v3 do portal.

        Args:
            client: Cliente HTTP já configurado com a chave do usuário
                (``PortalTransparenciaClient``).
        """
        self.client = client
        self.base_url = client.BASE_URL

    async def fetch_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Percorre todas as páginas de um recurso paginado da API v3.

        A API v3 não expõe page size configurável (fixo em 15; parâmetros como
        ``itens``/``limit``/``paginaTamanho`` são ignorados silenciosamente). O
        tamanho da primeira página define o limite de parada: a iteração termina
        quando uma página vem vazia ou mais curta que a anterior (página final).
        Cada registro carrega ``_source_page`` com o número da página de origem.

        Args:
            endpoint: Caminho relativo do recurso (ex:
                ``'api-de-dados/orgaos-siape'``).
            params: Parâmetros de filtro adicionais (opcional; ``pagina`` é
                gerenciado pelo próprio loop).

        Returns:
            Lista com todos os registros acumulados, cada um com a chave
            reservada ``_source_page``. Lista vazia se a API não tiver dados.
        """
        all_data: list[dict[str, Any]] = []
        page = 1
        page_size: int | None = None

        while True:
            page_params = dict(params or {})
            page_params["pagina"] = page
            data = await self.client.fetch(endpoint, params=page_params)

            if not data:
                break

            if page_size is None:
                page_size = len(data)

            for item in data:
                if isinstance(item, dict):
                    item[SOURCE_PAGE_COL] = page

            all_data.extend(data)

            if len(data) < page_size:
                break

            page += 1

        return all_data
