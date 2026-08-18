import logging
import os
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

import polars as pl
import polars.selectors as cs

from ipolitico.core.camara_client import CamaraClient
from ipolitico.extractors.base import BaseExtractor
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

logger = logging.getLogger(__name__)


class BaseBulkExtractor(BaseExtractor):
    """
    Classe base para extratores de arquivos massivos (Dumps/Bulk) da Câmara.

    Garante o Princípio da Responsabilidade Única (SRP): foca estritamente
    em baixar o arquivo (CSV/ZIP), descompactar e carregar o DataFrame bruto em
    memória, sem aplicar padronizações de regras de negócio ou realizar persistência.

    A leitura do CSV utiliza ``schema_overrides`` do ``BULK_REGISTRY`` (se
    presentes) para tipar colunas conhecidas na origem, evitando o segundo passe
    de cast nos transformers. Colunas de moeda BR permanecem como ``pl.Utf8``
    para processamento posterior pelo helper ``convert_br_currency_columns``.

    Implementa cache de DataFrames por chave (domínio, ano, mês) para evitar
    downloads redundantes do mesmo arquivo CSV quando múltiplos jobs processam
    o mesmo snapshot (ex: 7275 jobs para deputados_frentes que baixam o mesmo
    CSV). O cache é compartilhado entre todos os domínios via dicionário de
    classe; cada entrada contém uma tupla (DataFrame, config_registry) para
    detectar mudanças de schema. Use ``clear_cache()`` para resetar entre
    execuções.
    """

    # Cache compartilhado: {(domain_name, year, month): (DataFrame, config_hash)}
    _bulk_cache: dict[tuple[str, int | None, int | None], tuple[pl.DataFrame, int]] = {}

    # Nomes de mês em português sem acento — convenção da fonte para URLs de
    # dumps mensais (ex: "marco", nunca "março"). Índice 0 = janeiro.
    _MONTH_NAMES = (
        "janeiro",
        "fevereiro",
        "marco",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )

    @classmethod
    def clear_cache(cls) -> None:
        """Limpa o cache de DataFrames. Útil entre execuções de pipeline."""
        cls._bulk_cache.clear()

    def __init__(self, client: CamaraClient, domain_name: str = ""):
        """
        Inicializa o extrator com seu cliente HTTP e nome de domínio.

        Args:
            client (CamaraClient): Cliente HTTP configurado para requisições e retries.
            domain_name (str): Nome do domínio para lookup no BULK_REGISTRY.
                Ex: "deputados", "despesas", "proposicoes", "votacoes", "votos".
        """
        self.client = client
        self.domain_name = domain_name
        # Diretório persistente para downloads bulk. None → diretório temporário
        # descartável por execução (comportamento original da Câmara). Quando
        # definido (ex: portal da transparência), o arquivo baixado sobrevive
        # entre execuções e o cliente pode retomá-lo via Range header.
        self.download_dir: Path | None = None

    @contextmanager
    def _download_workdir(self):
        """
        Context manager do diretório de trabalho do download do dump.

        Se ``download_dir`` for None (padrão da Câmara), usa um diretório
        temporário descartável por execução. Se for um ``Path`` (ex: portal da
        transparência), garante que o diretório persistente exista e o usa —
        o arquivo baixado fica em disco para o cliente retomar via Range header.

        Yields:
            str: Caminho do diretório de trabalho do download.
        """
        if self.download_dir is None:
            with tempfile.TemporaryDirectory() as tmpdir:
                yield tmpdir
        else:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            yield str(self.download_dir)

    def _build_url(self, year: Optional[int] = None, month: Optional[int] = None) -> str:
        """
        Constrói a URL de download com base no domínio, ano e mês fornecidos.

        Para domínios mensais (``requires_month``, ex: ``folha_pagamento``),
        o mês é obrigatório e é convertido para o nome por extenso sem acento
        (``marco``, não ``março``) — convenção da fonte.

        Args:
            year (int, optional): Ano de referência para arquivos particionados.
            month (int, optional): Mês (1-12) para arquivos mensais.

        Returns:
            str: URL formatada para download.

        Raises:
            ValueError: Se o domínio não está no registry, se um parâmetro
                obrigatório (year/month) estiver ausente, ou se o mês estiver
                fora de 1-12 (evita IndexError cru no `_MONTH_NAMES`).
        """
        config = BULK_REGISTRY.get(self.domain_name)
        if not config:
            raise ValueError(f"Domínio Bulk não mapeado no registry: {self.domain_name}")

        if config["requires_year"] and not year:
            raise ValueError(f"O domínio {self.domain_name} exige o parâmetro 'year'.")

        if config.get("requires_month"):
            if month is None:
                raise ValueError(f"O domínio {self.domain_name} exige o parâmetro 'month'.")
            if not 1 <= month <= 12:
                raise ValueError(f"Mês inválido para {self.domain_name}: {month}. Esperado 1-12.")
            month_name = self._MONTH_NAMES[month - 1]
            return config["url_template"].format(year=year, month=month_name)

        return (
            config["url_template"].format(year=year)
            if config["requires_year"]
            else config["url_template"]
        )

    async def extract(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Descarrega o arquivo estático, descompacta (se aplicável) e lê o CSV.

        Aplica ``schema_overrides`` do ``BULK_REGISTRY`` (se presentes) na chamada
        a ``pl.read_csv``, tipando colunas conhecidas diretamente na leitura.
        Colunas de moeda BR (ex: ``vlrLiquido``) são mantidas como ``pl.Utf8``
        para processamento posterior pelo helper ``convert_br_currency_columns``.
        A codificação é definida por domínio no ``BULK_REGISTRY`` (campo
        ``encoding``, padrão ``utf8-lossy``); o consolidado mensal da folha usa
        ``latin1`` (ISO-8859-1).

        Args:
            year (int, optional): Ano para particionamento do arquivo.
            month (int, optional): Mês (1-12) para arquivos mensais (obrigatório
                quando ``requires_month`` é True no registry).
            **kwargs: Parâmetros contextuais adicionais.

        Utiliza cache compartilhado (``_bulk_cache``) para evitar downloads
        redundantes do mesmo arquivo CSV quando múltiplos jobs processam o
        mesmo snapshot. O cache é chaveado por (domain_name, year, month) e
        inclui um hash da configuração do registro para invalidar em mudanças
        de schema.

        Returns:
            pl.DataFrame: DataFrame contendo os dados estritamente brutos,
                          com ``_source_url`` (URL de download do CSV) como
                          primeira coluna. Retorna um DataFrame vazio em caso
                          de falha ou arquivo inexistente (sem ``_source_url``).

        Raises:
            ValueError: Se ``requires_month`` estiver configurado e ``month``
                não for fornecido (mesma regra do ``_build_url``).
        """
        if not self.domain_name:
            raise NotImplementedError("domain_name deve ser fornecido no construtor.")

        # ── Cache hit: retorna clone do DataFrame em cache ────────────────
        cache_key: tuple[str, int | None, int | None] = (self.domain_name, year, month)
        # `self._bulk_cache` (não `BaseBulkExtractor._bulk_cache`): subclasses
        # (ex: portal da transparência) declaram o próprio dict de cache, então
        # um módulo "despesas" do portal não colide com o domínio "despesas" da
        # Câmara na mesma classe.
        cached = self._bulk_cache.get(cache_key)
        if cached is not None:
            df_cached, _ = cached
            logger.debug(
                f"[{self.domain_name}] Cache hit para '{cache_key}', "
                f"reutilizando {len(df_cached)} linhas."
            )
            return df_cached.clone()

        url = self._build_url(year, month)

        with self._download_workdir() as workdir:
            file_name = url.split("/")[-1]
            dest_path = str(Path(workdir) / file_name)

            ref = f"{year or ''} {month or ''}".strip()
            logger.info(f"Baixando Dump Estático ({self.domain_name} {ref})...")

            success = await self.client.download_file(url, dest_path)

            if not success:
                logger.warning(f"Dump de {self.domain_name} para {ref} não existe no servidor.")
                return pl.DataFrame()

            # Detecta ZIP pelo magic byte, não pela extensão: o portal da
            # transparência baixa dumps cujo nome é só o segmento (ex: "202401",
            # sem ".zip").
            if zipfile.is_zipfile(dest_path):
                try:
                    with zipfile.ZipFile(dest_path, "r") as zip_ref:
                        csv_filename = zip_ref.namelist()[0]
                        zip_ref.extract(csv_filename, workdir)
                        dest_path = os.path.join(workdir, csv_filename)
                except zipfile.BadZipFile:
                    logger.error(f"Arquivo ZIP corrompido baixado de {url}. Abortando.")
                    return pl.DataFrame()
            # URL terminada em ".zip" mas com corpo não-ZIP (ex: página de erro do
            # servidor): loga a origem e devolve vazio — não deixa o corpo vazar
            # para o read_csv (evita linhas-lixo em vez de lista vazia).
            elif dest_path.endswith(".zip"):
                with open(dest_path, "r", encoding="utf-8", errors="ignore") as f:
                    fake_content = f.read(150).replace("\n", " ")
                logger.error(f"Arquivo corrompido recebido em vez de ZIP: '{fake_content}...'")
                return pl.DataFrame()

            try:
                config_registry = BULK_REGISTRY.get(self.domain_name, {})
                df = pl.read_csv(
                    dest_path,
                    separator=";",
                    ignore_errors=True,
                    infer_schema_length=0,
                    encoding=config_registry.get("encoding", "utf8-lossy"),
                    truncate_ragged_lines=True,
                    quote_char=None,
                    schema_overrides=config_registry.get("schema_overrides"),
                )

                df = df.rename(
                    {
                        c: c.replace("ï»¿", "").replace("\ufeff", "").replace('"', "").strip()
                        for c in df.columns
                    }
                )
                df = df.with_columns(cs.string().str.replace_all('"', "").str.strip_chars())

                rename_map = config_registry.get("rename_map", {})
                if rename_map:
                    existing = {k: v for k, v in rename_map.items() if k in df.columns}
                    if existing:
                        df = df.rename(existing)

                # ── _source_url: URL de download do CSV (audit trail) ─────
                df = df.with_columns(pl.lit(url).alias("_source_url").cast(pl.String))
                df = df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])

                # ── Popula cache antes de retornar ────────────────────────
                config_hash = hash(str(config_registry))
                self._bulk_cache[cache_key] = (df.clone(), config_hash)
                logger.debug(
                    f"[{self.domain_name}] Cache armazenado para '{cache_key}' ({len(df)} linhas)."
                )

                return df

            except Exception as e:
                logger.error(f"Falha crítica ao realizar o parse do CSV de {self.domain_name}: {e}")
                return pl.DataFrame()
