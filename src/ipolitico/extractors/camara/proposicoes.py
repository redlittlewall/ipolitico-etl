import logging
from datetime import datetime

import polars as pl

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class ProposicoesExtractor(CamaraBaseExtractor):
    """
    Extrator de Proposições (Projetos de Lei, PECs, Requerimentos).
    """

    async def extract(self, data_inicio: str = None, data_fim: str = None) -> pl.DataFrame:
        """
        Extrai as proposições. Como o volume é colossal, o fatiamento por ano é obrigatório.
        """
        if not data_inicio:
            data_inicio = (
                self._get_last_watermark("proposicoes", "dataApresentacao") or "2023-01-01"
            )
        if not data_fim:
            data_fim = datetime.now().strftime("%Y-%m-%d")

        dt_ini = datetime.strptime(data_inicio.split("T")[0], "%Y-%m-%d")
        dt_fim = datetime.strptime(data_fim.split("T")[0], "%Y-%m-%d")

        logger.info(f"Sincronizando Proposições do período: {data_inicio} a {data_fim}")

        # Fatiamento anual (Proposições funcionam bem fatiadas apenas por ano)
        anos = list(range(dt_ini.year, dt_fim.year + 1))

        async def fetch_proposicoes_ano(ano: int) -> pl.DataFrame:
            raw_params = {
                ApiParams.ANO: [ano],
                ApiParams.ORDEM: ApiParams.ORDEM_ASC,
                ApiParams.ORDENAR_POR: "id",
            }
            try:
                dados = await self.fetch_paginated(
                    ApiRoutes.PROPOSICOES, self.build_params(raw_params)
                )
                return pl.DataFrame(dados) if dados else pl.DataFrame()
            except Exception as e:
                logger.debug(f"Falha ao buscar proposições de {ano}: {e}")
                return pl.DataFrame()

        # Execução concorrente dos anos
        df_final = await self.execute_concurrently(
            anos, fetch_proposicoes_ano, max_workers=MAX_CONCURRENT_REQUESTS
        )

        # Filtro de precisão em memória
        if not df_final.is_empty() and "dataApresentacao" in df_final.columns:
            df_final = df_final.filter(
                (pl.col("dataApresentacao") >= data_inicio)
                & (pl.col("dataApresentacao") <= data_fim)
            )
            logger.info(f"{df_final.height} proposições extraídas.")
        else:
            logger.info("ℹNenhuma proposição nova no período.")

        return df_final
