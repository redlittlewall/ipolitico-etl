"""Cliente HTTP resiliente para a API de Dados Abertos do Senado Federal.

Segue o mesmo padrão do CamaraClient (semáforo, retry, headers),
mas sem telemetria SQLite, warmup, ou DNS pre-resolution.
A API do Senado não exige autenticação e retorna JSON com sufixo ``.json``.
"""

import asyncio
import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ipolitico.core.config import SENADO_API_BASE_URL, SENADO_HTTP_CONCURRENCY

logger = logging.getLogger(__name__)


class SenadoAPIError(Exception):
    """Exceção base para falhas na API do Senado."""

    pass


def _is_transient_error(exception: BaseException) -> bool:
    """Retorna True se o erro for transitório (deve tentar novamente)."""
    if isinstance(exception, httpx.TimeoutException):
        return True
    if isinstance(exception, httpx.NetworkError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, SenadoAPIError):
        return True
    return False


class SenadoClient:
    """
    Cliente HTTP assíncrono para a API de Dados Abertos do Senado.

    Características:
    - Semáforo de concorrência próprio (``SENADO_HTTP_CONCURRENCY``, padrão 5)
    - Retry com exponential backoff via tenacity para erros transitórios
    - Falsos 404 retornam lista vazia (mesmo comportamento do CamaraClient)
    - Endpoints são chamados com sufixo ``.json`` automaticamente
    """

    BASE_URL = SENADO_API_BASE_URL

    def __init__(self, max_retries: int = 5):
        """
        Inicializa o cliente HTTP do Senado.

        Args:
            max_retries: Número máximo de tentativas por requisição (padrão 5).
        """
        self.max_retries = max_retries
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "iPolitico-ETL-OpenSource/1.0",
        }
        self._semaphore = asyncio.Semaphore(SENADO_HTTP_CONCURRENCY)

    async def fetch(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        Executa requisição GET à API do Senado com retry e backoff.

        Aplica retry via tenacity para erros transitórios (timeout, rede,
        HTTP 429/5xx). HTTP 404 é tratado como lista vazia sem retry.

        Args:
            endpoint: Caminho relativo do recurso (ex: ``'senador/lista/atual'``).
                      O sufixo ``.json`` é adicionado automaticamente.
            params: Parâmetros de query string (opcional).

        Returns:
            JSON decodificado retornado pela API. Retorna lista vazia em 404.

        Raises:
            SenadoAPIError: Se esgotar as tentativas de conexão.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}.json"

        return await self._fetch_with_retry(url, params)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_transient_error),
        reraise=True,
    )
    async def _fetch_with_retry(self, url: str, params: dict[str, Any] | None) -> Any:
        """Método interno que carrega o decorator @retry (separado do fetch público)."""
        async with self._semaphore:
            async with httpx.AsyncClient(
                timeout=30.0, headers=self.headers, follow_redirects=True
            ) as client:
                try:
                    response = await client.get(url, params=params)
                except httpx.RequestError as e:
                    raise SenadoAPIError(f"Falha de rede ao acessar {url}: {e}") from e

                # 404: recurso sem dados → lista vazia (sem retry)
                if response.status_code == 404:
                    logger.debug("Recurso inexistente (404) em %s. Assumindo lista vazia.", url)
                    return []

                # 200 → sucesso
                if response.status_code == 200:
                    return response.json()

                # 429/5xx: raise SenadoAPIError para o @retry tentar novamente
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Erro transitório (%d) em %s. Retry via tenacity.",
                        response.status_code,
                        url,
                    )
                    raise SenadoAPIError(f"Erro transitório HTTP {response.status_code} em {url}")

                # Demais erros HTTP: fatal, não tenta novamente
                raise SenadoAPIError(
                    f"Erro HTTP {response.status_code} em {url}: {response.text[:200]}"
                )
