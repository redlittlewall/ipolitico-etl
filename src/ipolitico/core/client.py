import asyncio
import logging
from typing import Any

import httpx

from ipolitico.core.config import CAMARA_API_BASE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CamaraAPIError(Exception):
    """Exceção base para falhas gerais na API da Câmara."""

    pass


class SilentEmptyDataError(CamaraAPIError):
    """Lançada para barrar o bug da API que retorna 200 OK com array vazio em instabilidades."""

    pass


class CamaraClient:
    BASE_URL = CAMARA_API_BASE_URL

    def __init__(self, max_retries: int = 5):
        self.max_retries = max_retries
        # User-Agent claro e institucional evita bloqueios automáticos por firewalls do governo
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "iPolitico-ETL-OpenSource/1.0",
        }

    async def fetch(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[Any] | dict[str, Any]:
        """
        Realiza requisições GET assíncronas com tratamento de erros focado nas falhas estatais.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await client.get(url, params=params)

                    # Defesa contra Throttling (Saturação e Limitação de Taxa)
                    if response.status_code in (429, 503):
                        logger.warning(
                            f"Throttling detectado ({response.status_code}) em {url}. "
                            f"Tentativa {attempt}/{self.max_retries}."
                        )
                        await self._backoff(attempt)
                        continue

                    response.raise_for_status()
                    payload = response.json()

                    # Defesa contra a Falha Silenciosa de Array Vazio (Ameaça Mapeada)
                    if "dados" in payload:
                        dados = payload["dados"]
                        # Se for uma lista vazia,
                        # barramos a extração para proteger a integridade do banco
                        if isinstance(dados, list) and len(dados) == 0:
                            raise SilentEmptyDataError(
                                f"Erro silencioso flagrado: HTTP 200 recebido, "
                                f"mas 'dados' vazio em {url}"
                            )
                        return dados

                    return payload

                except httpx.RequestError as e:
                    logger.error(
                        f"Erro de rede ao conectar com a infraestrutura governamental: {e}"
                    )
                    await self._backoff(attempt)

            # Se esgotar as tentativas, é preferível abortar o pipeline a gravar lixo no Data Lake
            raise CamaraAPIError(
                f"Falha catastrófica ao acessar {url} após "
                f"{self.max_retries} tentativas com backoff."
            )

    async def _backoff(self, attempt: int) -> None:
        """Implementa Exponential Backoff para não sobrecarregar o serviço público."""
        sleep_time = 2**attempt  # Espera 2s, 4s, 8s, 16s...
        logger.info(
            f"Recuo tático. Aguardando {sleep_time} segundos antes da próxima requisição..."
        )
        await asyncio.sleep(sleep_time)
