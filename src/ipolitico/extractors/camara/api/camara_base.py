import asyncio
from datetime import datetime, timedelta
from typing import Any

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_PAGE_SIZE
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.base import BaseExtractor, IStateStore


class CamaraBaseExtractor(BaseExtractor):
    """
    Extrator Base específico para a API de Dados Abertos da Câmara.

    Atua como uma ponte (Adapter) entre o motor assíncrono genérico e as
    regras de negócio estatais, gerenciando a injeção automática de parâmetros
    de paginação e a normalização de Enumerações.
    """

    def __init__(self, client: CamaraClient, state_store: IStateStore):
        super().__init__(state_store)
        self.client = client

    def build_params(self, raw_params: dict[Any, Any]) -> dict[str, Any]:
        """
        Limpa parâmetros nulos e resolve Enums para strings compreensíveis pela API.

        Args:
            raw_params (dict): Dicionário de parâmetros de requisição cru.

        Returns:
            dict: Dicionário purificado e pronto para serialização na URL.
        """
        cleaned_params = {}
        for key, value in raw_params.items():
            if value is not None:
                param_key = key.value if isinstance(key, ApiParams) else key
                cleaned_params[param_key] = value
        return cleaned_params

    async def fetch_paginated(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Lida com a paginação infinita da Câmara (baseada em 'pagina' e 'itens').

        Percorre as páginas da API automaticamente até que uma lista vazia
        ou uma página com menos itens que o limite máximo (CAMARA_PAGE_SIZE) seja retornada.

        Args:
            endpoint (str): Caminho relativo do recurso (ex: 'deputados/1/despesas').
            params (dict): Parâmetros de filtro e ordenação já limpos.

        Returns:
            list: Todos os registros acumulados das múltiplas páginas.
        """
        all_data = []
        pagina = 1

        while True:
            params[ApiParams.PAGINA.value] = pagina

            dados = await self.client.fetch(endpoint, params=params)

            if not dados:
                break

            all_data.extend(dados)

            if len(dados) < CAMARA_PAGE_SIZE:
                break

            pagina += 1

        return all_data

    async def probe_endpoint(self, endpoint: str) -> int:
        """
        Sonda o endpoint pedindo apenas 1 item para ler o x-total-count.
        Retorna a quantidade total de registros. Se for 0, o recurso está vazio.
        """
        try:
            dados = await self.client.fetch(endpoint, params={"itens": 1})
            return len(dados) if dados else 0
        except Exception:
            return 1

    async def generate_temporal_jobs(
        self,
        route_template: str,
        deputados_ids: list,
        start_date: str,
        end_date: str,
        dep_meta: dict,
        window_days: int = 1460,
    ) -> list[dict]:
        """
        O Motor de Filtro Triplo Genérico:
        1. Poda Biográfica (usa dep_meta para cruzar anos de mandato)
        2. Probing Concorrente (descarta quem não tem dados na rota)
        3. Window Slicing (cria as fatias seguras de N dias para não dar Erro 400)

        Retorna uma lista plana de dicionários (jobs) prontos a consumir.
        """
        dt_start_global = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end_global = datetime.strptime(end_date, "%Y-%m-%d")

        # CAMADA 1: Poda Biográfica
        ativos = []
        for dep_id in deputados_ids:
            meta = dep_meta.get(dep_id)
            if meta:
                # Leg 1 = 1826. Cálculo: 1826 + (ID-1)*4
                ano_i = 1826 + (int(meta["idLegislaturaInicial"]) - 1) * 4
                ano_f = 1826 + (int(meta["idLegislaturaFinal"]) - 1) * 4 + 4

                # Ajusta limites para a janela global solicitada
                foco_inicio = max(ano_i, dt_start_global.year)
                foco_fim = min(ano_f, dt_end_global.year)

                if foco_inicio <= foco_fim:
                    ativos.append((dep_id, foco_inicio, foco_fim))
            else:
                # Se não temos meta, assumimos o período global por segurança
                ativos.append((dep_id, dt_start_global.year, dt_end_global.year))

        # CAMADA 2: Sondagem (Probe) - Descarta quem não tem NADA na rota
        probe_semaphore = asyncio.Semaphore(15)
        com_dados = []

        async def probe(info):
            d_id, a_i, a_f = info
            async with probe_semaphore:
                # Se a rota básica retornar vazio, o x-total-count é 0
                res = await self.client.fetch(route_template.format(id=d_id), params={"itens": 1})
                if res:
                    com_dados.append(info)

        await asyncio.gather(*(probe(i) for i in ativos))

        # CAMADA 3: Window Slicing (Fatias de 4 anos)
        jobs = []
        for d_id, a_i, a_f in com_dados:
            curr_s = datetime(a_i, 1, 1)
            limit_e = datetime(a_f, 12, 31)
            while curr_s <= limit_e:
                curr_e = min(curr_s + timedelta(days=window_days), limit_e)
                jobs.append(
                    {
                        "id": d_id,
                        "start": curr_s.strftime("%Y-%m-%d"),
                        "end": curr_e.strftime("%Y-%m-%d"),
                    }
                )
                curr_s = curr_e + timedelta(days=1)

        return jobs
