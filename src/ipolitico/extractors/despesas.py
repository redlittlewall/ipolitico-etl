import asyncio
from asyncio.log import logger

import polars as pl

from ipolitico.core.config import LEGISLATURA_ATUAL
from ipolitico.extractors.base import BaseExtractor


class DespesasExtractor(BaseExtractor):
    """
    Extrator de despesas (Cota Parlamentar).
    Crucial para auditoria de gastos com combustível, passagens e consultoria.
    """

    async def extract(self, deputados_ids: list) -> pl.DataFrame:
        """
        Orquestra a extração de todos os deputados com controle de concorrência interno.
        """
        semaforo = asyncio.Semaphore(5)
        tarefas = [self._extract_por_deputado(d_id, semaforo) for d_id in deputados_ids]

        logger.info(f"Sincronizando despesas de {len(deputados_ids)} deputados...")
        resultados = await asyncio.gather(*tarefas)

        frames = [r for r in resultados if not r.is_empty()]
        return pl.concat(frames) if frames else pl.DataFrame()

    async def _extract_por_deputado(
        self, deputado_id: int, semaforo: asyncio.Semaphore
    ) -> pl.DataFrame:
        """
        Extrai as despesas de um deputado específico de forma incremental.
        """
        # Buscamos a última data de emissão para este deputado específico no banco
        # Nota: Idealmente o banco deve ter o 'id_deputado' para esse filtro
        async with semaforo:
            data_inicio = self._get_last_watermark("despesas", "dataEmissao") or "2023-02-01"

            endpoint = f"deputados/{deputado_id}/despesas"
            params = {
                "idLegislatura": LEGISLATURA_ATUAL,
                "ordem": "ASC",
                "ordenarPor": "dataEmissao",
                "dataInicio": data_inicio.split("T")[0],
            }

            dados = await self.client.fetch(endpoint, params=params)

            if not dados:
                return pl.DataFrame()
