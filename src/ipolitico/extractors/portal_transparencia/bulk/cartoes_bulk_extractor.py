"""Extrator bulk do domínio cg_cartoes — dumps mensais multi-módulo (CPGF/CPCC/CPDC).

ROTA DUPLA (exigência explícita do ticket 04): em FULL_LOAD o histórico de
cartões vem do bulk mensal do portal. Diferente dos outros módulos (1 módulo por
domínio), os cartões de pagamento são publicados em TRÊS módulos distintos —
``cpgf`` (Cartão de Pagamento da GF), ``cpcc`` (Cartão de Compras Corporativo) e
``cpdc`` (Cartão de Diárias e Compras) — cada um em ``/download-de-dados/{módulo}/
{YYYYMM}`` (ZIP/CSV latin-1). Validação real: alguns meses não publicam todos os
módulos (cpcc frequentemente ausente → 403 AccessDenied do S3, que o cliente
trata como ``False`` de ausência) → o extrator pula o módulo faltante e concatena
os demais (``pl.concat(how="diagonal_relaxed")`` — os CSVs têm colunas
heterogêneas; as colunas extras do cpdc, convênio, ficam fora do contrato).

Cache PRÓPRIO por ``(module, year, month)``: o cache do ``BaseBulkExtractor`` é
por domínio e colidiria entre os módulos (mesmo domínio cg_cartoes, dumps
diferentes).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import polars as pl

from ipolitico.core.config import PORTAL_BULK_BASE_URL, PORTAL_BULK_DIR
from ipolitico.core.portal_transparencia_client import (
    PortalTransparenciaAPIError,
    PortalTransparenciaClient,
    PortalTransparenciaWAFError,
)
from ipolitico.extractors.portal_transparencia.bulk.bulk_extractor import (
    PortalTransparenciaBulkExtractor,
)

logger = logging.getLogger(__name__)


class PortalCartoesBulkExtractor(PortalTransparenciaBulkExtractor):
    """
    Extrator dos dumps mensais de cartões de pagamento (cpgf/cpcc/cpdc).

    Estende o ``PortalTransparenciaBulkExtractor`` apenas na extração: baixa UM
    dump por módulo do mês (janela ``{"year", "month"}`` do
    ``MonthlyBulkStrategy``), pula módulos indisponíveis graciosamente (ausência
    403-AccessDenied→False, WAF ou 403 genérico) e concatena os CSVs dos
    módulos presentes. ``_build_url`` herdado é substituído por
    ``_build_module_url`` (URL por módulo, mesma convenção de segmento).
    """

    # Cache próprio da subclasse (chave por módulo, não por domínio): o cache do
    # base colidiria entre cpgf/cpcc/cpdc (mesmo domínio, dumps diferentes).
    _module_cache: dict[tuple[str, int, int], pl.DataFrame] = {}

    def __init__(
        self,
        client: PortalTransparenciaClient,
        domain_name: Optional[str] = None,
        modules: Optional[list[str]] = None,
        bulk_dir: Optional[Path | str] = None,
    ):
        """
        Inicializa o extrator multi-módulo de cartões.

        Args:
            client: Cliente HTTP do portal (``download_file`` faz o resume via
                Range e trata 403-AccessDenied como ausência).
            domain_name: Nome do domínio do pipeline (``cg_cartoes``) — chave do
                registry (encoding/schema do CSV). Default: herdado do base.
            modules: Módulos bulk a baixar por mês. Default: os três reais
                (``["cpgf", "cpcc", "cpdc"]``) — o kwarg do YAML.
            bulk_dir: Diretório persistente dos dumps. Default: ``PORTAL_BULK_DIR``.
        """
        super().__init__(client, domain_name=domain_name)
        self.modules = list(modules) if modules else ["cpgf", "cpcc", "cpdc"]
        self.download_dir = Path(bulk_dir) if bulk_dir else Path(PORTAL_BULK_DIR)

    def _build_module_url(self, module: str, year: int, month: int) -> str:
        """
        Constrói a URL do dump mensal de um módulo por convenção de segmento.

        Args:
            module: Módulo do portal (``cpgf``/``cpcc``/``cpdc``).
            year: Ano de referência.
            month: Mês 1-12.

        Returns:
            URL ``/download-de-dados/{module}/{YYYYMM}``.

        Raises:
            ValueError: Se ``year``/``month`` ausentes ou ``month`` fora de 1-12.
        """
        if year is None or month is None:
            raise ValueError(f"Cartões exigem year e month para o dump de {module}.")
        if not 1 <= month <= 12:
            raise ValueError(f"Mês inválido para {module}: {month}. Esperado 1-12.")
        return f"{PORTAL_BULK_BASE_URL.rstrip('/')}/{module}/{year}{month:02d}"

    async def extract(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        **kwargs,
    ) -> pl.DataFrame:
        """
        Baixa os dumps mensais de TODOS os módulos presentes e concatena.

        Para cada módulo configurado, baixa ``/download-de-dados/{module}/{YYYYMM}``
        e concatena via ``pl.concat(how="diagonal_relaxed")`` (colunas
        heterogêneas — as extras do cpdc ficam fora do contrato Silver). Módulo
        indisponível (403-AccessDenied do S3 → ``download_file`` retorna False,
        WAF → ``PortalTransparenciaWAFError``, ou 403 genérico do host →
        ``PortalTransparenciaAPIError`` com ``status_code=403``) é logado e
        PULADO — os demais módulos seguem. Sem nenhum módulo disponível →
        DataFrame vazio.

        Args:
            year: Ano do mês (ex: 2026).
            month: Mês 1-12 (ex: 6).
            **kwargs: Argumentos contextuais adicionais.

        Returns:
            DataFrame bruto concatenado com ``_source_url`` como primeira
            coluna, ou DataFrame vazio se nenhum módulo publicou o mês.

        Raises:
            ValueError: Se ``year``/``month`` ausentes — o dump de um módulo
                não tem URL sem a janela (mesma regra do ``_build_module_url``
                e da rota API gêmea).
        """
        dfs: list[pl.DataFrame] = []
        for module in self.modules:
            key = (module, year, month)
            if key in self._module_cache:
                cached = self._module_cache[key]
                if not cached.is_empty():
                    dfs.append(cached.clone())
                continue

            df = await self._extract_module(module, year, month)
            self._module_cache[key] = df.clone()
            if not df.is_empty():
                dfs.append(df)

        if not dfs:
            return pl.DataFrame()
        return pl.concat(dfs, how="diagonal_relaxed")

    async def _extract_module(self, module: str, year: int, month: int) -> pl.DataFrame:
        """
        Baixa e lê o dump mensal de um único módulo (cache à parte).

        Args:
            module: Módulo do portal (``cpgf``/``cpcc``/``cpdc``).
            year: Ano do mês.
            month: Mês 1-12.

        Returns:
            DataFrame bruto do módulo, ou DataFrame vazio em ausência
            (403-AccessDenied → ``download_file`` False) ou bloqueio WAF
            (``PortalTransparenciaWAFError``) — módulo indisponível é pulado,
            não derruba o job.
        """
        try:
            url = self._build_module_url(module, year, month)
            dest = self.download_dir / f"{module}_{year}{month:02d}"
            ok = await self.client.download_file(url, str(dest))
            if not ok:
                logger.warning(
                    f"Módulo {module} {year}{month:02d} não publicado (dump ausente). Pulando."
                )
                return pl.DataFrame()
            return self._load_raw_df(str(dest), str(self.download_dir), url)
        except PortalTransparenciaWAFError as e:
            logger.warning(
                f"WAF bloqueou o dump de {module} {year}{month:02d}: {e} — pulando "
                "o módulo (os demais seguem; re-executa quando o host liberar)."
            )
            return pl.DataFrame()
        except PortalTransparenciaAPIError as e:
            if e.status_code != 403:
                raise
            # 403 do host de dumps SEM os marcadores (WAF/XML AccessDenied, que o
            # cliente já resolveu antes) — módulo indisponível por outra razão.
            # Pula o módulo (plano §4.4): um mês sem arquivo não derruba o job;
            # autorização real (401/403 da API, sem 403 no download) continua fatal.
            logger.warning(
                f"403 ao baixar {module} {year}{month:02d}: {e} — pulando o módulo "
                "(os demais seguem)."
            )
            return pl.DataFrame()
