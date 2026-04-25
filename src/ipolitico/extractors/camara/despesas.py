import logging
from datetime import datetime

import polars as pl

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class DespesasExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Despesas (Cota Parlamentar).

    A API da Câmara possui um limite rígido de itens por requisição e frequentemente
    retorna HTTP 400 (Bad Request) se a janela temporal de busca for muito ampla.
    Este extrator implementa um algoritmo de particionamento (Chunking) dinâmico,
    fatiando as buscas mes a mes para cada deputado, garantindo extração segura.
    """

    async def extract(
        self, deputados_ids: list[int] = None, start_date: str = None, end_date: str = None
    ) -> pl.DataFrame:
        """
        Orquestra a extração de despesas executando jobs mensais/anuais.

        Args:
            deputados_ids (list[int]): Lista de IDs dos deputados. Obrigatório.
            start_date (str): Data inicial no formato YYYY-MM-DD. Obrigatório.
            end_date (str): Data final no formato YYYY-MM-DD. Obrigatório.

        Returns:
            pl.DataFrame: DataFrame contendo as despesas filtradas e validadas.

        Raises:
            ValueError: Caso os limites temporais ou IDs não sejam fornecidos.
        """
        if not start_date or not end_date or not deputados_ids:
            raise ValueError(
                "Extrator de Despesas exige start_date, end_date e deputados_ids explícitos."
            )

        start_dt = datetime.strptime(start_date.split("T")[0], "%Y-%m-%d")
        end_dt = datetime.strptime(end_date.split("T")[0], "%Y-%m-%d")

        start_year, start_month = start_dt.year, start_dt.month
        end_year, end_month = end_dt.year, end_dt.month
        logger.debug(f"Sincronizando despesas do período: {start_date} a {end_date}")

        # Construção da matriz de processamento (Jobs Temporais)
        jobs = []
        for year in range(start_year, end_year + 1):
            months = (
                range(start_month, end_month + 1)
                if start_year == end_year
                else range(start_month, 13)
                if year == start_year
                else range(1, end_month + 1)
                if year == end_year
                else range(1, 13)
            )

            for d_id in deputados_ids:
                for month in months:
                    jobs.append({"id": d_id, "year": year, "month": month})

        # Definição da rotina operária estrita
        async def fetch_despesa_deputado(job: dict) -> pl.DataFrame:
            endpoint = f"{ApiRoutes.DEPUTADOS.value}/{job['id']}/despesas"

            raw_params = {
                ApiParams.ANO: job["year"],  # Correção Crítica: Sem colchetes
                ApiParams.MES: job["month"],
                ApiParams.ORDEM: ApiParams.ORDEM_ASC.value,
                ApiParams.ORDENAR_POR: "dataDocumento",
            }
            dados = await self.fetch_paginated(endpoint, self.build_params(raw_params))

            if not dados:
                return pl.DataFrame()

            # Injeção da Chave Estrangeira
            return pl.DataFrame(dados).with_columns(pl.lit(job["id"]).alias("id_deputado"))

        # Execução concorrente usando o motor do BaseExtractor
        df_final = await self.execute_concurrently(
            jobs,
            fetch_despesa_deputado,
            max_workers=MAX_CONCURRENT_REQUESTS,
            desc="Baixando Despesas",
        )

        # Transformação e filtro de precisão
        if not df_final.is_empty():
            df_final = df_final.filter(
                (pl.col("dataDocumento").str.slice(0, 10) >= start_date)
                & (pl.col("dataDocumento").str.slice(0, 10) <= end_date)
            )
            if df_final.is_empty():
                logger.warning("O filtro removeu todos os dados! Verifique os formatos de data.")
            else:
                logger.debug(f"{df_final.height} registros prontos para salvar.")
        else:
            logger.debug("ℹ Nenhuma despesa nova encontrada para os critérios informados.")

        return df_final
