"""Extrator e parser de pessoal de gabinete de Deputados Federais via scraping HTML."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from html.parser import HTMLParser as StdlibHTMLParser
from typing import Any, Optional

import httpx
import polars as pl
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ipolitico.core.camara_client import CamaraClient
from ipolitico.core.config import CAMARA_HTTP_CONCURRENCY
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class CamaraScraperTransientError(Exception):
    """Exceção para erros de rede ou servidor (HTTP 429/5xx) retentáveis pelo tenacity."""

    pass


def _is_transient_error(exc: BaseException) -> bool:
    """
    Verifica se uma exceção é transitória e deve ser retentada.

    Args:
        exc: Exceção capturada durante a execução da requisição.

    Returns:
        bool: True se for um erro transitório elegível para retry; False caso contrário.
    """
    return isinstance(exc, (CamaraScraperTransientError, httpx.RequestError))


class _TableParser(StdlibHTMLParser):
    """
    Parser HTML baseado na biblioteca padrão para extração de tabelas.

    Gera uma representação matricial tabular: lista de tabelas, onde cada
    tabela é uma lista de linhas contendo textos de suas células.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            self._current_table = []
        elif tag_lower == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag_lower in ("td", "th") and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in ("td", "th") and self._current_cell is not None:
            text = "".join(self._current_cell).strip()
            if self._current_row is not None:
                self._current_row.append(text)
            self._current_cell = None
        elif tag_lower == "tr" and self._current_row is not None:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag_lower == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None


def _extract_tables_from_html(html: str) -> list[list[list[str]]]:
    """
    Extrai matrizes de tabelas de um documento HTML.

    Tenta utilizar `selectolax`, depois `BeautifulSoup4` e por fim recorre
    ao parser nativo da biblioteca padrão (`html.parser.HTMLParser`).

    Args:
        html: String contendo o código HTML bruto da página.

    Returns:
        list[list[list[str]]]: Lista de tabelas, com suas respectivas linhas e células.
    """
    # 1. Tentativa com selectolax (parser ultrarrápido em C)
    try:
        from selectolax.parser import HTMLParser as SelectolaxParser

        tree = SelectolaxParser(html)
        tables: list[list[list[str]]] = []
        for table_elem in tree.css("table"):
            rows: list[list[str]] = []
            for tr in table_elem.css("tr"):
                row = [td.text(strip=True) for td in tr.css("th, td")]
                if row:
                    rows.append(row)
            if rows:
                tables.append(rows)
        return tables
    except ImportError:
        pass

    # 2. Tentativa com BeautifulSoup4
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        tables = []
        for table_elem in soup.find_all("table"):
            rows = []
            for tr in table_elem.find_all("tr"):
                row = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                if row:
                    rows.append(row)
            if rows:
                tables.append(rows)
        return tables
    except ImportError:
        pass

    # 3. Fallback resiliente com biblioteca padrão Python (zero dependências externas)
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as e:
        logger.warning("Falha ao parsear HTML com stdlib: %s", e)
        return []

    return parser.tables


def parse_pessoal_gabinete_html(
    html: str,
    deputado_id: int | None = None,
    source_url: str = "",
    captured_at: str = "",
) -> pl.DataFrame:
    """
    Analisa o HTML da página de pessoal de gabinete e extrai a lista nominal de assessores.

    Localiza a tabela relevante por meio dos cabeçalhos esperados (Nome/Servidor, Cargo/Função,
    Grupo Funcional, Início de Exercício/Data) e constrói um DataFrame Polars bruto.

    Args:
        html: Código HTML bruto da página de gabinete.
        deputado_id: Identificador numérico do Deputado Federal na Câmara.
        source_url: URL exata de auditoria consultada.
        captured_at: Timestamp ISO-8601 do instante da captura.

    Returns:
        pl.DataFrame: DataFrame com os registros extraídos contendo colunas:
            `deputado_id`, `nome_assessor`, `cargo`, `grupo_funcional`,
            `data_exercicio`, `captured_at`, `_source_url`.
            Retorna DataFrame vazio caso não encontre tabela ou servidores.
    """
    if not html or not html.strip():
        return pl.DataFrame()

    tables = _extract_tables_from_html(html)
    if not tables:
        return pl.DataFrame()

    matched_rows: list[dict[str, Any]] = []

    for table in tables:
        if len(table) < 2:
            continue

        header = [h.strip().lower() for h in table[0]]

        # Identifica índices de colunas
        col_nome: int | None = None
        col_cargo: int | None = None
        col_grupo: int | None = None
        col_data: int | None = None

        for idx, col_name in enumerate(header):
            if "nome" in col_name or "servidor" in col_name:
                col_nome = idx
            elif "cargo" in col_name or "função" in col_name or "funcao" in col_name:
                col_cargo = idx
            elif "grupo" in col_name:
                col_grupo = idx
            elif any(
                k in col_name
                for k in (
                    "exercício",
                    "exercicio",
                    "início",
                    "inicio",
                    "período",
                    "periodo",
                    "data",
                )
            ):
                col_data = idx

        # A tabela precisa ter ao menos a coluna de Nome
        if col_nome is None:
            continue

        for row in table[1:]:
            if not row or len(row) <= col_nome:
                continue

            nome = row[col_nome].strip()
            # Descarta linhas informativas ou mensagens de ausência
            if not nome or "nenhum" in nome.lower() or "não há" in nome.lower():
                continue

            cargo = (
                row[col_cargo].strip() if col_cargo is not None and len(row) > col_cargo else None
            )
            grupo = (
                row[col_grupo].strip() if col_grupo is not None and len(row) > col_grupo else None
            )
            data = row[col_data].strip() if col_data is not None and len(row) > col_data else None

            matched_rows.append(
                {
                    "deputado_id": deputado_id,
                    "nome_assessor": nome,
                    "cargo": cargo,
                    "grupo_funcional": grupo,
                    "data_exercicio": data,
                    "captured_at": captured_at,
                    "_source_url": source_url,
                }
            )

        if matched_rows:
            break

    if not matched_rows:
        return pl.DataFrame()

    return pl.DataFrame(matched_rows)


