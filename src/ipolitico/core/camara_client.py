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

from ipolitico.core.config import (
    CAMARA_API_BASE_URL,
    CAMARA_HTTP_CONCURRENCY,
    CAMARA_MAX_BACKOFF_S,
    CAMARA_QUARANTINE_THRESHOLD,
)
from ipolitico.core.constants import ApiParams, DomainType
from ipolitico.core.exceptions import ResourceQuarantinedError

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

    def __init__(
        self,
        max_retries: int = 10,
        max_backoff_s: int | None = None,
        quarantine_threshold: int | None = None,
    ):
        """
        Inicializa o cliente com resiliência configurável.

        Args:
            max_retries: Nº máximo de tentativas por chamada HTTP.
            max_backoff_s: Teto (em segundos) do backoff exponencial
                ``2**attempt``. Se None, usa ``CAMARA_MAX_BACKOFF_S`` da config.
            quarantine_threshold: Nº de falhas 5xx CONSECUTIVAS em um mesmo
                recurso que o coloca em quarentena (pulado instantâneo). Se
                None, usa ``CAMARA_QUARANTINE_THRESHOLD`` da config. Os
                parâmetros explícitos permitem que testes fixem valores sem
                depender de variáveis de ambiente.
        """
        self.max_retries = max_retries
        self.max_backoff_s = CAMARA_MAX_BACKOFF_S if max_backoff_s is None else max_backoff_s
        self.quarantine_threshold = (
            CAMARA_QUARANTINE_THRESHOLD if quarantine_threshold is None else quarantine_threshold
        )
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "iPolitico-ETL-OpenSource/1.0",
        }
        self._init_telemetry()
        self._semaphore = asyncio.Semaphore(CAMARA_HTTP_CONCURRENCY)
        # Inicializa o cache de warmup como atributo de instância.
        # O sentinel class-level (None) nunca é usado diretamente.
        self._warmed_urls: set[str] = set()
        # Estado da quarentena por recurso (path + params estáveis), em memória.
        # Falhas CONSECUTIVAS por recurso; recurso entra em _quarantined ao
        # atingir quarantine_threshold e passa a ser pulado sem chamada HTTP.
        self._resource_failures: dict[str, int] = {}
        self._quarantined: set[str] = set()

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
            ResourceQuarantinedError: Se o recurso acumular ``quarantine_threshold``
                falhas 5xx consecutivas — e em toda chamada seguinte ao mesmo
                recurso, que é pulado sem chamada HTTP até o fim da execução.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        resource_key = self._resource_key(endpoint, params)

        # Pré-resolve DNS para isolar falhas de resolução de nome
        from urllib.parse import urlparse

        hostname = urlparse(url).hostname
        if hostname:
            await self._resolve_host_with_retries(hostname)
        async with self._semaphore:
            # Re-checagem após adquirir o semáforo: o check pré-semáforo seria
            # uma corrida TOCTOU benigna; aqui o estado já está serializado.
            if resource_key in self._quarantined:
                raise ResourceQuarantinedError(
                    f"Recurso em quarentena (pulado sem chamada HTTP): {url}"
                )
            async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
                for attempt in range(1, self.max_retries + 1):
                    try:
                        response = await client.get(url, params=params)

                        # Erros de Servidor (500/502/503/504): incrementa o
                        # contador de falhas CONSECUTIVAS do recurso. Ao atingir
                        # o threshold, o recurso entra em quarentena e passa a
                        # ser pulado instantâneo — é a "maçã podre" que não cede
                        # com backoff (ex: /deputados/{id}/discursos persistente).
                        if response.status_code in (500, 502, 503, 504):
                            self._resource_failures[resource_key] = (
                                self._resource_failures.get(resource_key, 0) + 1
                            )
                            if self._resource_failures[resource_key] >= self.quarantine_threshold:
                                self._quarantined.add(resource_key)
                                logger.warning(
                                    f"[QUARENTENA] Recurso em quarentena após "
                                    f"{self.quarantine_threshold} falhas 5xx "
                                    f"consecutivas: {url}"
                                )
                                raise ResourceQuarantinedError(
                                    f"Recurso em quarentena após "
                                    f"{self.quarantine_threshold} falhas 5xx "
                                    f"consecutivas: {url}"
                                )
                            logger.warning(
                                f"Erro de servidor ({response.status_code}) em {url}. "
                                f"Tentativa {attempt}/{self.max_retries}."
                            )
                            await self._backoff(attempt)
                            continue

                        # Defesa contra Throttling (HTTP 429). NÃO entra em
                        # quarentena: é sinal global de rate-limit que cede com
                        # backoff — e o teto de backoff já limita o custo.
                        if response.status_code == 429:
                            logger.warning(
                                f"Throttling detectado (429) em {url}. "
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
                            self._reset_resource(resource_key)
                            logger.debug(
                                f"Recurso inexistente ({response.status_code}) em {url}. "
                                "Assumindo lista vazia."
                            )
                            return []

                        response.raise_for_status()
                        payload = response.json()

                        # Sucesso: zera o contador de falhas do recurso.
                        self._reset_resource(resource_key)

                        # Isola os dados úteis da casca de metadados da Câmara
                        if "dados" in payload:
                            return payload["dados"]

                        return payload

                    except httpx.RequestError as e:
                        # Erro transitório que se recupera nas retentativas:
                        # DEBUG (com o tipo da exceção para diagnóstico), não ERROR.
                        # A falha final já é logada pelo runner ("Erro fatal"). Sem
                        # isso, cada tentativa-que-recobra poluía o log com ERROR.
                        logger.debug(
                            f"Erro de rede ({type(e).__name__}) ao conectar "
                            f"com a infraestrutura governamental: {e}"
                        )
                        await self._backoff(attempt)

                # Esgotadas as tentativas, estouramos o erro para o Extrator/Orquestrador agir
                raise CamaraAPIError(
                    f"Falha catastrófica ao acessar {url} após "
                    f"{self.max_retries} tentativas com backoff."
                )

    def _resource_key(self, endpoint: str, params: dict[str, Any] | None) -> str:
        """
        Chave de quarentena de um recurso: path + parâmetros estáveis.

        Parâmetros de paginação/ordenação (``pagina``, ``itens``, ``ordem``,
        ``ordenarPor``) ficam de fora: páginas da MESMA janela compartilham o
        contador de falhas. Parâmetros de filtro (ex: ``ano``, ``mes``,
        ``dataInicio``, ``dataFim``) participam, isolando um recurso podre sem
        quarentenar o domínio inteiro.

        Args:
            endpoint: Caminho da API (nunca traz query string).
            params: Parâmetros da query string (pode ser None).

        Returns:
            str: Chave estável do recurso, serializada de forma determinística.
        """
        if not params:
            return endpoint
        excluded = {
            ApiParams.PAGINA.value,
            ApiParams.ITENS.value,
            ApiParams.ORDEM.value,
            ApiParams.ORDENAR_POR.value,
        }
        stable = {k: v for k, v in params.items() if k not in excluded}
        if not stable:
            return endpoint
        query = "&".join(f"{k}={v}" for k, v in sorted(stable.items()))
        return f"{endpoint}?{query}"

    def _reset_resource(self, resource_key: str) -> None:
        """
        Zera o contador de falhas consecutivas de um recurso.

        Chamado em resposta 2xx e em 400/404 (falso positivo = recurso válido,
        apenas sem dados). Limpa o dicionário sem levantar — a falha precisa ser
        CONSECUTIVA para contar para quarentena.

        Args:
            resource_key: Chave de quarentena do recurso.

        Returns:
            N/A (muta estado interno do client).
        """
        self._resource_failures.pop(resource_key, None)

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
        Finaliza o client e reporta o resumo da quarentena da execução.

        O resumo é uma conveniência de observabilidade — o sinal autoritativo
        por recurso é o WARNING ``[QUARENTENA]`` emitido no momento em que o
        recurso entra em quarentena (sobrevive até a SIGKILL).

        Returns:
            N/A.
        """
        if not self._quarantined:
            logger.info("[QUARENTENA] Nenhum recurso em quarentena nesta execução.")
            return
        listing = "\n  ".join(sorted(f"{self.BASE_URL}/{k}" for k in self._quarantined))
        logger.warning(
            "[QUARENTENA] Resumo da execução — %d recurso(s) em quarentena (pulados "
            "sem chamada HTTP; re-testados na próxima execução):\n  %s",
            len(self._quarantined),
            listing,
        )

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
        """
        Pausa a execução com backoff exponencial, com teto.

        Crescimento 2s, 4s, 8s, 16s... mas limitado a ``self.max_backoff_s``
        (padrão 30s). Sem o teto, a tentativa 10 dormiria 1024s (~17min) — o
        cenário que fez uma execução com poucos recursos 5xx demorar horas.

        Args:
            attempt: Número da tentativa atual (1-based).

        Returns:
            N/A (só espera).
        """
        sleep_time = min(2**attempt, self.max_backoff_s)
        logger.info(
            f"Recuo tático. Aguardando {sleep_time} segundos antes da próxima requisição..."
        )
        await asyncio.sleep(sleep_time)
