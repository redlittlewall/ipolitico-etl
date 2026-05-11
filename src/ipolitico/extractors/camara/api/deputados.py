import asyncio
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
            await asyncio.sleep(0.2)

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

    # ==========================================
    # DADOS BIOGRÁFICOS (ESTÁTICOS)
    # ==========================================

    async def extract_profissoes(self, sink_func, deputados_ids: list) -> None:
        """Extrai a lista de profissões declaradas pelos deputados."""
        if not deputados_ids:
            return
        logger.info(f"     ∟ Extraindo profissões para {len(deputados_ids)} deputados...")

        async def fetch_func(dep_id: int) -> pl.DataFrame:
            await asyncio.sleep(0.1)
            dados = await self.client.fetch(f"{ApiRoutes.DEPUTADOS.value}/{dep_id}/profissoes")
            if dados:
                df = pl.DataFrame(dados).with_columns(pl.all().cast(pl.String, strict=False))
                return df.with_columns(pl.lit(dep_id).cast(pl.Int64).alias("id_deputado"))
            return pl.DataFrame()

        await self.execute_pipeline(
            deputados_ids,
            fetch_func,
            sink_func,
            "deputados_profissoes",
            ["id_deputado", "codTipoProfissao"],
        )

    async def extract_ocupacoes(self, sink_func, deputados_ids: list) -> None:
        """Extrai as ocupações (empregos e atividades) anteriores dos deputados."""
        if not deputados_ids:
            return
        logger.info(f"     ∟ Extraindo ocupações para {len(deputados_ids)} deputados...")

        async def fetch_func(dep_id: int) -> pl.DataFrame:
            await asyncio.sleep(0.1)
            dados = await self.client.fetch(f"{ApiRoutes.DEPUTADOS.value}/{dep_id}/ocupacoes")
            if dados:
                df = pl.DataFrame(dados).with_columns(pl.all().cast(pl.String, strict=False))
                return df.with_columns(pl.lit(dep_id).cast(pl.Int64).alias("id_deputado"))
            return pl.DataFrame()

        await self.execute_pipeline(
            deputados_ids,
            fetch_func,
            sink_func,
            "deputados_ocupacoes",
            ["id_deputado", "titulo", "entidade"],
        )

    async def extract_mandatos_externos(self, sink_func, deputados_ids: list) -> None:
        """Extrai cargos eletivos externos (prefeito, vereador, etc) já exercidos."""
        if not deputados_ids:
            return
        logger.info(f"     ∟ Extraindo mandatos externos para {len(deputados_ids)} deputados...")

        async def fetch_func(dep_id: int) -> pl.DataFrame:
            await asyncio.sleep(0.1)
            dados = await self.client.fetch(
                f"{ApiRoutes.DEPUTADOS.value}/{dep_id}/mandatosExternos"
            )
            if dados:
                df = pl.DataFrame(dados).with_columns(pl.all().cast(pl.String, strict=False))
                return df.with_columns(pl.lit(dep_id).cast(pl.Int64).alias("id_deputado"))
            return pl.DataFrame()

        await self.execute_pipeline(
            deputados_ids,
            fetch_func,
            sink_func,
            "deputados_mandatos_externos",
            ["id_deputado", "cargo", "anoInicio"],
        )

    async def extract_frentes(self, sink_func, deputados_ids: list) -> None:
        """Extrai as frentes parlamentares das quais os deputados são membros."""
        if not deputados_ids:
            return
        logger.info(
            f"     ∟ Extraindo frentes parlamentares para {len(deputados_ids)} deputados..."
        )

        async def fetch_func(dep_id: int) -> pl.DataFrame:
            await asyncio.sleep(0.1)
            dados = await self.client.fetch(f"{ApiRoutes.DEPUTADOS.value}/{dep_id}/frentes")
            if dados:
                df = pl.DataFrame(dados).with_columns(pl.all().cast(pl.String, strict=False))
                return df.with_columns(pl.lit(dep_id).cast(pl.Int64).alias("id_deputado"))
            return pl.DataFrame()

        await self.execute_pipeline(
            deputados_ids, fetch_func, sink_func, "deputados_frentes", ["id_deputado", "id"]
        )

    async def extract_historico(self, sink_func, deputados_ids: list) -> None:
        """Extrai o histórico de mudanças no exercício parlamentar (licenças, trocas de partido)."""
        if not deputados_ids:
            return
        logger.info(
            f"     ∟ Extraindo histórico parlamentar para {len(deputados_ids)} deputados..."
        )

        async def fetch_func(dep_id: int) -> pl.DataFrame:
            await asyncio.sleep(0.5)
            dados = await self.client.fetch(f"{ApiRoutes.DEPUTADOS.value}/{dep_id}/historico")
            if dados:
                df = pl.DataFrame(dados).with_columns(pl.all().cast(pl.String, strict=False))
                return df.with_columns(pl.lit(dep_id).cast(pl.Int64).alias("id_deputado"))
            return pl.DataFrame()

        await self.execute_pipeline(
            deputados_ids,
            fetch_func,
            sink_func,
            "deputados_historico",
            ["id_deputado", "dataHora", "situacao"],
            max_workers=3,
        )

    # ==========================================
    # ATIVIDADES (TEMPORAIS E PAGINADAS)
    # ==========================================

    async def extract_discursos(
        self, sink_func, deputados_ids: list, start_date: str, end_date: str, dep_meta: dict
    ) -> None:
        """
        Extrai discursos aplicando o Filtro de Três Camadas (Otimização Extrema):
        1. Poda Biográfica: Ignora anos em que o deputado não tinha mandato.
        2. Sondagem HTTP (Probing): Verifica se o deputado tem qualquer discurso na base.
        3. Window Slicing: Fatiamento de 4 anos para bypass do Erro 400 da Câmara.
        """
        if not start_date or not end_date or not deputados_ids:
            return
        logger.info(f"     ∟ [DISCURSOS] Gerando tarefas para {len(deputados_ids)} deputados...")

        route_tmpl = f"{ApiRoutes.DEPUTADOS.value}/{{id}}/discursos"
        jobs = await self.generate_temporal_jobs(
            route_tmpl, deputados_ids, start_date, end_date, dep_meta
        )

        if not jobs:
            return
        logger.info(f"     ∟ Disparando {len(jobs)} fatias de extração de discursos...")

        async def fetch_func(job: dict) -> pl.DataFrame:
            await asyncio.sleep(0.1)
            params = self.build_params(
                {
                    ApiParams.DATA_INICIO.value: job["start"],
                    ApiParams.DATA_FIM.value: job["end"],
                    ApiParams.ITENS.value: 100,
                }
            )
            try:
                dados = await self.fetch_paginated(route_tmpl.format(id=job["id"]), params)
                if dados:
                    df = pl.DataFrame(dados)
                    if "transcricao" in df.columns:
                        df = df.with_columns(pl.col("transcricao").cast(pl.String))
                    return df.with_columns(pl.lit(job["id"]).cast(pl.Int64).alias("id_deputado"))
            except Exception:
                pass
            return pl.DataFrame()

        await self.execute_pipeline(
            jobs,
            fetch_func,
            sink_func,
            "deputados_discursos",
            ["id_deputado", "dataHoraInicio"],
            max_workers=3,
        )

    async def extract_orgaos(
        self, sink_func, deputados_ids: list, start_date: str, end_date: str, dep_meta: dict
    ) -> None:
        """Extrai os órgãos (comissões) dos quais o deputado participou no período."""
        if not start_date or not end_date or not deputados_ids:
            return
        logger.info(
            f"     ∟ [ÓRGÃOS] Gerando tarefas com Poda e Probe para {len(deputados_ids)} "
            "deputados..."
        )

        route_tmpl = f"{ApiRoutes.DEPUTADOS.value}/{{id}}/orgaos"
        jobs = await self.generate_temporal_jobs(
            route_tmpl, deputados_ids, start_date, end_date, dep_meta
        )

        if not jobs:
            return
        logger.info(f"     ∟ Disparando {len(jobs)} fatias de extração de órgãos...")

        async def fetch_func(job: dict) -> pl.DataFrame:
            await asyncio.sleep(0.1)
            params = self.build_params(
                {
                    ApiParams.DATA_INICIO.value: job["start"],
                    ApiParams.DATA_FIM.value: job["end"],
                    ApiParams.ITENS.value: 100,
                }
            )
            try:
                dados = await self.fetch_paginated(route_tmpl.format(id=job["id"]), params)
                if dados:
                    return pl.DataFrame(dados).with_columns(
                        pl.lit(job["id"]).cast(pl.Int64).alias("id_deputado")
                    )
            except Exception:
                pass
            return pl.DataFrame()

        await self.execute_pipeline(
            jobs,
            fetch_func,
            sink_func,
            "deputados_orgaos",
            ["id_deputado", "idOrgao", "dataInicio"],
            max_workers=4,
        )

    async def extract_eventos(
        self, sink_func, deputados_ids: list, start_date: str, end_date: str, dep_meta: dict
    ) -> None:
        """Extrai os eventos com previsão de participação do deputado."""
        if not start_date or not end_date or not deputados_ids:
            return
        logger.info(
            f"     ∟ [EVENTOS] Gerando tarefas com Poda e Probe para {len(deputados_ids)}"
            " deputados..."
        )

        route_tmpl = f"{ApiRoutes.DEPUTADOS.value}/{{id}}/eventos"
        jobs = await self.generate_temporal_jobs(
            route_tmpl, deputados_ids, start_date, end_date, dep_meta
        )

        if not jobs:
            return
        logger.info(f"     ∟ Disparando {len(jobs)} fatias de extração de eventos...")

        async def fetch_func(job: dict) -> pl.DataFrame:
            await asyncio.sleep(0.1)
            params = self.build_params(
                {
                    ApiParams.DATA_INICIO.value: job["start"],
                    ApiParams.DATA_FIM.value: job["end"],
                    ApiParams.ITENS.value: 100,
                }
            )
            try:
                dados = await self.fetch_paginated(route_tmpl.format(id=job["id"]), params)
                if dados:
                    return pl.DataFrame(dados).with_columns(
                        pl.lit(job["id"]).cast(pl.Int64).alias("id_deputado")
                    )
            except Exception:
                pass
            return pl.DataFrame()

        await self.execute_pipeline(
            jobs, fetch_func, sink_func, "deputados_eventos", ["id_deputado", "id"], max_workers=4
        )