class CamaraPessoalGabineteExtractor(CamaraBaseExtractor):
    """
    Extrator assíncrono para o scraping de pessoal de gabinete de Deputados Federais.

    Herda de `CamaraBaseExtractor`, utilizando `httpx` assíncrono controlado por um
    semáforo de concorrência (`CAMARA_HTTP_CONCURRENCY`) e exponential backoff via `tenacity`.
    """

    BASE_SCRAPER_URL = "https://www.camara.leg.br/deputados"

    def __init__(
        self,
        client: Optional[CamaraClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        concurrency: int = CAMARA_HTTP_CONCURRENCY,
        max_retries: int = 5,
    ) -> None:
        """
        Inicializa o extrator de pessoal de gabinete.

        Args:
            client: Instância opcional de `CamaraClient`. Se ausente, cria uma instância padrão.
            http_client: Cliente `httpx.AsyncClient` opcional para injeção ou reutilização.
            concurrency: Número máximo de requisições simultâneas (semáforo).
            max_retries: Número máximo de tentativas com backoff para falhas transitórias.
        """
        base_client = client or CamaraClient()
        super().__init__(client=base_client)
        self.max_retries = max_retries
        self._http_client = http_client
        self._semaphore = asyncio.Semaphore(concurrency)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        self._fetch_with_retry = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception(_is_transient_error),
            reraise=True,
        )(self._fetch_html_once)

    async def _fetch_html_once(self, url: str) -> str:
        """
        Executa uma única tentativa de requisição HTTP GET para obter o HTML.

        Args:
            url: URL completa da página a ser baixada.

        Returns:
            str: Conteúdo HTML da página baixada (ou string vazia em caso de 404).

        Raises:
            CamaraScraperTransientError: Em erro de rede ou código HTTP transitório (429/5xx).
        """
        async with self._semaphore:
            if self._http_client is not None:
                try:
                    response = await self._http_client.get(url, headers=self.headers)
                except httpx.RequestError as exc:
                    raise CamaraScraperTransientError(
                        f"Erro de rede ao acessar {url}: {exc}"
                    ) from exc

                if response.status_code == 404:
                    logger.debug(
                        "Página não encontrada (404) para %s. Assumindo gabinete vazio.", url
                    )
                    return ""

                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Falha transitória HTTP %d em %s. Disparando retry.",
                        response.status_code,
                        url,
                    )
                    raise CamaraScraperTransientError(
                        f"Status HTTP {response.status_code} em {url}"
                    )

                response.raise_for_status()
                return response.text

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                try:
                    response = await client.get(url, headers=self.headers)
                except httpx.RequestError as exc:
                    raise CamaraScraperTransientError(
                        f"Erro de rede ao acessar {url}: {exc}"
                    ) from exc

                if response.status_code == 404:
                    logger.debug(
                        "Página não encontrada (404) para %s. Assumindo gabinete vazio.", url
                    )
                    return ""

                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Falha transitória HTTP %d em %s. Disparando retry.",
                        response.status_code,
                        url,
                    )
                    raise CamaraScraperTransientError(
                        f"Status HTTP {response.status_code} em {url}"
                    )

                response.raise_for_status()
                return response.text

    async def extract(self, deputado_id: Optional[int] = None, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a extração da lista nominal de assessores de gabinete de um deputado.

        Args:
            deputado_id: Identificador numérico do Deputado Federal na Câmara.
            **kwargs: Parâmetros adicionais contextuais (ignorados).

        Returns:
            pl.DataFrame: DataFrame Polars bruto com as linhas de pessoal de gabinete extraídas,
                ou DataFrame vazio caso o deputado não possua gabinete ou a página retorne 404.
        """
        if deputado_id is None:
            return pl.DataFrame()

        target_url = f"{self.BASE_SCRAPER_URL}/{int(deputado_id)}/pessoal-gabinete"
        captured_at = datetime.now(timezone.utc).isoformat()

        try:
            html = await self._fetch_with_retry(target_url)
        except Exception as exc:
            logger.error(
                "Erro fatal ao requisitar página de gabinete para deputado %s (%s): %s",
                deputado_id,
                target_url,
                exc,
            )
            return pl.DataFrame()

        if not html:
            return pl.DataFrame()

        return parse_pessoal_gabinete_html(
            html=html,
            deputado_id=int(deputado_id),
            source_url=target_url,
            captured_at=captured_at,
        )
