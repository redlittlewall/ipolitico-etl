import asyncio
import logging
import os
import socket
import sqlite3
import urllib
from datetime import time
from pathlib import Path
from typing import Any

import httpx

from ipolitico.core.config import CAMARA_API_BASE_URL, CAMARA_HTTP_CONCURRENCY
from ipolitico.core.constants import DomainType

logger = logging.getLogger(__name__)

TELEMETRY_DB_PATH = Path("data/api_telemetry.db")


class CamaraAPIError(Exception):
    """Exceção base para falhas gerais na API da Câmara."""

    pass


class CamaraClient:
    """
    Cliente HTTP Assíncrono focado na resiliência contra infraestruturas estatais.

    Implementa defesas ativas contra Throttling (HTTP 429), timeouts e falhas
    determinísticas (falsos positivos de HTTP 404). Também gerencia
    pré-aquecimento seletivo de cache (warmup) para rotas com histórico de 504.
    """

    BASE_URL = CAMARA_API_BASE_URL

    # Rastreamento global de URLs já aquecidas nesta sessão.
    # Evita re-aquecer a mesma URL quando domínios compartilham recursos
    # ou quando o mesmo domínio roda múltiplas vezes.
    _warmed_urls: set[str] | None = None  # class-level sentinel

    def __init__(self, max_retries: int = 10):
        self.max_retries = max_retries
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "iPolitico-ETL-OpenSource/1.0",
        }
        self._init_telemetry()
        self._semaphore = asyncio.Semaphore(CAMARA_HTTP_CONCURRENCY)
        # Inicializa o cache de warmup como atributo de instância.
        # O sentinel class-level (None) nunca é usado diretamente.
        self._warmed_urls: set[str] = set()

    def _init_telemetry(self):
        """Inicializa um banco SQLite super leve apenas para logs de requisições."""
        TELEMETRY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(TELEMETRY_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    endpoint TEXT,
                    method TEXT,
                    status_code INTEGER,
                    response_time_ms REAL,
                    success BOOLEAN
                )
            """)

    def _log_api_call(self, endpoint: str, method: str, status: int, time_ms: float, success: bool):
        """Salva a métrica da requisição no banco de dados isolado."""
        try:
            with sqlite3.connect(TELEMETRY_DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO api_requests "
                    "(endpoint, method, status_code, response_time_ms, success) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (endpoint, method, status, time_ms, success),
                )
        except Exception:
            pass  # Nunca deixamos a telemetria quebrar o negócio principal

    async def _resolve_host_with_retries(self, hostname: str, max_retries: int = 3) -> str | None:
        """
        Pré-resolve o hostname da API de forma assíncrona antes de tentar a requisição HTTP.

        Isola falhas de DNS (nome não resolve) das falhas de rede (conexão caiu),
        permitindo retry específico no DNS sem contaminar a lógica de backoff HTTP.

        Args:
            hostname: Nome do host a resolver.
            max_retries: Número máximo de tentativas de DNS.

        Returns:
            IP resolvido como string, ou None se esgotaram as tentativas.
        """
        for attempt in range(1, max_retries + 1):
            try:
                result = await asyncio.to_thread(socket.getaddrinfo, hostname, 443, socket.AF_INET)
                return result[0][4][0]
            except socket.gaierror:
                if attempt < max_retries:
                    logger.warning(
                        "[DNS] Falha ao resolver %s (tentativa %d/%d). Retentando em 2s...",
                        hostname,
                        attempt,
                        max_retries,
                    )
                    await asyncio.sleep(2)
                else:
                    logger.error(
                        "[DNS] Falha catastrófica ao resolver %s após %d tentativas.",
                        hostname,
                        max_retries,
                    )
        return None

    async def fetch(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[Any] | dict[str, Any]:
        """
        Executa requisições GET à API com lógica de retentativa e backoff.

        Inclui pré-resolução de DNS com retry dedicado para isolar falhas de
        resolução de nome (comuns em runners cloud) das falhas de rede.

        Args:
            endpoint (str): O caminho da API (ex: '/deputados').
            params (dict, optional): Parâmetros da query string.

        Returns:
            list | dict: Payload de dados retornado pela API. Retorna lista vazia em 404.

        Raises:
            CamaraAPIError: Se esgotar as tentativas de conexão ou receber erros de servidor.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        # Pré-resolve DNS para isolar falhas de resolução de nome
        from urllib.parse import urlparse

        hostname = urlparse(url).hostname
        if hostname:
            await self._resolve_host_with_retries(hostname)
        async with self._semaphore:
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
                        # 404: endpoint não tem dados (ex: deputado sem discursos).
                        # 400: mesmo caso em alguns endpoints inconsistentes da API
                        # (ex: /partidos/{id}/lideres para partidos extintos,
                        # /deputados/{id}/discursos para deputados históricos).
                        if response.status_code in (400, 404):
                            logger.debug(
                                f"Recurso inexistente ({response.status_code}) em {url}. "
                                "Assumindo lista vazia."
                            )
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

    async def warmup_for_domain(
        self,
        domain: DomainType,
        jobs: list[dict[str, Any]],
        only_new: bool = True,
        parallel: bool = False,
        max_parallel: int = 5,
    ) -> None:
        """Pré-aquece o cache da API para URLs de um domínio (best-effort).

        Por padrão (parallel=False), cada URL é chamada sequencialmente.
        Com parallel=True, até ``max_parallel`` URLs são aquecidas em paralelo,
        reduzindo o tempo total de warmup em troca de maior chance de 504
        da API. Erros são ignorados — o warmup é sempre opcional.

        Args:
            domain: Tipo do domínio a aquecer.
            jobs: Lista de jobs gerados pelo ``CamaraJobPlanner``.
                  Usada apenas para extrair IDs; o conteúdo é irrelevante.
            only_new: Se True (padrão), pula URLs já aquecidas nesta sessão
                      via ``_warmed_urls``.
            parallel: Se True, faz requisições paralelas (até max_parallel).
            max_parallel: Número máximo de requisições simultâneas no warmup.
        """
        # Import lazy para evitar dependência circular
        from ipolitico.core.warmup import WARMUP_CONFIG, build_warmup_urls

        spec = WARMUP_CONFIG.get(domain)
        if spec is None or not jobs:
            return

        urls = build_warmup_urls(self.BASE_URL, jobs, spec)
        if not urls:
            return

        if only_new:
            new_urls = [u for u in urls if u not in self._warmed_urls]
            skipped = len(urls) - len(new_urls)
        else:
            new_urls = list(urls)
            skipped = 0

        if not new_urls:
            logger.info(
                "[WARMUP] %s: todas as %d URLs já aquecidas anteriormente.",
                domain.value.upper(),
                len(urls),
            )
            return

        modo = "paralelo" if parallel else "sequencial"
        logger.info(
            "[WARMUP] %s: aquecendo %d URLs (saltou %d repetidas, %s, best-effort)...",
            domain.value.upper(),
            len(new_urls),
            skipped,
            modo,
        )

        warmed = 0

        async def _warm_one(client: httpx.AsyncClient, url: str) -> None:
            nonlocal warmed
            try:
                await client.get(url, timeout=30.0)
                warmed += 1
            except Exception:
                pass  # Best-effort
            finally:
                self._warmed_urls.add(url)

        async with httpx.AsyncClient(timeout=60.0, headers=self.headers) as client:
            if parallel:
                sem = asyncio.Semaphore(max_parallel)

                async def _bounded(url: str) -> None:
                    async with sem:
                        await _warm_one(client, url)

                await asyncio.gather(*[_bounded(u) for u in new_urls])
            else:
                for url in new_urls:
                    await _warm_one(client, url)

        logger.info(
            "[WARMUP] %s: concluído — %d/%d URLs aquecidas (ignorando erros).",
            domain.value.upper(),
            warmed,
            len(new_urls),
        )

    async def _backoff(self, attempt: int) -> None:
        """Pausa a execução usando Crescimento Exponencial (2s, 4s, 8s...)"""
        sleep_time = 2**attempt
        logger.info(
            f"Recuo tático. Aguardando {sleep_time} segundos antes da próxima requisição..."
        )
        await asyncio.sleep(sleep_time)
