"""Extrator bulk do Portal da Transparência (CGU) — /download-de-dados.

O portal publica dumps ZIP/CSV por módulo em ``download-de-dados/{módulo}``:
sem ano/mês é o snapshot mais recente; com ``{YYYY}`` é a cobertura anual; com
``{YYYYMM}`` (um único segmento) é o dump mensal. A URL é construída por
convenção de segmento — não há registry de templates como na Câmara.

Diferente do bulk da Câmara (temp descartável), o portal baixa para um
**diretório persistente** (``PORTAL_BULK_DIR`` no config, ou ``bulk_dir`` no
construtor): o arquivo parcial sobrevive entre execuções e o
``PortalTransparenciaClient.download_file`` o retoma via Range header — defesa
contra o WAF que derruba conexões longas intermitentemente.

Dois overrides sobre o ``BaseBulkExtractor``:

1. **ZIP multi-CSV** (``_load_raw_df``): dumps mensais de ``servidores`` vêm como
   ZIP com vários CSVs (um por órgão). O override extrai TODOS os membros não-dir
   e concatena via ``pl.concat(how="diagonal_relaxed")`` — o base extrairia só o
   ``namelist()[0]`` e perderia o resto.
2. **WAF-gracioso** (``extract``): se o ``PortalTransparenciaClient`` levantar
   ``PortalTransparenciaWAFError`` (bloco AWS WAF — 403 + desafio JS no host de
   dumps, verificado real no ticket 03), o job NÃO cai: devolve DataFrame vazio
   e loga. Quando o WAF liberar, o mesmo job passa a baixar sem mudança de código.
"""

import logging
import os
import zipfile
from pathlib import Path
from typing import Optional

import polars as pl

from ipolitico.core.config import PORTAL_BULK_BASE_URL, PORTAL_BULK_DIR
from ipolitico.core.portal_transparencia_client import (
    PortalTransparenciaClient,
    PortalTransparenciaWAFError,
)
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor

logger = logging.getLogger(__name__)


