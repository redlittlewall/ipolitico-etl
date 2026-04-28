import logging
from datetime import datetime

import polars as pl

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class ProposicoesExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Proposições Legislativas.

    Busca Projetos de Lei, PECs, Requerimentos e outras matérias. Devido ao volume massivo,
    a extração é obrigatoriamente particionada por ano para evitar timeouts da infraestrutura
    governamental.
    """

    async def extract(self, start_date: str, end_date: str) -> pl.DataFrame:
        """
        Executa a extração de proposições numa janela de tempo estrita.

        Args:
            start_date (str): Data de início (YYYY-MM-DD). Obrigatório.
            end_date (str): Data de fim (YYYY-MM-DD). Obrigatório.

        Returns:
            pl.DataFrame: DataFrame contendo as proposições do período filtrado.
        """
        if not start_date or not end_date:
            raise ValueError("O Extrator de Proposições exige limites temporais explícitos.")

        dt_ini = datetime.strptime(start_date.split("T")[0], "%Y-%m-%d")
        dt_fim = datetime.strptime(end_date.split("T")[0], "%Y-%m-%d")

        logger.debug(f"Sincronizando Proposições: {start_date} a {end_date}")

        anos = list(range(dt_ini.year, dt_fim.year + 1))

        async def fetch_proposicoes_ano(ano: int) -> pl.DataFrame:
            raw_params = {
                ApiParams.ANO: ano,
                ApiParams.ORDEM: ApiParams.ORDEM_ASC.value,
                ApiParams.ORDENAR_POR: "id",
            }
            dados = await self.fetch_paginated(
                ApiRoutes.PROPOSICOES.value, self.build_params(raw_params)
            )
            return pl.DataFrame(dados) if dados else pl.DataFrame()

        df_final = await self.execute_concurrently(
            anos,
            fetch_proposicoes_ano,
            max_workers=MAX_CONCURRENT_REQUESTS,
            desc="Baixando Proposições",
        )

        if not df_final.is_empty():
            df_final = df_final.filter(
                (pl.col("dataApresentacao").str.slice(0, 10) >= start_date)
                & (pl.col("dataApresentacao").str.slice(0, 10) <= end_date)
            )
            logger.debug(f"{df_final.height} proposições processadas.")

        return df_final
