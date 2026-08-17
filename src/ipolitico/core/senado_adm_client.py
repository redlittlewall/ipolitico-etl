"""Cliente HTTP resiliente para a API administrativa do Senado (adm-dadosabertos).

Segue o padrão do SenadoClient (semáforo, retry, headers), mas para a base
``adm.senado.gov.br/adm-dadosabertos`` — sem autenticação e sem sufixo
``.json`` nas rotas. É a fonte de dados das fatias 07-09 (SERVIDORES,
REMUNERACOES, DESPESAS_CEAPS).

Diferente do SenadoClient, este cliente é **agnóstico de shape**: devolve o
JSON como veio (lista top-level ou envelope ``{statusCode, msg, data}``). A
normalização de envelope é responsabilidade do extrator/transformer do domínio,
não do cliente HTTP.
"""

import asyncio
import logging
import ssl
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ipolitico.core.config import SENADO_ADM_API_BASE_URL, SENADO_ADM_HTTP_CONCURRENCY

logger = logging.getLogger(__name__)


class SenadoAdmAPIError(Exception):
    """Exceção base para falhas na API adm-dadosabertos do Senado."""

    pass


def _is_transient_error(exception: BaseException) -> bool:
    """Retorna True se o erro for transitório (deve tentar novamente)."""
    if isinstance(exception, ssl.SSLError):
        return True
    if isinstance(exception, httpx.TimeoutException):
        return True
    if isinstance(exception, httpx.NetworkError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, SenadoAdmAPIError):
        return True
    return False


class SenadoAdmClient:
    """
    Cliente HTTP assíncrono para a API adm-dadosabertos do Senado.

    Características:
    - Semáforo de concorrência próprio (``SENADO_ADM_HTTP_CONCURRENCY``)
    - Retry com exponential backoff via tenacity para erros transitórios
      (rede/SSL, HTTP 429/5xx); ``max_retries`` controla o número de tentativas
    - Falsos 404 retornam lista vazia (mesmo comportamento do CamaraClient)
    - Agnóstico de shape: não normaliza envelope; devolve o JSON como veio
    """

    BASE_URL = SENADO_ADM_API_BASE_URL

    def __init__(self, max_retries: int = 5):
        """
        Inicializa o cliente HTTP da API adm-dadosabertos.

        Args:
            max_retries: Número máximo de tentativas por requisição (padrão 5).
        """
        self.max_retries = max_retries
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "iPolitico-ETL-OpenSource/1.0",
        }
        self._semaphore = asyncio.Semaphore(SENADO_ADM_HTTP_CONCURRENCY)
        # O tenacity avalia ``stop_after_attempt`` no momento da decoração;
        # para ligar o ``max_retries`` da instância, o retry é construído aqui
        # (ao contrário do decorator estático do SenadoClient).
        self._fetch_with_retry = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception(_is_transient_error),
            reraise=True,
        )(self._fetch_once)

    async def warmup_for_domain(
        self,
        domain: Any,
        jobs: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """No-op: API adm-dadosabertos não exige pré-aquecimento de cache.

        Existe apenas para compatibilidade com a interface esperada pelo
        PipelineManager.

        Args:
            domain: Tipo do domínio (ignorado — sem warmup necessário).
            jobs: Lista de jobs (ignorado — sem warmup necessário).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            None.
        """
        return None

    async def fetch(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        Executa requisição GET à API adm-dadosabertos com retry e backoff.

        Aplica retry via tenacity para erros transitórios (timeout, rede/SSL,
        HTTP 429/5xx). HTTP 404 é tratado como lista vazia sem retry.

        Args:
            endpoint: Caminho relativo do recurso (ex:
                      ``'servidores/remuneracoes/2013/1'``). Sem sufixo
                      ``.json`` — a base adm-dadosabertos não o usa.
            params: Parâmetros de query string (opcional).

        Returns:
            JSON decodificado como veio da API (lista top-level ou envelope
            ``{statusCode, msg, data}``) — sem normalização. Retorna lista
            vazia em 404 (recurso sem dados).

        Raises:
            SenadoAdmAPIError: Se esgotar as tentativas de conexão.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        return await self._fetch_with_retry(url, params)

    async def _fetch_once(self, url: str, params: dict[str, Any] | None) -> Any:
        """Executa uma única tentativa de GET, dentro do semáforo."""
        async with self._semaphore:
            async with httpx.AsyncClient(
                timeout=30.0, headers=self.headers, follow_redirects=True
            ) as client:
                try:
                    response = await client.get(url, params=params)
                except (httpx.RequestError, ssl.SSLError) as e:
                    # Rede/SSL transiente (ex: [SSL: INVALID_SESSION_ID] do survey)
                    # → SenadoAdmAPIError transitório para o tenacity retry.
                    raise SenadoAdmAPIError(
                        f"Falha de rede/SSL ao acessar {url}: {e}"
                    ) from e

                # 404: recurso sem dados → lista vazia (sem retry)
                if response.status_code == 404:
                    logger.debug("Recurso inexistente (404) em %s. Assumindo lista vazia.", url)
                    return []

                # 2xx: sucesso — devolve o JSON como veio (agnóstico de shape)
                if response.is_success:
                    return response.json()

                # 429/5xx: raise SenadoAdmAPIError para o @retry tentar novamente
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Erro transitório (%d) em %s. Retry via tenacity.",
                        response.status_code,
                        url,
                    )
                    raise SenadoAdmAPIError(
                        f"Erro transitório HTTP {response.status_code} em {url}"
                    )

                # Demais erros HTTP: fatal, não tenta novamente
                raise SenadoAdmAPIError(
                    f"Erro HTTP {response.status_code} em {url}: {response.text[:200]}"
                )
