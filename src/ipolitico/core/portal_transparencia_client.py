"""Cliente HTTP resiliente para a API v3 do Portal da Transparência (CGU).

Segue o padrão do ``SenadoAdmClient`` (semáforo próprio, retry tenacity só para
erros transitórios, 404 → lista vazia), com duas diferenças de domínio:

1. **Autenticação por chave do usuário:** a chave gratuita gerada no portal vai
   no header ``chave-api-dados``. Sem chave a API responde 401 — o cliente levanta
   ``PortalTransparenciaAuthError`` (não retentado: re-tentar com a mesma chave
   não muda nada). A chave real vive só no ``.env`` (gitignored).
2. **``download_file`` com resume via Range header:** dumps bulk de
   ``/download-de-dados`` são baixados para um diretório persistente; se a
   conexão cai no meio (WAF derrubando conexões longas), o retry pede apenas o
   trecho restante (``Range: bytes=N-``) em vez de recomeçar do zero.

O download bulk fica **fora** do semáforo da API: o host de dumps
(``portaldatransparencia.gov.br`` / ``dadosabertos-download.cgu.gov.br``) é
diferente da API v3 (``api.portaldatransparencia.gov.br``) e os jobs de bulk já
são naturalmente serializados pelo pipeline — mesmo padrão do ``CamaraClient``.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ipolitico.core.config import PORTAL_API_BASE_URL, PORTAL_HTTP_CONCURRENCY

logger = logging.getLogger(__name__)

# O host de bulk responde melhor a um User-Agent de navegador (mesma estratégia
# do CamaraClient para downloads estáticos; o host público não é a API v3).
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class PortalTransparenciaAPIError(Exception):
    """Exceção base para falhas na API v3 do Portal da Transparência.

    Args:
        message: Descrição do erro (inclusive o status HTTP quando houver).
        status_code: Status HTTP que originou o erro, quando ele veio de um
            response (403 do host de dumps, 400 da API, etc.); ``None`` quando
            o erro não tem status (ex: falha de rede). Usado pelo extrator bulk
            multi-módulo de cartões para distinguir o 403 do módulo
            indisponível (pulado) de um erro de autorização real.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PortalTransparenciaAuthError(PortalTransparenciaAPIError):
    """Erro de autenticação (HTTP 401/403) — chave ausente, inválida ou sem permissão.

    Não é retentado: re-tentar com a mesma chave não muda o resultado. A chave é
    gratuita e por usuário (``PORTAL_API_KEY`` no .env, nunca versionada).
    """

    pass


class PortalTransparenciaTransientError(PortalTransparenciaAPIError):
    """Erro transitório (rede, HTTP 429/5xx) — deve ser retentado pelo tenacity.

    Distingue do erro fatal (demais HTTP 4xx) para que o retry só tente novamente
    o que é recuperável — HTTP 400 não é, 429 é.
    """

    pass


class PortalTransparenciaWAFError(PortalTransparenciaAPIError):
    """O host de dumps bloqueou o download via AWS WAF (403 + desafio JS).

    Verificado real no ticket 03: ``portaldatransparencia.gov.br`` /
    ``dadosabertos-download.cgu.gov.br`` responde 403 com desafio JS (CAPTCHA
    ``awswaf``) a clientes não-browser — um agente HTTP puro não resolve. NÃO é
    transitório (re-tentar com a mesma assinatura não muda o resultado), então
    não é retentado pelo tenacity. O ``PortalTransparenciaBulkExtractor`` captura
    este erro e devolve lista vazia — o job não cai; quando o WAF liberar, o
    mesmo job passa a baixar sem mudança de código.
    """

    pass


def _is_transient_error(exception: BaseException) -> bool:
    """
    Decide se uma exceção é transitória (deve tentar novamente).

    Args:
        exception: Exceção levantada durante a requisição.

    Returns:
        True para erro de transporte (rede/read/timeout — inclui queda de conexão
        no meio de download) e ``PortalTransparenciaTransientError`` (HTTP 429/5xx);
        False para erros fatais (demais HTTP 4xx, erros de autenticação).
    """
    if isinstance(exception, PortalTransparenciaTransientError):
        return True
    # httpx.TransportError cobre NetworkError, ReadError (queda no meio do stream)
    # e TimeoutException — tudo transiente.
    if isinstance(exception, httpx.TransportError):
        return True
    return False


