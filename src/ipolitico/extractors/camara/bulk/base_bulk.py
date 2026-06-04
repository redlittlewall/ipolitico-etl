import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

import polars as pl
import polars.selectors as cs

from ipolitico.core.client import CamaraClient
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
    """

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

    def _build_url(self, year: Optional[int] = None) -> str:
        """
        Constrói a URL de download com base no domínio e ano fornecidos.

        Args:
            year (int, optional): Ano de referência para arquivos particionados.

        Returns:
            str: URL formatada para download.
        """
        config = BULK_REGISTRY.get(self.domain_name)
        if not config:
            raise ValueError(f"Domínio Bulk não mapeado no registry: {self.domain_name}")

        if config["requires_year"] and not year:
            raise ValueError(f"O domínio {self.domain_name} exige o parâmetro 'year'.")

        return (
            config["url_template"].format(year=year)
            if config["requires_year"]
            else config["url_template"]
        )

    async def extract(self, year: Optional[int] = None, **kwargs: Any) -> pl.DataFrame:
        """
        Descarrega o arquivo estático, descompacta (se aplicável) e lê o CSV.

        Aplica ``schema_overrides`` do ``BULK_REGISTRY`` (se presentes) na chamada
        a ``pl.read_csv``, tipando colunas conhecidas diretamente na leitura.
        Colunas de moeda BR (ex: ``vlrLiquido``) são mantidas como ``pl.Utf8``
        para processamento posterior pelo helper ``convert_br_currency_columns``.

        Args:
            year (int, optional): Ano para particionamento do arquivo.
            **kwargs: Parâmetros contextuais adicionais.

        Returns:
            pl.DataFrame: DataFrame contendo os dados estritamente brutos.
                          Retorna um DataFrame vazio em caso de falha ou arquivo inexistente.
        """
        if not self.domain_name:
            raise NotImplementedError("domain_name deve ser fornecido no construtor.")

        url = self._build_url(year)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_name = url.split("/")[-1]
            dest_path = str(Path(tmpdir) / file_name)

            logger.info(f"Baixando Dump Estático ({self.domain_name} {year or ''})...")

            success = await self.client.download_file(url, dest_path)

            if not success:
                logger.warning(f"Dump de {self.domain_name} para {year} não existe no servidor.")
                return pl.DataFrame()

            if dest_path.endswith(".zip"):
                if not zipfile.is_zipfile(dest_path):
                    with open(dest_path, "r", encoding="utf-8", errors="ignore") as f:
                        fake_content = f.read(150).replace("\n", " ")
                    logger.error(f"Arquivo corrompido recebido em vez de ZIP: '{fake_content}...'")
                    return pl.DataFrame()
                try:
                    with zipfile.ZipFile(dest_path, "r") as zip_ref:
                        csv_filename = zip_ref.namelist()[0]
                        zip_ref.extract(csv_filename, tmpdir)
                        dest_path = os.path.join(tmpdir, csv_filename)
                except zipfile.BadZipFile:
                    logger.error(f"Arquivo ZIP corrompido baixado de {url}. Abortando.")
                    return pl.DataFrame()

            try:
                config_registry = BULK_REGISTRY.get(self.domain_name, {})
                df = pl.read_csv(
                    dest_path,
                    separator=";",
                    ignore_errors=True,
                    infer_schema_length=0,
                    encoding="utf8-lossy",
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

                return df

            except Exception as e:
                logger.error(f"Falha crítica ao realizar o parse do CSV de {self.domain_name}: {e}")
                return pl.DataFrame()
