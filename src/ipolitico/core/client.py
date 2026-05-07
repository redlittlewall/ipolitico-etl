import asyncio
import logging
import os
import urllib
from datetime import time
from typing import Any

import httpx

from ipolitico.core.config import CAMARA_API_BASE_URL

logger = logging.getLogger(__name__)


class CamaraAPIError(Exception):
    """Exceção base para falhas gerais na API da Câmara."""

    pass


class CamaraClient:
    """
    Cliente HTTP Assíncrono focado na resiliência contra infraestruturas estatais.

    Implementa defesas ativas contra Throttling (HTTP 429), timeouts e falhas
    determinísticas (falsos positivos de HTTP 404).
    """

    BASE_URL = CAMARA_API_BASE_URL

    def __init__(self, max_retries: int = 10):
        self.max_retries = max_retries
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "iPolitico-ETL-OpenSource/1.0",
        }

    async def fetch(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[Any] | dict[str, Any]:
        """
        Executa requisições GET à API com lógica de retentativa e backoff.

        Args:
            endpoint (str): O caminho da API (ex: '/deputados').
            params (dict, optional): Parâmetros da query string.

        Returns:
            list | dict: Payload de dados retornado pela API. Retorna lista vazia em 404.

        Raises:
            CamaraAPIError: Se esgotar as tentativas de conexão ou receber erros de servidor.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await client.get(url, params=params)

                    # Defesa contra Throttling (Erros Transientes)
                    if response.status_code in (429, 500, 502, 503, 504):
                        logger.warning(
                            f"Throttling detectado ({response.status_code}) em {url}. "
                            f"Tentativa {attempt}/{self.max_retries}."
                        )
                        await self._backoff(attempt)
                        continue

                    # Defesa contra Falsos Positivos da API - Aborta tentativa
                    if response.status_code == 404:
                        logger.debug(f"Recurso inexistente (404) em {url}. Assumindo lista vazia.")
                        return []

                    response.raise_for_status()
                    payload = response.json()

                    # Isola os dados úteis da casca de metadados da Câmara
                    if "dados" in payload:
                        return payload["dados"]

                    return payload

                except httpx.RequestError as e:
                    logger.error(
                        f"Erro de rede ao conectar com a infraestrutura governamental: {e}"
                    )
                    await self._backoff(attempt)

            # Esgotadas as tentativas, estouramos o erro para o Extrator/Orquestrador agir
            raise CamaraAPIError(
                f"Falha catastrófica ao acessar {url} após "
                f"{self.max_retries} tentativas com backoff."
            )

    async def download_file(self, url: str, dest_path: str) -> bool:
        """
        Faz o download de arquivos estáticos (CSV/ZIP) com a mesma resiliência
        usada na API (Exponential Backoff para 50X e 429).

        Args:
            url (str): A URL completa e absoluta do arquivo.
            dest_path (str): O caminho no disco onde o arquivo será salvo.

        Returns:
            bool: True se o download foi um sucesso, False se o arquivo não existir (404).
        """

        def sync_download():
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML ¨ike Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            for attempt in range(self.max_retries):
                # Verifica quanto do arquivo já sobreviveu no HD
                downloaded = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

                req = urllib.request.Request(url, headers=headers)

                # Se já tem algo, pede para a Câmara mandar só o que falta
                if downloaded > 0:
                    req.add_header("Range", f"bytes={downloaded}-")

                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        if response.getcode() == 200 and downloaded > 0:
                            downloaded = 0
                            mode = "wb"  # Sobrescreve tudo
                        else:
                            mode = "ab" if downloaded > 0 else "wb"

                        with open(dest_path, mode) as f:
                            while True:
                                chunk = response.read(1024 * 1024)  # Puxa 1 Megabyte por vez
                                if not chunk:
                                    break
                                f.write(chunk)

                        return True

                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        return False
                    if e.code == 416:
                        # Range Not Satisfiable: Significa que o arquivo já foi 100% baixado!
                        return True

                    time.sleep(2)

                except Exception:
                    logger.warning(f"Queda de conexão no byte {downloaded}. Retomando...")
                    time.sleep(3)

            return False

        sucesso = await asyncio.to_thread(sync_download)
        if not sucesso:
            logger.error(f"Falha catastrófica ao baixar {url} após {self.max_retries} tentativas.")

        return sucesso

    async def close(self) -> None:
        """
        Garante a compatibilidade com a interface do orquestrador.
        """
        pass

    async def _backoff(self, attempt: int) -> None:
        """Pausa a execução usando Crescimento Exponencial (2s, 4s, 8s...)"""
        sleep_time = 2**attempt
        logger.info(
            f"Recuo tático. Aguardando {sleep_time} segundos antes da próxima requisição..."
        )
        await asyncio.sleep(sleep_time)
