import json
import logging

import polars as pl

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.camara_base import CamaraBaseExtractor
from ipolitico.services.metadata import CamaraMetadataService

logger = logging.getLogger(__name__)


class DeputadosExtractor(CamaraBaseExtractor):
    """
    Extrator responsável por buscar a listagem de deputados federais.
    Consome a rota /deputados da API da Câmara.
    """

    def __init__(self, client, state_store):
        super().__init__(client, state_store)
        self.metadata = CamaraMetadataService(client)

    async def get_all_ids(self) -> list[int]:
        """
        Pede ao banco (StateStore) os IDs. Se não tiver, extrai e devolve.
        """
        ids_no_banco = self.state_store.get_existing_ids("deputados")
        if ids_no_banco:
            return ids_no_banco

        df_new = await self.extract()
        return df_new["id"].to_list() if not df_new.is_empty() else []

    async def extract(
        self, data_inicio: str = None, data_fim: str = None, legislatura: int = None
    ) -> pl.DataFrame:
        if legislatura or data_inicio or data_fim:
            raw_params = {
                ApiParams.DATA_INICIO.value: data_inicio,
                ApiParams.DATA_FIM.value: data_fim,
                ApiParams.ID_LEGISLATURA.value: legislatura,
            }
            dados = await self.fetch_paginated(
                ApiRoutes.DEPUTADOS.value, self.build_params(raw_params)
            )
            return pl.DataFrame(dados) if dados else pl.DataFrame()

        ultima_leg = await self.metadata.get_current_legislature_id()
        logger.info(f"Sincronizando História (Legislaturas 1 a {ultima_leg})...")

        async def fetch_job(leg_id: int) -> pl.DataFrame:
            params = self.build_params({ApiParams.ID_LEGISLATURA.value: leg_id})
            try:
                dados = await self.fetch_paginated(ApiRoutes.DEPUTADOS.value, params)
                return pl.DataFrame(dados) if dados else pl.DataFrame()
            except Exception:
                return pl.DataFrame()

        df_historico = await self.execute_concurrently(
            list(range(1, ultima_leg + 1)),
            fetch_job,
            max_workers=MAX_CONCURRENT_REQUESTS,
            desc="Baixando Deputados",
        )

        return df_historico.unique(subset=["id"]) if not df_historico.is_empty() else df_historico

    async def extract_detalhes(self, deputados_ids: list) -> pl.DataFrame:
        async def fetch_detalhe(dep_id: int) -> pl.DataFrame:
            endpoint = f"{ApiRoutes.DEPUTADOS}/{dep_id}"
            try:
                resp = await self.client.fetch(endpoint)
                if resp:
                    for key, value in resp.items():
                        if isinstance(value, (dict, list)):
                            resp[key] = json.dumps(value, ensure_ascii=False)

                    return pl.DataFrame([resp])
                return pl.DataFrame()
            except Exception:
                return pl.DataFrame()

        return await self.execute_concurrently(
            deputados_ids, fetch_detalhe, desc="Baixando Detalhes dos Deputados"
        )
