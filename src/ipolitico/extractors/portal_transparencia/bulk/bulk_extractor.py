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
"""

import logging
from pathlib import Path
from typing import Optional

import polars as pl

from ipolitico.core.config import PORTAL_BULK_BASE_URL, PORTAL_BULK_DIR
from ipolitico.core.portal_transparencia_client import PortalTransparenciaClient
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor

logger = logging.getLogger(__name__)


class PortalTransparenciaBulkExtractor(BaseBulkExtractor):
    """
    Extrator de dumps bulk do Portal da Transparência (``download-de-dados``).

    Reusa todo o fluxo do ``BaseBulkExtractor`` (download → ZIP opcional →
    ``pl.read_csv`` → ``_source_url``), apenas trocando a construção da URL (por
    convenção de segmento, sem BULK_REGISTRY) e o diretório de download
    (persistente, para resume via Range header).
    """

    # Cache próprio da subclasse (o base consulta ``self._bulk_cache``): um
    # módulo "despesas" do portal não colide com o domínio "despesas" da Câmara
    # no cache compartilhado da classe base.
    _bulk_cache: dict[tuple[str, int | None, int | None], tuple[pl.DataFrame, int]] = {}

    def __init__(
        self,
        client: PortalTransparenciaClient,
        module: str = "",
        bulk_dir: Optional[Path | str] = None,
    ):
        """
        Inicializa o extrator do módulo bulk do portal.

        Args:
            client: Cliente HTTP do portal (o mesmo ``PortalTransparenciaClient``
                da API v3 — ``download_file`` faz o resume via Range).
            module: Módulo do portal (ex: ``"servidores"``, ``"orgaos"``). Vira o
                ``domain_name`` do ``BaseBulkExtractor`` (chave do cache).
            bulk_dir: Diretório persistente dos dumps. Default: ``PORTAL_BULK_DIR``
                do config (``data/portal_dumps``). O arquivo baixado sobrevive
                entre execuções para o resume via Range header.
        """
        super().__init__(client, domain_name=module)
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
        não existe no ``BULK_REGISTRY``, então a leitura do CSV usa os defaults
        (``utf8-lossy``, sem ``schema_overrides``); os contratos por módulo são
        travados nas fatias verticais (tracer bullet ``cg_orgaos``, etc.).

        Args:
            year: Ano de referência (opcional).
            month: Mês 1-12 (opcional).
            **kwargs: Parâmetros contextuais adicionais.

        Returns:
            pl.DataFrame bruto com ``_source_url`` como primeira coluna, ou
            DataFrame vazio em falha/ausência (404 → lista vazia).
        """
        return await super().extract(year=year, month=month, **kwargs)