# Headers que o AWS WAF injeta na resposta de bloqueio (desafio JS/CAPTCHA).
# SÓ os específicos do WAF (``x-amzn-waf-*``): os genéricos do AWS
# (``x-amzn-requestid``, ``x-amzn-trace-id``) também aparecem em 403 de S3/
# CloudFront — inclui-los faria um 403 fatal ser engolido como "WAF gracioso".
_WAF_HEADER_MARKERS = (
    "x-amzn-waf-action",
    "x-amzn-waf-request-id",
    "x-amzn-waf-rule-id",
)
# Marca de corpo da página de bloqueio do WAF (Challenge JS / CAPTCHA) — o
# "awswaf" identifica o desafio (observado real no ticket 03). "AccessDenied"
# é genérico de AWS (S3/IAM) e NÃO entra aqui pelo mesmo motivo dos headers.
_WAF_BODY_MARKERS = ("awswaf",)


def _is_waf_block(response: httpx.Response) -> bool:
    """
    Detecta um bloqueio do AWS WAF (desafio JS) numa resposta HTTP 403.

    O host de dumps responde 403 com header ``x-amzn-waf-*`` (ação/regra do
    WAF) e/ou corpo com ``awswaf`` (desafio JS/CAPTCHA) quando bloqueia
    clientes não-browser (validado real no ticket 03). Distingue de um 403
    genérico do host (S3/CloudFront) — que é erro fatal
    ``PortalTransparenciaAPIError``, não WAF. Só assinaturas específicas do
    WAF contam; headers/corpo genéricos do AWS ficam de fora para não engolir
    um 403 fatal como "WAF-gracioso".

    Args:
        response: Resposta HTTP do host de dumps (já com o corpo lido).

    Returns:
        True se a resposta carrega a assinatura do WAF; False caso contrário.
    """
    if any(marker in response.headers for marker in _WAF_HEADER_MARKERS):
        return True
    body = response.text[:2000].lower()
    return any(marker in body for marker in _WAF_BODY_MARKERS)


