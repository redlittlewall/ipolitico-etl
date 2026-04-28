import logging
from datetime import datetime

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class VotacoesExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Votações e Votos Nominais.

    Atenção Arquitetural: O volume de dados é massivo. O sistema opera via streaming,
    processando e salvando metadados e votos em paralelo para manter um footprint
    de memória baixo e constante, independente do volume da legislatura.
    """

    async def extract(self, sink_func, start_date: str, end_date: str) -> pl.DataFrame:
        """
        Extrai o cabeçalho e os metadados das votações via streaming.

        Args:
            sink_func (callable): Função assíncrona de persistência.
            start_date (str): Data inicial (YYYY-MM-DD).
            end_date (str): Data final (YYYY-MM-DD).

        Returns:
            None
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
                ApiParams.DATA_INICIO: current_start,
                ApiParams.DATA_FIM: current_end,
                ApiParams.ORDEM: ApiParams.ORDEM_ASC.value,
                ApiParams.ORDENAR_POR: "data",
            }
            dados = await self.fetch_paginated(
                ApiRoutes.VOTACOES.value, self.build_params(raw_params)
            )
            df = pl.DataFrame(dados) if dados else pl.DataFrame()
            if not df.is_empty():
                df = df.filter(
                    (pl.col("data").str.slice(0, 10) >= start_date)
                    & (pl.col("data").str.slice(0, 10) <= end_date)
                )
            return df

        await self.execute_pipeline(
            items=anos,
            fetch_func=fetch_votacoes_ano,
            sink_func=sink_func,
            table_name="votacoes",
            unique_keys="id",
        )

    async def extract_votos(self, sink_func, votacoes_ids: list[str]) -> None:
        """
        Extrai os votos nominais detalhados enviando-os para o sink em tempo real.

        Args:
            sink_func (callable): Função assíncrona de persistência.
            votacoes_ids (list[str]): Lista de IDs das votações alvo.

        Returns:
            None
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

        await self.execute_pipeline(
            items=votacoes_ids,
            fetch_func=fetch_votos,
            sink_func=sink_func,
            table_name="votos",
            unique_keys=["idVotacao", "deputado_id"],
        )
