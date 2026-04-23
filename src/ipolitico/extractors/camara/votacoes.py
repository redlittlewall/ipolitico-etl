import logging
from datetime import datetime

import polars as pl

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class VotacoesExtractor(CamaraBaseExtractor):
    """
    Extrator de Votações da Câmara dos Deputados.
    """

    async def extract(self, data_inicio: str = None, data_fim: str = None) -> pl.DataFrame:
        """
        Orquestra a extração dividindo a janela temporal solicitada em blocos anuais de requisição.
        """
        if not data_inicio:
            data_inicio = self._get_last_watermark("votacoes", "data") or "2023-01-01"
        if not data_fim:
            data_fim = datetime.now().strftime("%Y-%m-%d")

        dt_ini = datetime.strptime(data_inicio.split("T")[0], "%Y-%m-%d")
        dt_fim = datetime.strptime(data_fim.split("T")[0], "%Y-%m-%d")

        logger.info(f"Sincronizando Votações do período: {data_inicio} a {data_fim}")

        anos = list(range(dt_ini.year, dt_fim.year + 1))

        async def fetch_votacoes_ano(ano: int) -> pl.DataFrame:
            # Delimita as bordas temporais de cada bloco (ano) processado
            start_date = f"{ano}-01-01" if ano > dt_ini.year else data_inicio
            end_date = f"{ano}-12-31" if ano < dt_fim.year else data_fim

            raw_params = {
                ApiParams.DATA_INICIO: start_date,
                ApiParams.DATA_FIM: end_date,
                ApiParams.ORDEM: ApiParams.ORDEM_ASC,
                ApiParams.ORDENAR_POR: "data",
            }
            try:
                dados = await self.fetch_paginated(
                    ApiRoutes.VOTACOES, self.build_params(raw_params)
                )
                return pl.DataFrame(dados) if dados else pl.DataFrame()
            except Exception as e:
                logger.debug(f"Falha ao buscar votações de {ano}: {e}")
                return pl.DataFrame()

        df_final = await self.execute_concurrently(
            anos, fetch_votacoes_ano, max_workers=MAX_CONCURRENT_REQUESTS
        )

        if not df_final.is_empty() and "data" in df_final.columns:
            # Filtro Polars de segurança para garantir a janela exata
            # (a API pode vazar os últimos dias do parâmetro)
            df_final = df_final.filter(
                (pl.col("data") >= data_inicio) & (pl.col("data") <= data_fim)
            )
            logger.info(f"{df_final.height} votações extraídas.")
        else:
            logger.info("ℹNenhuma votação nova no período.")

        return df_final

    async def extract_votos(self, votacoes_ids: list[str]) -> pl.DataFrame:
        """Extrai os votos nominais de uma lista de votações usando concorrência máxima."""

        async def fetch_votos(votacao_id: str) -> pl.DataFrame:
            endpoint = f"{ApiRoutes.VOTACOES}/{votacao_id}/votos"
            try:
                dados = await self.client.fetch(endpoint)
                return (
                    pl.DataFrame(dados).with_columns(pl.lit(votacao_id).alias("idVotacao"))
                    if dados
                    else pl.DataFrame()
                )
            except Exception:
                return pl.DataFrame()

        return await self.execute_concurrently(votacoes_ids, fetch_votos)