class PortalTransparenciaClient:
    """
    Cliente HTTP assíncrono para a API v3 do Portal da Transparência (CGU).

    Características:
    - Autenticação por chave do usuário (header ``chave-api-dados``); sem chave,
      a API responde 401 → ``PortalTransparenciaAuthError`` (sem retry).
    - Semáforo de concorrência próprio (``PORTAL_HTTP_CONCURRENCY``).
    - Retry com exponential backoff via tenacity para erros transitórios
      (rede, HTTP 429/5xx); ``max_retries`` controla o número de tentativas.
    - Falsos 404 retornam lista vazia (mesmo comportamento do CamaraClient).
    - Agnóstico de shape: a API v3 devolve lista top-level; o cliente entrega o
      JSON como veio, sem normalizar envelope.
    - ``download_file`` com resume via Range header para dumps bulk de
      ``/download-de-dados`` (defesa anti-WAF).
    """

    BASE_URL = PORTAL_API_BASE_URL

    def __init__(self, api_key: str | None = None, max_retries: int = 5):
        """
        Inicializa o cliente HTTP da API v3 do Portal da Transparência.

        Args:
            api_key: Chave gratuita do usuário (header ``chave-api-dados``). Se
                ausente, um aviso é logado e as chamadas à API v3 falham com 401.
            max_retries: Número máximo de tentativas por requisição (padrão 5).
        """
        self.max_retries = max_retries
        self.headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "iPolitico-ETL-OpenSource/1.0",
        }
        if api_key:
            self.headers["chave-api-dados"] = api_key
        else:
            logger.warning(
                "PORTAL_API_KEY ausente: a API v3 responde 401 sem a chave do usuário "
                "(PortalTransparenciaAuthError). Gere uma chave gratuita no portal e "
                "defina-a no .env (nunca em arquivos versionados)."
            )
        self._semaphore = asyncio.Semaphore(PORTAL_HTTP_CONCURRENCY)
        # O tenacity avalia ``stop_after_attempt`` no momento da decoração;
        # para ligar o ``max_retries`` da instância, os retries são construídos
        # aqui (mesmo padrão do SenadoAdmClient).
        self._fetch_with_retry = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception(_is_transient_error),
            reraise=True,
        )(self._fetch_once)
        self._download_with_retry = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception(_is_transient_error),
            reraise=True,
        )(self._download_once)

    async def warmup_for_domain(
        self,
        domain: Any,
        jobs: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """No-op: a API v3 do portal não exige pré-aquecimento de cache.

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

    async def close(self) -> None:
        """Garante a compatibilidade com a interface do orquestrador.

        O cliente não mantém conexões persistentes (um ``httpx.AsyncClient`` é
        aberto por requisição, padrão dos demais sistemas).

        Returns:
            None.
        """
        pass

    async def fetch(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        Executa requisição GET à API v3 do portal com retry e backoff.

        Aplica retry via tenacity para erros transitórios (rede, HTTP 429/5xx).
        HTTP 404 é tratado como lista vazia sem retry.

        Args:
            endpoint: Caminho relativo do recurso (ex:
                ``'api-de-dados/orgaos-siape'``).
            params: Parâmetros de query string (opcional).

        Returns:
            JSON decodificado como veio da API (lista top-level — a v3 não usa
            envelope). Retorna lista vazia em 404 (recurso sem dados).

        Raises:
            PortalTransparenciaAPIError: Se esgotar as tentativas de conexão.
            PortalTransparenciaAuthError: Se a chave for ausente/inválida (401/403).
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        return await self._fetch_with_retry(url, params)

    async def _fetch_once(self, url: str, params: dict[str, Any] | None) -> Any:
        """
        Executa uma única tentativa de GET, dentro do semáforo.

        Args:
            url: URL completa do recurso (base + endpoint).
            params: Parâmetros de query string (opcional).

        Returns:
            JSON decodificado como veio da API, ou lista vazia em 404.

        Raises:
            PortalTransparenciaTransientError: Em falha de rede ou HTTP 429/5xx
                (retentável pelo tenacity).
            PortalTransparenciaAuthError: Em HTTP 401/403 (chave ausente/inválida)
                — sem retry.
            PortalTransparenciaAPIError: Em erro HTTP fatal (demais 4xx) — sem retry.
        """
        async with self._semaphore:
            async with httpx.AsyncClient(
                timeout=30.0, headers=self.headers, follow_redirects=True
            ) as client:
                try:
                    response = await client.get(url, params=params)
                except httpx.TransportError as e:
                    # Rede/read/timeout transiente → retry via tenacity.
                    raise PortalTransparenciaTransientError(
                        f"Falha de rede ao acessar {url}: {e}"
                    ) from e

                # 404: recurso sem dados → lista vazia (sem retry)
                if response.status_code == 404:
                    logger.debug("Recurso inexistente (404) em %s. Assumindo lista vazia.", url)
                    return []

                # 2xx: sucesso — devolve o JSON como veio (agnóstico de shape)
                if response.is_success:
                    return response.json()

                # 401/403: chave ausente/inválida → erro de autenticação distinto
                if response.status_code in (401, 403):
                    raise PortalTransparenciaAuthError(
                        f"Falha de autenticação HTTP {response.status_code} em {url}: "
                        f"{response.text[:200]}"
                    )

                # 429/5xx: transitório → retry via tenacity
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Erro transitório (%d) em %s. Retry via tenacity.",
                        response.status_code,
                        url,
                    )
                    raise PortalTransparenciaTransientError(
                        f"Erro transitório HTTP {response.status_code} em {url}"
                    )

                # Demais erros HTTP: fatal, não tenta novamente
                raise PortalTransparenciaAPIError(
                    f"Erro HTTP {response.status_code} em {url}: {response.text[:200]}",
                    status_code=response.status_code,
                )

    async def download_file(self, url: str, dest_path: str | Path) -> bool:
        """
        Baixa um dump bulk (ZIP/CSV de /download-de-dados) com resume e retry.

        Se o arquivo local já tiver bytes (execução anterior interrompida), o
        cliente pede ``Range: bytes=N-`` e anexa a resposta 206 ao que existe.
        Uma queda no meio do stream (``httpx.ReadError`` — WAF derrubando
        conexões longas) é transiente: o retry retoma do byte parcial, não
        recomeça do zero. Fora do semáforo da API (host de dumps é outro).

        Args:
            url: URL completa do dump (ex:
                ``.../download-de-dados/servidores/202401``).
            dest_path: Caminho persistente no disco onde o arquivo é salvo — o
                partial sobrevive entre execuções para permitir o resume.

        Returns:
            True se o download completou (ou o arquivo local já estava completo —
            416 Range Not Satisfiable); False se o arquivo não existe no servidor
            (404, para o extrator devolver lista vazia).

        Raises:
            PortalTransparenciaAPIError: Se as tentativas esgotarem por erro
                transitório, ou em erro HTTP fatal (demais 4xx).
        """
        return await self._download_with_retry(url, str(dest_path))

    async def _download_once(self, url: str, dest_path: str) -> bool:
        """
        Executa uma única tentativa de download, com resume via Range header.

        Args:
            url: URL completa do dump bulk.
            dest_path: Caminho persistente no disco do arquivo.

        Returns:
            True se completou (incluindo 416 = arquivo local já completo);
            False se o servidor respondeu 404.

        Raises:
            PortalTransparenciaTransientError: Em falha de rede (inclui queda no
                meio do stream) ou HTTP 429/5xx — retentável.
            PortalTransparenciaAPIError: Em erro HTTP fatal (demais 4xx).
        """
        downloaded = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        headers = {"User-Agent": _BROWSER_USER_AGENT}
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    # 404: arquivo não publicado → ausência, não exceção
                    if response.status_code == 404:
                        logger.debug("Dump inexistente (404) em %s.", url)
                        return False
                    # 416 Range Not Satisfiable: o arquivo local já está completo
                    if response.status_code == 416:
                        logger.info("Dump %s já completo no disco (416).", url)
                        return True
                    # 429/5xx: transitório → retry via tenacity
                    if response.status_code in (429, 500, 502, 503, 504):
                        raise PortalTransparenciaTransientError(
                            f"Erro transitório HTTP {response.status_code} em {url}"
                        )
                    # 403 com assinatura do AWS WAF (desafio JS/CAPTCHA) no host
                    # de dumps: não é transitório (re-tentar não resolve o
                    # desafio) → WAFError distinto, sem retry. O extrator bulk
                    # captura e devolve vazio (job WAF-gracioso).
                    if response.status_code == 403:
                        # A assinatura do WAF pode estar só no corpo (ex:
                        # "awswaf"); num response em streaming o corpo ainda não
                        # foi lido — aread() antes de inspecionar (403 é página
                        # de erro pequena, sem custo relevante).
                        await response.aread()
                        if _is_waf_block(response):
                            raise PortalTransparenciaWAFError(
                                f"Bloco AWS WAF (desafio JS) ao baixar {url} — o host "
                                "exige um navegador para o download."
                            )
                        # 403 do S3 anônimo com o envelope XML do objeto ausente
                        # (<Error><Code>AccessDenied</Code>… — validado real no
                        # ticket 04): listing negado → nunca chega a 404.
                        # Ausência análoga ao 404 → False, sem retry. Necessário
                        # para pep/imoveis (dump não publicado) e cpgf/cpcc/cpdc
                        # (mês sem arquivo). O marcador é o envelope `<Code>Access
                        # Denied</Code>`: o texto "AccessDenied" NU (sem o XML)
                        # num 403 não distingue o S3 de um 403 real do host →
                        # permanece fatal abaixo (não engole erro de autorização).
                        if "<code>accessdenied</code>" in response.text[:2000].lower():
                            logger.debug("Dump inexistente (403 AccessDenied do S3) em %s.", url)
                            return False
                    if not response.is_success:
                        raise PortalTransparenciaAPIError(
                            f"Erro HTTP {response.status_code} ao baixar {url}",
                            status_code=response.status_code,
                        )

                    # 206 com parcial já baixado → anexa ao que existe; 200 (servidor
                    # ignorou o Range) ou sem parcial → escreve do zero.
                    mode = "ab" if (response.status_code == 206 and downloaded > 0) else "wb"

                    with open(dest_path, mode) as f:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            f.write(chunk)
                    return True
        except httpx.TransportError as e:
            raise PortalTransparenciaTransientError(
                f"Queda de conexão ao baixar {url} (byte {downloaded}): {e}"
            ) from e
