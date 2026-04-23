import logging
from datetime import datetime

import polars as pl

from ipolitico.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class DespesasExtractor(BaseExtractor):
    """
    Extrator de despesas (Cota Parlamentar).
    Delega o controle de paginação e concorrência para a BaseExtractor.
    """

    async def extract(
        self, deputados_ids: list, data_inicio: str = None, data_fim: str = None
    ) -> pl.DataFrame:
        # Definição do Ponto de Partida e Chegada
        if not data_inicio:
            data_inicio = self._get_last_watermark("despesas", "dataDocumento") or "2023-02-01"
        if not data_fim:
            data_fim = datetime.now().strftime("%Y-%m-%d")

        dt_ini = datetime.strptime(data_inicio.split("T")[0], "%Y-%m-%d")
        dt_fim = datetime.strptime(data_fim.split("T")[0], "%Y-%m-%d")

        ano_ini, mes_ini = dt_ini.year, dt_ini.month
        ano_fim, mes_fim = dt_fim.year, dt_fim.month

        logger.info(f"Sincronizando despesas de {data_inicio} até {data_fim}...")

        # Construindo a "Lista de Tarefas" (Jobs) para o motor da Base
        trabalhos = []
        for ano in range(ano_ini, ano_fim + 1):
            if ano == ano_ini and ano == ano_fim:
                meses = list(range(mes_ini, mes_fim + 1))
            elif ano == ano_ini:
                meses = list(range(mes_ini, 13))
            elif ano == ano_fim:
                meses = list(range(1, mes_fim + 1))
            else:
                meses = list(range(1, 13))

            if not meses:
                continue

            # Adiciona um "job" para cada deputado naquele ano/mês
            for d_id in deputados_ids:
                trabalhos.append({"id": d_id, "ano": ano, "meses": meses})

        # Definimos a Função Operária (O que fazer com cada Job)
        async def fetch_despesa_deputado(job: dict) -> pl.DataFrame:
            endpoint = f"deputados/{job['id']}/despesas"
            params = {
                "ano": [job["ano"]],
                "mes": job["meses"],
                "ordem": "ASC",
                "ordenarPor": "dataDocumento",
            }

            try:
                dados = await self.fetch_paginated(endpoint, params)
                if not dados:
                    return pl.DataFrame()
                return pl.DataFrame(dados).with_columns(pl.lit(job["id"]).alias("id_deputado"))
            except Exception:
                return pl.DataFrame()

        # Execução Concorrente via BaseExtractor
        # A base recebe a lista de jobs e a função, e roda tudo com semáforo
        df_final = await self.execute_concurrently(
            trabalhos, fetch_despesa_deputado, max_workers=10
        )

        # Sintonia Fina com Polars
        if not df_final.is_empty():
            df_final = df_final.filter(
                (pl.col("dataDocumento") >= data_inicio) & (pl.col("dataDocumento") <= data_fim)
            )
            logger.info(f"{df_final.height} despesas extraídas e filtradas com sucesso.")
        else:
            logger.info("ℹNenhuma despesa nova encontrada para o período.")

        return df_final
