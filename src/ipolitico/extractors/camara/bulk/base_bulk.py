import logging
import tempfile
from pathlib import Path

import polars as pl

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

    async def extract(self, year: int = None) -> pl.DataFrame:
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
                return pl.DataFrame()

            try:
                # infer_schema_length=0 força a leitura como String para evitar crashs
                df = pl.read_csv(
                    dest_path, separator=";", ignore_errors=True, infer_schema_length=0
                )

                # Invoca a tradução de colunas específica da classe filha
                df = self._standardize_schema(df)
                return df
            except Exception as e:
                logger.error(f"Falha ao ler o CSV de {self.domain_name}: {e}")
                return pl.DataFrame()
