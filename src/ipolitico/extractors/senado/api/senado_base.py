"""Extrator base para a API de Dados Abertos do Senado Federal.

Gerencia a chamada única (sem paginação) e a normalização do formato
XML-heritage (objeto-único vs array, aninhamento de envelopes).
"""

import logging
from typing import Any

import polars as pl

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

    def _build_batch_dataframe(
        self,
        batches: list[tuple[str, list[dict[str, Any]], dict[str, Any] | None]],
    ) -> pl.DataFrame:
        """
        Constrói um único DataFrame para um lote de entidades, unificando o schema.

        Substitui o anti-padrão "DataFrame por entidade + ``pl.concat``", que
        falhava com ``SchemaError`` quando entidades do mesmo domínio tinham
        colunas (ou structs aninhadas) diferentes — ex: senador em exercício
        vs. histórico, veto com vs. sem ``Mensagem``. Um único DataFrame
        construído com ``infer_schema_length=None`` a partir da lista de
        registros unifica colunas e structs recursivamente, preenchendo com
        null os campos ausentes.

        Args:
            batches: Lista de tuplas ``(endpoint, records, params)``. Cada
                     registro recebe ``_source_url`` como primeira chave,
                     derivada de ``endpoint`` (e ``params``) via
                     ``build_source_url``.

        Returns:
            DataFrame único com todos os registros do lote (``_source_url``
            como primeira coluna), ou DataFrame vazio sem colunas se nenhum
            registro existir.
        """
        all_records: list[dict[str, Any]] = []
        for endpoint, records, params in batches:
            if not records:
                continue
            source_url = self.build_source_url(endpoint, params=params)
            for record in records:
                # _source_url como primeira chave preserva a convenção de
                # _inject_source_url ("primeira coluna do DataFrame").
                all_records.append({"_source_url": source_url, **record})

        if not all_records:
            return pl.DataFrame()

        return pl.DataFrame(all_records, infer_schema_length=None)

    async def extract(self, **kwargs: Any) -> Any:
        """Implementação abstrata de BaseExtractor — delega para fetch_flat."""
        return await self.fetch_flat(**kwargs)
