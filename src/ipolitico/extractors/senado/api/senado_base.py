"""Extrator base para a API de Dados Abertos do Senado Federal.

Gerencia a chamada única (sem paginação) e a normalização do formato
XML-heritage (objeto-único vs array, aninhamento de envelopes).
"""

import logging
from typing import Any

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class SenadoBaseExtractor(BaseExtractor):
    """
    Extrator base para a API do Senado.

    Diferente do ``CamaraBaseExtractor``:
    - **Sem paginação**: a API do Senado retorna arrays completos de uma vez
    - **XML-heritage**: os dados vêm num envelope aninhado (herança XML)
      que precisa ser aplainado via ``flatten_response()``
    - **Objeto-único vs array**: quando só 1 item, a API retorna objeto;
      ``_ensure_list()`` normaliza para lista
    """

    def __init__(self, client: SenadoClient):
        """
        Inicializa o extrator base.

        Args:
            client: Cliente HTTP configurado para a API do Senado.
        """
        self.client = client
        self.base_url = client.BASE_URL if client else ""

    async def fetch_flat(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        Executa chamada única (sem paginação) à API do Senado.

        Args:
            endpoint: Caminho relativo do recurso (ex: ``'senador/lista/atual'``).
            params: Parâmetros de query string (opcional).

        Returns:
            JSON decodificado retornado pela API.
        """
        return await self.client.fetch(endpoint, params=params)

    def flatten_response(self, data: dict[str, Any], data_path: list[str]) -> list[dict[str, Any]]:
        """
        Extrai o array de dados do envelope XML-heritage navegando pela ``data_path``.

        A API do Senado retorna JSON com estrutura aninhada herdada de XML.
        Exemplo para senadores::

            {"ListaParlamentarEmExercicio": {
                "Metadados": {...},
                "Parlamentares": {
                    "Parlamentar": [...]   ← data_path=["Parlamentares", "Parlamentar"]
                }
            }}

        Args:
            data: Dicionário completo retornado pela API.
            data_path: Lista de chaves a navegar sequencialmente
                       (ex: ``["Parlamentares", "Parlamentar"]``).

        Returns:
            Lista de registros encontrados no final da navegação,
            ou lista vazia se o path não existir.
        """
        current: Any = data
        for key in data_path:
            if not isinstance(current, dict) or key not in current:
                return []
            current = current[key]
        return self._ensure_list(current)

    def _ensure_list(self, item: Any) -> list[Any]:
        """
        Normaliza um item que pode ser objeto-único, lista ou None.

        A API do Senado, por herança XML, retorna um objeto quando há
        apenas 1 item e uma lista quando há 2+. Este método unifica ambos.

        Args:
            item: Valor a normalizar (dict, list, None).

        Returns:
            Lista de itens. None vira lista vazia.
        """
        if item is None:
            return []
        if isinstance(item, list):
            return item
        return [item]

    async def extract(self, **kwargs: Any) -> Any:
        """Implementação abstrata de BaseExtractor — delega para fetch_flat."""
        return await self.fetch_flat(**kwargs)