class PortalTransparenciaBulkExtractor(BaseBulkExtractor):
    """
    Extrator de dumps bulk do Portal da Transparência (``download-de-dados``).

    Reusa todo o fluxo do ``BaseBulkExtractor`` (download → ZIP opcional →
    ``pl.read_csv`` → ``_source_url``), apenas trocando a construção da URL (por
    convenção de segmento, sem BULK_REGISTRY), o diretório de download
    (persistente, para resume via Range header), a leitura de ZIP multi-CSV
    (concatena todos os membros) e o tratamento WAF-gracioso.
    """

    # Cache próprio da subclasse (o base consulta ``self._bulk_cache``): um
    # módulo "despesas" do portal não colide com o domínio "despesas" da Câmara
    # no cache compartilhado da classe base.
    _bulk_cache: dict[tuple[str, int | None, int | None], tuple[pl.DataFrame, int]] = {}

    def __init__(
        self,
        client: PortalTransparenciaClient,
        module: str = "",
        domain_name: Optional[str] = None,
        bulk_dir: Optional[Path | str] = None,
    ):
        """
        Inicializa o extrator do módulo bulk do portal.

        ``domain_name`` e ``module`` são desacoplados: o runner injeta o domínio
        do pipeline (``cg_servidores``) enquanto a URL usa o segmento do portal
        (``servidores``) — a convenção de segmento pode diferir do nome do domínio
        (ex: ``cg_imoveis_funcionais`` → ``imoveis-funcionais``). O ``module`` é
        o segmento da URL; o ``domain_name`` é a chave do cache do
        ``BaseBulkExtractor`` (fallback para ``module`` quando ausente).

        Args:
            client: Cliente HTTP do portal (o mesmo ``PortalTransparenciaClient``
                da API v3 — ``download_file`` faz o resume via Range).
            module: Segmento do módulo no URL (ex: ``"servidores"``,
                ``"ceis"``). Usado em ``_build_url``.
            domain_name: Nome do domínio do pipeline (ex: ``"cg_servidores"``) —
                vira o ``domain_name`` do ``BaseBulkExtractor`` (chave do cache).
                Default: o próprio ``module`` (compat com a fundação do ticket 01).
            bulk_dir: Diretório persistente dos dumps. Default: ``PORTAL_BULK_DIR``
                do config (``data/portal_dumps``). O arquivo baixado sobrevive
                entre execuções para o resume via Range header.
        """
        super().__init__(client, domain_name=domain_name or module)
        self.module = module
        self.download_dir = Path(bulk_dir) if bulk_dir else Path(PORTAL_BULK_DIR)

    def _build_url(self, year: Optional[int] = None, month: Optional[int] = None) -> str:
        """
        Constrói a URL do dump por convenção de segmento do portal.

        Sem ano/mês → snapshot: ``download-de-dados/{módulo}``.
        Com ano → cobertura anual: ``download-de-dados/{módulo}/{YYYY}``.
        Com ano+mês → dump mensal (um segmento): ``download-de-dados/{módulo}/{YYYYMM}``.

        Args:
            year: Ano de referência (opcional — snapshot quando ausente).
            month: Mês 1-12 (opcional — exige ``year`` quando presente).

        Returns:
            URL completa do dump no padrão do portal.

        Raises:
            ValueError: Se ``month`` for fornecido sem ``year`` ou estiver fora
                de 1-12 (mesma regra defensiva do ``BaseBulkExtractor._build_url``).
        """
        if month is not None:
            if year is None:
                raise ValueError(f"month exige 'year' para o módulo do portal: {self.module}")
            if not 1 <= month <= 12:
                raise ValueError(f"Mês inválido para {self.module}: {month}. Esperado 1-12.")
        parts = [PORTAL_BULK_BASE_URL.rstrip("/"), self.module]
        if year:
            parts.append(str(year) + (f"{month:02d}" if month else ""))
        return "/".join(parts)

    async def extract(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        **kwargs,
    ) -> pl.DataFrame:
        """
        Baixa o dump do módulo e devolve o DataFrame bruto com ``_source_url``.

        Delega o fluxo ao ``BaseBulkExtractor.extract`` — o registro do portal
        não existe no ``BULK_REGISTRY`` (a entrada ``cg_remuneracoes`` existe
        apenas para o SourceRouter rotar bulk e o ``_read_single_csv`` ler
        encoding/schema_overrides), então a leitura do CSV usa os defaults
        (``utf8-lossy``, sem ``schema_overrides``); os contratos por módulo são
        travados nas fatias verticais (ex: ``cg_servidores``, ``cg_viagens``).

        Se o ``PortalTransparenciaClient`` levantar ``PortalTransparenciaWAFError``
        (bloco AWS WAF no host de dumps — 403 + desafio JS, não transitório),
        o job NÃO cai: loga e devolve DataFrame vazio (WAF-gracioso). Quando o
        WAF liberar, o mesmo job passa a baixar sem mudança de código.

        Args:
            year: Ano de referência (opcional).
            month: Mês 1-12 (opcional).
            **kwargs: Parâmetros contextuais adicionais.

        Returns:
            pl.DataFrame bruto com ``_source_url`` como primeira coluna, ou
            DataFrame vazio em falha/ausência (404 → lista vazia) ou bloqueio
            do WAF (``PortalTransparenciaWAFError`` → lista vazia).
        """
        try:
            return await super().extract(year=year, month=month, **kwargs)
        except PortalTransparenciaWAFError as e:
            ref = f"{year or ''} {month or ''}".strip()
            logger.warning(
                f"WAF bloqueou o dump de {self.module} ({ref}): {e} — devolvendo vazio "
                "(job WAF-gracioso; re-executa quando o host liberar)."
            )
            return pl.DataFrame()

    def _load_raw_df(self, dest_path: str, workdir: str, url: str) -> pl.DataFrame:
        """
        Carrega o dump do portal, concatenando TODOS os CSVs de um ZIP multi-CSV.

        Dumps mensais de ``servidores`` vêm como ZIP com vários CSVs (um por
        órgão) de colunas possivelmente distintas. O override extrai todos os
        membros não-diretório e concatena via ``pl.concat(how="diagonal_relaxed")``
        (colunas ausentes viram nulo). ZIP sem arquivos → DataFrame vazio.
        Arquivo não-ZIP (CSV direto) ou ZIP corrompido delega ao base; corpo
        HTML com 200 (página de erro do host) é detectado pelo primeiro byte e
        devolvido como vazio — o base só detectaria pela extensão ".zip".

        Args:
            dest_path: Caminho do arquivo baixado (pode ser ZIP ou CSV).
            workdir: Diretório de trabalho do download (para extração do ZIP).
            url: URL de origem do dump (vira ``_source_url`` no DataFrame).

        Returns:
            DataFrame bruto com ``_source_url`` como primeira coluna (concatenação
            de todos os CSVs do ZIP), ou DataFrame vazio em ZIP vazio/corrompido
            ou corpo não-ZIP (herda o tratamento do base).
        """
        if zipfile.is_zipfile(dest_path):
            try:
                dfs: list[pl.DataFrame] = []
                with zipfile.ZipFile(dest_path, "r") as zip_ref:
                    members = [m for m in zip_ref.namelist() if not m.endswith("/")]
                    if not members:
                        logger.warning(
                            f"ZIP vazio (sem arquivos) baixado de {url}. Devolvendo vazio."
                        )
                        return pl.DataFrame()

                    for name in members:
                        zip_ref.extract(name, workdir)
                        dfs.append(self._read_single_csv(os.path.join(workdir, name), url))
                return pl.concat(dfs, how="diagonal_relaxed")
            except zipfile.BadZipFile:
                logger.error(f"Arquivo ZIP corrompido baixado de {url}. Abortando.")
                return pl.DataFrame()

        # Corpo não-CSV com 200 (ex: página de erro do host). O base só detecta
        # pela extensão ".zip" (convenção de nome da Câmara); os dumps do portal
        # têm nome de segmento (ex: "202401"), sem extensão — um read_csv de HTML
        # injetaria lixo em dados append-only. Filtra pelo primeiro byte ("<").
        with open(dest_path, "rb") as f:
            if f.read(1) == b"<":
                logger.error(f"Corpo não-CSV recebido de {url} (HTML em vez de dump). Abortando.")
                return pl.DataFrame()
        return super()._load_raw_df(dest_path, workdir, url)
