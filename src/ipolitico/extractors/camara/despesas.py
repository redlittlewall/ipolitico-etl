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
    Implementa particionamento temporal dinâmico para otimização de requisições HTTP
    e evasão de erros 400.
    """

    async def extract(
        self, deputados_ids: list[int], data_inicio: str = None, data_fim: str = None
    ) -> pl.DataFrame:
        """
        Orquestra a extração de despesas executando chunks mensais/anuais.
        """
        # Resolução de limites temporais (Carga Incremental vs Carga Histórica/Específica)
        if not data_inicio:
            data_inicio = self._get_last_watermark("despesas", "dataDocumento") or "2023-02-01"
        if not data_fim:
            data_fim = datetime.now().strftime("%Y-%m-%d")

        dt_ini = datetime.strptime(data_inicio.split("T")[0], "%Y-%m-%d")
        dt_fim = datetime.strptime(data_fim.split("T")[0], "%Y-%m-%d")

        ano_ini, mes_ini = dt_ini.year, dt_ini.month
        ano_fim, mes_fim = dt_fim.year, dt_fim.month

        logger.info(f"Sincronizando despesas do período: {data_inicio} a {data_fim}")

        # Construção da matriz de processamento (Jobs)
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

            for d_id in deputados_ids:
                trabalhos.append({"id": d_id, "ano": ano, "meses": meses})

        # Definição da rotina operária
        async def fetch_despesa_deputado(job: dict) -> pl.DataFrame:
            endpoint = f"{ApiRoutes.DEPUTADOS}/{job['id']}/despesas"

            raw_params = {
                ApiParams.ANO: [job["ano"]],
                ApiParams.MES: job["meses"],
                ApiParams.ORDEM: ApiParams.ORDEM_ASC,
                ApiParams.ORDENAR_POR: "dataDocumento",
            }

            try:
                # Delega paginação para a classe base
                dados = await self.fetch_paginated(endpoint, self.build_params(raw_params))
                if not dados:
                    return pl.DataFrame()

                return pl.DataFrame(dados).with_columns(pl.lit(job["id"]).alias("id_deputado"))
            except Exception as e:
                logger.debug(f"Processamento vazio/falho para o job {job}: {e}")
                return pl.DataFrame()

        # Execução concorrente
        df_final = await self.execute_concurrently(
            trabalhos, fetch_despesa_deputado, max_workers=MAX_CONCURRENT_REQUESTS
        )

        # Transformação e filtro de precisão
        if not df_final.is_empty():
            df_final = df_final.filter(
                (pl.col("dataDocumento") >= data_inicio) & (pl.col("dataDocumento") <= data_fim)
            )
            logger.info(f"Pipeline concluído: {df_final.height} despesas processadas no período.")
        else:
            logger.info("ℹNenhuma despesa nova encontrada para os critérios informados.")

        return df_final
