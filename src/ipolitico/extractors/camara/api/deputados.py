import json
import logging

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor
from ipolitico.services.metadata import CamaraMetadataService

logger = logging.getLogger(__name__)


class DeputadosExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Deputados Federais.

    Gere a extração via streaming, permitindo o processamento paralelo de
    múltiplas legislaturas ou detalhes individuais sem sobrecarregar a memória.
    """

    def __init__(self, client, state_store):
        super().__init__(client, state_store)
        self.metadata = CamaraMetadataService(client)

    async def get_all_ids(self) -> list[int]:
        ids_no_banco = self.state_store.get_existing_ids("deputados")
        if ids_no_banco:
            return ids_no_banco
        df_new = await self.extract()
        return df_new["id"].to_list() if not df_new.is_empty() else []

    async def extract(
        self,
        sink_func,
        start_date: str = None,
        end_date: str = None,
        legislatura: int = None,
        full_load: bool = False,
    ) -> None:
        """
        Extrai a lista de deputados com base em filtros temporais ou legislaturas.

        Se nenhum filtro for providenciado, o comportamento varia segundo a flag `full_load`:
        - Se True: Executa uma carga massiva de todas as legislaturas (1 até à atual).
        - Se False: Sincroniza apenas os deputados da legislatura em curso.

        Args:
            sink_func (callable): Função assíncrona de persistência.
            start_date (str, optional): Filtro de data inicial (YYYY-MM-DD).
            end_date (str, optional): Filtro de data final (YYYY-MM-DD).
            legislatura (int, optional): ID específico da legislatura.
            full_load (bool): Define se deve varrer o histórico inteiro
                se os filtros estiverem vazios.

        Returns:
            None: Os dados são enviados diretamente para a fila do consumidor (sink_func).
        """
        if legislatura or start_date or end_date:
            logger.debug(
                f"Baixando deputados (Filtros - Leg: {legislatura} | {start_date} a {end_date})"
            )
            raw_params = {
                ApiParams.DATA_INICIO.value: start_date,
                ApiParams.DATA_FIM.value: end_date,
                ApiParams.ID_LEGISLATURA.value: legislatura,
            }
            dados = await self.fetch_paginated(
                ApiRoutes.DEPUTADOS.value, self.build_params(raw_params)
            )
            if dados:
                await sink_func(pl.DataFrame(dados), "deputados", "id")
            return

        ultima_leg = await self.metadata.get_current_legislature_id()
        legislaturas_alvo = list(range(1, ultima_leg + 1)) if full_load else [ultima_leg]

        async def fetch_job(leg_id: int) -> pl.DataFrame:
            params = self.build_params({ApiParams.ID_LEGISLATURA.value: leg_id})
            dados = await self.fetch_paginated(ApiRoutes.DEPUTADOS.value, params)
            return pl.DataFrame(dados) if dados else pl.DataFrame()

        await self.execute_pipeline(
            items=legislaturas_alvo,
            fetch_func=fetch_job,
            sink_func=sink_func,
            table_name="deputados",
            unique_keys="id",
        )

    async def extract_detalhes(self, sink_func, deputados_ids: list) -> None:
        """
        Extrai informações cadastrais profundas de uma lista específica de deputados.

        Realiza chamadas HTTP individuais para o endpoint '/deputados/{id}', normalizando
        estruturas complexas (dicionários e listas internas) para JSON em formato texto,
        prevenindo erros de schema no Polars/SQLite.

        Args:
            sink_func (callable): Função assíncrona de persistência.
            deputados_ids (list[int]): Lista de IDs únicos dos deputados a processar.

        Returns:
            None: Os dados são enviados diretamente para a fila do consumidor (sink_func).
        """
        if not deputados_ids:
            return

        async def fetch_detalhe(dep_id: int) -> pl.DataFrame:
            endpoint = f"{ApiRoutes.DEPUTADOS.value}/{dep_id}"
            resp = await self.client.fetch(endpoint)
            if resp:
                for key, value in resp.items():
                    if isinstance(value, (dict, list)):
                        resp[key] = json.dumps(value, ensure_ascii=False)
                return pl.DataFrame([resp])
            return pl.DataFrame()

        await self.execute_pipeline(
            items=deputados_ids,
            fetch_func=fetch_detalhe,
            sink_func=sink_func,
            table_name="deputados_detalhes",
            unique_keys="id",
        )
