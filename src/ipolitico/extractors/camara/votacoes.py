import logging
from datetime import datetime

import polars as pl

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class VotacoesExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Votações e Votos Nominais.

    Atenção Arquitetural: O volume de votos nominais (513 deputados * milhares de votações)
    cresce exponencialmente. O uso de lotes (chunks) pelo orquestrador ao chamar `extract_votos`
    é inegociável para evitar o esgotamento de memória RAM e bloqueios da API (HTTP 429).
    """

    async def extract(self, start_date: str, end_date: str) -> pl.DataFrame:
        """
        Extrai o cabeçalho e os metadados das votações numa janela temporal estrita.

        Args:
            start_date (str): Data inicial (YYYY-MM-DD).
            end_date (str): Data final (YYYY-MM-DD).

        Returns:
            pl.DataFrame: DataFrame com os metadados das votações do período.
        """
        if not start_date or not end_date:
            raise ValueError("O Extrator de Votações exige limites temporais explícitos.")

        clean_start = str(start_date).split("T")[0]
        clean_end = str(end_date).split("T")[0]
        ini_dt = datetime.strptime(clean_start, "%Y-%m-%d")
        end_dt = datetime.strptime(clean_end, "%Y-%m-%d")

        logger.debug(f"Sincronizando Votações: {clean_start} a {clean_end}")
        anos = list(range(ini_dt.year, end_dt.year + 1))

        async def fetch_votacoes_ano(ano: int) -> pl.DataFrame:
            current_start = f"{ano}-01-01" if ano > ini_dt.year else clean_start
            current_end = f"{ano}-12-31" if ano < end_dt.year else clean_end

            raw_params = {
                ApiParams.DATA_INICIO.value: current_start,
                ApiParams.DATA_FIM.value: current_end,
                ApiParams.ORDEM.value: ApiParams.ORDEM_ASC.value,
                ApiParams.ORDENAR_POR.value: "data",
            }
            dados = await self.fetch_paginated(
                ApiRoutes.VOTACOES.value, self.build_params(raw_params)
            )
            return pl.DataFrame(dados) if dados else pl.DataFrame()

        df_final = await self.execute_concurrently(
            anos, fetch_votacoes_ano, max_workers=MAX_CONCURRENT_REQUESTS, desc="Baixando Votações"
        )

        if not df_final.is_empty():
            df_final = df_final.filter(
                (pl.col("data").str.slice(0, 10) >= start_date)
                & (pl.col("data").str.slice(0, 10) <= end_date)
            )

        return df_final

    async def extract_votos(self, votacoes_ids: list[str]) -> pl.DataFrame:
        """
        Extrai os votos nominais detalhados (Sim, Não, Abstenção) de uma lista de votações.

        Args:
            votacoes_ids (list[str]): Lista restrita de IDs das votações alvo.

        Returns:
            pl.DataFrame: DataFrame contendo o posicionamento individual dos deputados.
        """
        if not votacoes_ids:
            return pl.DataFrame()

        async def fetch_votos(votacao_id: str) -> pl.DataFrame:
            endpoint = f"{ApiRoutes.VOTACOES.value}/{votacao_id}/votos"

            dados = await self.client.fetch(endpoint)

            if dados:
                for voto in dados:
                    voto["idVotacao"] = votacao_id

                    if "deputado_" in voto and isinstance(voto["deputado_"], dict):
                        # Extrai as chaves relacionais para a raiz do registo
                        voto["deputado_id"] = voto["deputado_"].get("id")
                        voto["partido_no_voto"] = voto["deputado_"].get("siglaPartido")
                        voto["uf_no_voto"] = voto["deputado_"].get("siglaUf")

                        # Destrói o dicionário para que o SQLite não rejeite o INSERT
                        del voto["deputado_"]

                return pl.DataFrame(dados)

            return pl.DataFrame()

        return await self.execute_concurrently(
            votacoes_ids, fetch_votos, desc="Baixando Votos Nominais"
        )
