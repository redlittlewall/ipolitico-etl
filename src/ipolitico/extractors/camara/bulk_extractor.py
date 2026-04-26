import logging
import tempfile
from pathlib import Path

import polars as pl

from ipolitico.core.client import CamaraClient

logger = logging.getLogger(__name__)


class CamaraBulkExtractor:
    """
    Extrator de Carga Massiva (Dumps).
    Consome os arquivos estáticos (CSV/ZIP) da Câmara para cargas históricas de
    alta velocidade, contornando os limites de paginação da API Rest.
    """

    def __init__(self, client: CamaraClient):
        self.client = client
        self.base_api_url = "http://dadosabertos.camara.leg.br/arquivos"
        self.base_cotas_url = "http://www.camara.leg.br/cotas"

    def _build_url(self, domain: str, year: int = None) -> str:
        """Resolve as regras de negócio de URLs mapeadas na documentação oficial."""
        if domain == "deputados":
            return f"{self.base_api_url}/deputados/csv/deputados.csv"

        if domain == "despesas":
            # A exceção à regra: Fica num domínio antigo e exige ZIP
            return f"{self.base_cotas_url}/Ano-{year}.csv.zip"

        # Regra geral para Proposições, Votações e Votos
        domain_map = {
            "proposicoes": "proposicoes",
            "votacoes": "votacoes",
            "votos": "votacoesVotos",
        }

        if domain not in domain_map:
            raise ValueError(f"Domínio Bulk não mapeado: {domain}")

        tema = domain_map[domain]
        return f"{self.base_api_url}/{tema}/csv/{tema}-{year}.csv"

    async def extract(self, domain: str, year: int = None) -> pl.DataFrame:
        """
        Faz o download do dump estático e carrega em um DataFrame Polars.

        Args:
            domain (str): O domínio de dados (ex: 'despesas', 'votacoes').
            year (int, optional): O ano alvo. Nulo apenas para domínios atemporais (deputados).
        """
        url = self._build_url(domain, year)

        # Cria um diretório temporário que se auto-destrói após o uso
        with tempfile.TemporaryDirectory() as tmpdir:
            file_name = url.split("/")[-1]
            dest_path = str(Path(tmpdir) / file_name)

            logger.info(f"     ∟ Baixando Dump Estático ({domain} {year or ''})...")

            sucesso = await self.client.download_file(url, dest_path)

            if not sucesso:
                logger.warning(f"Dump de {domain} para o ano {year} não existe no servidor.")
                return pl.DataFrame()

            logger.info("     ∟ Lendo dados com Polars...")

            # O Polars é inteligente o suficiente para ler CSVs zipados se a extensão for .zip
            try:
                # separator=";" é o padrão comum do governo brasileiro em CSVs
                df = pl.read_csv(
                    dest_path, separator=";", ignore_errors=True, infer_schema_length=10000
                )
            except Exception as e:
                logger.error(f"Falha ao ler o CSV de {domain}: {e}")
                return pl.DataFrame()

            # TODO: Fase 2 - Opcional.
            # Como a API e o CSV às vezes tem nomes de colunas diferentes
            # (ex: txNomeParlamentar vs nome),
            # aqui seria o local perfeito para um bloco de rename() para garantir que
            # o DataLake receba o schema idêntico, independentemente se veio da API ou do Bulk.

            return df
