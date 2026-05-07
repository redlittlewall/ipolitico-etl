import logging
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import polars as pl
import polars.selectors as cs

from ipolitico.core.client import CamaraClient
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

logger = logging.getLogger(__name__)


class BaseBulkExtractor:
    """
    Classe base para extratores de Dumps massivos.
    Implementa o Design Pattern 'Template Method': a extração é genérica,
    mas a tradução de schema (padronização de colunas) é delegada aos filhos.
    """

    domain_name = ""  # Deve ser sobrescrito nas classes filhas (ex: "despesas")

    def __init__(self, client: CamaraClient):
        self.client = client

    def _build_url(self, year: int = None) -> str:
        config = BULK_REGISTRY.get(self.domain_name)
        if not config:
            raise ValueError(f"Domínio Bulk não mapeado no registry: {self.domain_name}")

        if config["requires_year"] and not year:
            raise ValueError(f"O domínio {self.domain_name} exige o parâmetro 'year'.")

        return config["url"].format(year=year) if config["requires_year"] else config["url"]

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        """Método de tradução. Retorna o DF intocado por padrão."""
        return df

    async def extract(
        self, sink_func, unique_keys: str | list[str] | None = None, year: int = None
    ) -> None:
        """
        Descarrega o Dump estático e processa-o via Disk-to-Database Streaming.
        Lê o CSV em lotes (batches) para garantir consumo mínimo de RAM.
        """

        if not self.domain_name:
            raise NotImplementedError("domain_name deve ser definido na classe filha.")

        url = self._build_url(year)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_name = url.split("/")[-1]
            dest_path = str(Path(tmpdir) / file_name)

            logger.info(f"     ∟ Baixando Dump Estático ({self.domain_name} {year or ''})...")

            sucesso = await self.client.download_file(url, dest_path)

            if not sucesso:
                logger.warning(f"Dump de {self.domain_name} para {year} não existe no servidor.")
                return

            if dest_path.endswith(".zip"):
                if not zipfile.is_zipfile(dest_path):
                    with open(dest_path, "r", encoding="utf-8", errors="ignore") as f:
                        conteudo_falso = f.read(150).replace("\n", " ")
                    logger.error(
                        f"O servidor enviou um arquivo corrompido/bloqueado em vez do ZIP:"
                        f" '{conteudo_falso}...'"
                    )
                    return
                try:
                    with zipfile.ZipFile(dest_path, "r") as zip_ref:
                        csv_filename = zip_ref.namelist()[0]
                        zip_ref.extract(csv_filename, tmpdir)
                        dest_path = os.path.join(tmpdir, csv_filename)
                except zipfile.BadZipFile:
                    logger.error(f"Arquivo ZIP corrompido baixado de {url}. Abortando.")
                    return
            try:
                df = pl.read_csv(
                    dest_path,
                    separator=";",
                    ignore_errors=True,
                    infer_schema_length=0,
                    encoding="utf8-lossy",
                    truncate_ragged_lines=True,
                    quote_char=None,
                )

                df = df.rename(
                    {
                        c: c.replace("ï»¿", "").replace("\ufeff", "").replace('"', "").strip()
                        for c in df.columns
                    }
                )
                df = df.with_columns(cs.string().str.replace_all('"', "").str.strip_chars())

                df = self._standardize_schema(df)
                agora = datetime.now()
                df = df.with_columns(
                    [
                        pl.lit(agora).cast(pl.Datetime).alias("captured_at"),
                        pl.lit(agora).cast(pl.Datetime).alias("updated_at"),
                    ]
                )

                await sink_func(df, self.domain_name, unique_keys)

            except Exception as e:
                logger.error(f"Falha crítica ao parsear o CSV de {self.domain_name}: {e}")
