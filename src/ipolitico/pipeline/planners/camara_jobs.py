import calendar
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from ipolitico.core.constants import (
    EARLIEST_DATE_MAP,
    DomainType,
    MedallionLayer,
    SourceType,
)
from ipolitico.pipeline.deputy_universe import resolve_deputy_ids_for_calendar_window
from ipolitico.pipeline.effective_window import resolve_calendar_years
from ipolitico.pipeline.job_resume import (
    filter_deputado_child_jobs,
    filter_despesas_api_jobs,
    filter_entity_ids_pending_child,
    filter_proposicao_ids_pending_child,
    filter_votacao_ids_pending_votos,
)
from ipolitico.pipeline.source_router import ExtractionPlan
from ipolitico.storage.datalake_repository import DataLakeRepository

logger = logging.getLogger(__name__)

_STATIC_DEPUTY_CHILDREN = frozenset(
    {
        DomainType.PROFISSÕES.value,
        DomainType.OCUPACOES.value,
        DomainType.DEPUTADOS_FRENTES.value,
        DomainType.DEPUTADOS_HISTORICO.value,
    }
)
_TEMPORAL_DEPUTY_CHILDREN = frozenset(
    {
        DomainType.DISCURSOS.value,
        DomainType.DEPUTADOS_ORGAOS.value,
        DomainType.DEPUTADOS_EVENTOS.value,
    }
)
_PROPOSICAO_CHILDREN = frozenset(
    {
        DomainType.TRAMITACOES.value,
        DomainType.AUTORES.value,
        DomainType.RELACIONADAS.value,
        DomainType.TEMAS.value,
        DomainType.PROPOSICOES_VOTACOES.value,
    }
)
_EVENTO_CHILDREN = frozenset(
    {
        DomainType.EVENTOS_DEPUTADOS.value,
        DomainType.EVENTOS_VOTACOES.value,
        DomainType.EVENTOS_PAUTA.value,
    }
)


class CamaraJobPlanner:
    """Geração de jobs e mapeadores kw para chamadas à API/Bulk."""

    def __init__(self, state_store: Any, lake_repository: Optional[DataLakeRepository]) -> None:
        self._state_store = state_store
        self._lake = lake_repository

    def build(
        self,
        domain: DomainType,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
    ) -> Tuple[List[Dict[str, Any]], Callable[[Dict[str, Any]], Dict[str, Any]]]:
        domain_val = domain.value if hasattr(domain, "value") else str(domain)

        if domain_val == DomainType.DEPUTADOS.value:
            if start == EARLIEST_DATE_MAP[DomainType.DEPUTADOS]:
                jobs = [{"legislatura_id": leg} for leg in range(1, current_leg + 1)]
                logger.info(
                    f"[{domain_val.upper()}] Estratégia Histórica. "
                    f"Iterando da Legislatura 1 até a atual ({current_leg})."
                )
            else:
                jobs = [{"start_date": start, "end_date": end}]
                logger.info(f"[{domain_val.upper()}] Recorte temporal: {start} a {end}.")

            def deputados_mapper(job: dict) -> dict:
                if "legislatura_id" in job:
                    return {"legislatura_id": job["legislatura_id"]}
                return {"start_date": job["start_date"], "end_date": job["end_date"]}

            return jobs, deputados_mapper

        if domain_val == DomainType.DESPESAS.value:
            start_year, end_year = resolve_calendar_years(start, end)

            if extraction_plan.source_type == SourceType.BULK:
                jobs = [{"year": y} for y in range(start_year, end_year + 1)]

                def despesas_bulk_mapper(job: dict) -> dict:
                    return {"year": job["year"]}

                logger.info(
                    f"[{domain_val.upper()}] BULK CEAP por ano: "
                    f"{len(jobs)} arquivos ({start_year}-{end_year})."
                )
                return jobs, despesas_bulk_mapper

            deputados_ids = resolve_deputy_ids_for_calendar_window(
                start_iso=start,
                end_iso=end,
                current_legislature_id=current_leg,
                anchor_year=anchor_year,
                lake=self._lake,
                state_store=self._state_store,
            )

            if not deputados_ids:
                logger.warning(
                    f"[{domain_val.upper()}] Nenhum deputado encontrado no State Store! "
                    f"Execute o pipeline de '{DomainType.DEPUTADOS.value}' primeiro."
                )
                return [], lambda x: {}

            jobs = []
            for dep_id in deputados_ids:
                for year in range(start_year, end_year + 1):
                    jobs.append({"deputado_id": dep_id, "year": year})

            if self._lake is not None:
                covered = self._lake.list_deputy_expense_year_pairs()
                jobs = filter_despesas_api_jobs(jobs, covered)

            logger.info(
                f"[{domain_val.upper()}] Criados {len(jobs)} micro-lotes "
                f"(deputados na janela: {len(deputados_ids)}, anos {start_year}..{end_year})."
            )

            def despesas_mapper(job: dict) -> dict:
                return {"deputado_id": job["deputado_id"], "year": job["year"]}

            return jobs, despesas_mapper

        if domain_val in [
            DomainType.PROPOSICOES.value,
            DomainType.VOTACOES.value,
            DomainType.EVENTOS.value,
        ]:
            start_year = int(start.split("-")[0])
            start_month = int(start.split("-")[1])
            end_year = int(end.split("-")[0])
            end_month = int(end.split("-")[1])

            jobs: List[Dict[str, Any]] = []
            if extraction_plan.source_type == SourceType.BULK:
                for y in range(start_year, end_year + 1):
                    jobs.append({"year": y})

                logger.info(f"[{domain_val.upper()}] BULK por ano: {len(jobs)} lotes.")

                def year_mapper(job: dict) -> dict:
                    return {"year": job["year"]}

                return jobs, year_mapper

            for y in range(start_year, end_year + 1):
                m_start = start_month if y == start_year else 1
                m_end = end_month if y == end_year else 12
                for m in range(m_start, m_end + 1):
                    first_day = f"{y}-{m:02d}-01"
                    last_d = calendar.monthrange(y, m)[1]
                    last_day = f"{y}-{m:02d}-{last_d:02d}"
                    jobs.append({"start_date": first_day, "end_date": last_day})

            logger.info(f"[{domain_val.upper()}] Criados {len(jobs)} micro-lotes mensais.")

            def time_mapper(job: dict) -> dict:
                return {"start_date": job["start_date"], "end_date": job["end_date"]}

            return jobs, time_mapper

        if domain_val in _STATIC_DEPUTY_CHILDREN:
            deputados_ids = resolve_deputy_ids_for_calendar_window(
                start_iso=start,
                end_iso=end,
                current_legislature_id=current_leg,
                anchor_year=anchor_year,
                lake=self._lake,
                state_store=self._state_store,
            )
            if not deputados_ids:
                logger.error(
                    "[%s] Abortando: nenhum deputado no lake. Rode '%s' antes.",
                    domain_val.upper(),
                    DomainType.DEPUTADOS.value,
                )
                return [], lambda x: {}

            jobs = [{"deputado_id": dep_id} for dep_id in deputados_ids]
            if self._lake is not None:
                covered = self._lake.list_deputy_ids_in_child_table(domain_val)
                jobs = filter_deputado_child_jobs(jobs, covered)
            logger.info("[%s] %s jobs (1 req/deputado).", domain_val.upper(), len(jobs))

            def static_child_mapper(job: dict) -> dict:
                return {"deputado_id": job["deputado_id"]}

            return jobs, static_child_mapper

        if domain_val in _TEMPORAL_DEPUTY_CHILDREN:
            deputados_ids = resolve_deputy_ids_for_calendar_window(
                start_iso=start,
                end_iso=end,
                current_legislature_id=current_leg,
                anchor_year=anchor_year,
                lake=self._lake,
                state_store=self._state_store,
            )
            if not deputados_ids:
                logger.error(
                    "[%s] Abortando: nenhum deputado no lake. Rode '%s' antes.",
                    domain_val.upper(),
                    DomainType.DEPUTADOS.value,
                )
                return [], lambda x: {}

            jobs = [
                {"deputado_id": dep_id, "start_date": start, "end_date": end}
                for dep_id in deputados_ids
            ]
            if self._lake is not None:
                covered = self._lake.list_deputy_ids_in_child_table(domain_val)
                jobs = filter_deputado_child_jobs(jobs, covered)
            logger.info("[%s] %s jobs (deputado × janela).", domain_val.upper(), len(jobs))

            def temporal_child_mapper(job: dict) -> dict:
                return {
                    "deputado_id": job["deputado_id"],
                    "start_date": job["start_date"],
                    "end_date": job["end_date"],
                }

            return jobs, temporal_child_mapper

        if domain_val == DomainType.VOTOS.value:
            if self._lake is not None:
                votacoes_ids = self._lake.list_votacao_ids_silver_or_gold(start, end)
            else:
                votacoes_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.VOTACOES.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )

            if not votacoes_ids:
                logger.error(
                    "[VOTOS] Abortando: nenhum ID em silver/votacoes (ou gold). "
                    "Rode votacoes no mesmo período antes e confira logs de transformação "
                    "(linhas brutas descartadas = contrato Silver)."
                )
                return [], lambda x: {}

            if self._lake is not None:
                covered_votos = self._lake.list_votacao_ids_with_votos_materialized()
                votacoes_ids = filter_votacao_ids_pending_votos(votacoes_ids, covered_votos)

            if not votacoes_ids:
                logger.info("[VOTOS] Todas as votações da janela já possuem votos na Silver/Gold.")
                return [], lambda x: {}

            batch_size = 20
            jobs = [
                {"votacao_ids": votacoes_ids[i : i + batch_size]}
                for i in range(0, len(votacoes_ids), batch_size)
            ]

            logger.info(f"[VOTOS] Orquestrando {len(votacoes_ids)} votações em {len(jobs)} lotes.")

            def votos_mapper(job: dict) -> dict:
                return {"votacao_ids": job["votacao_ids"]}

            return jobs, votos_mapper

        if domain_val == DomainType.ORIENTACOES.value:
            if self._lake is not None:
                votacoes_ids = self._lake.list_votacao_ids_silver_or_gold(start, end)
            else:
                votacoes_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.VOTACOES.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )

            if not votacoes_ids:
                logger.error(
                    "[ORIENTACOES] Abortando: nenhuma votação no lake. Rode '%s' antes.",
                    DomainType.VOTACOES.value,
                )
                return [], lambda x: {}

            if self._lake is not None:
                covered = self._lake.list_votacao_ids_with_orientacoes_materialized()
                votacoes_ids = filter_votacao_ids_pending_votos(votacoes_ids, covered)

            if not votacoes_ids:
                logger.info("[ORIENTACOES] Todas as votações da janela já possuem orientações.")
                return [], lambda x: {}

            batch_size = 20
            jobs = [
                {"votacao_ids": votacoes_ids[i : i + batch_size]}
                for i in range(0, len(votacoes_ids), batch_size)
            ]
            logger.info("[ORIENTACOES] %s votações em %s lotes.", len(votacoes_ids), len(jobs))

            def orientacoes_mapper(job: dict) -> dict:
                return {"votacao_ids": job["votacao_ids"]}

            return jobs, orientacoes_mapper

        if domain_val == DomainType.ORGAOS.value:
            jobs = [{"start_date": start, "end_date": end}]
            logger.info("[%s] 1 job (janela %s a %s).", domain_val.upper(), start, end)

            def orgaos_mapper(job: dict) -> dict:
                return {"start_date": job["start_date"], "end_date": job["end_date"]}

            return jobs, orgaos_mapper

        if domain_val == DomainType.ORGAOS_MEMBROS.value:
            if self._lake is not None:
                orgao_ids = self._lake.list_orgao_ids_silver_or_gold()
            else:
                orgao_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.ORGAOS.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )

            if not orgao_ids:
                logger.error(
                    "[ORGAOS_MEMBROS] Abortando: nenhum órgão no lake. Rode '%s' antes.",
                    DomainType.ORGAOS.value,
                )
                return [], lambda x: {}

            if self._lake is not None:
                covered = self._lake.list_entity_ids_with_child_materialized(domain_val, "id_orgao")
                orgao_ids = filter_entity_ids_pending_child(
                    orgao_ids, covered, domain_val, "órgãos"
                )

            if not orgao_ids:
                logger.info("[ORGAOS_MEMBROS] Todos os órgãos já possuem membros materializados.")
                return [], lambda x: {}

            batch_size = 15
            jobs = [
                {
                    "orgao_ids": orgao_ids[i : i + batch_size],
                    "start_date": start,
                    "end_date": end,
                }
                for i in range(0, len(orgao_ids), batch_size)
            ]
            logger.info("[ORGAOS_MEMBROS] %s órgãos em %s lotes.", len(orgao_ids), len(jobs))

            def orgaos_membros_mapper(job: dict) -> dict:
                return {
                    "orgao_ids": job["orgao_ids"],
                    "start_date": job["start_date"],
                    "end_date": job["end_date"],
                }

            return jobs, orgaos_membros_mapper

        if domain_val == DomainType.PARTIDOS.value:
            jobs = [
                {
                    "start_date": start,
                    "end_date": end,
                    "legislatura_id": current_leg,
                }
            ]
            logger.info("[%s] 1 job com legislatura %s.", domain_val.upper(), current_leg)

            def partidos_mapper(job: dict) -> dict:
                return {
                    "start_date": job["start_date"],
                    "end_date": job["end_date"],
                    "legislatura_id": job["legislatura_id"],
                }

            return jobs, partidos_mapper

        if domain_val in (DomainType.BLOCOS.value, DomainType.FRENTES.value):
            domain_enum = DomainType(domain_val)
            if start == EARLIEST_DATE_MAP[domain_enum]:
                jobs = [{"legislatura_id": leg} for leg in range(1, current_leg + 1)]
                logger.info(
                    "[%s] Histórico: %s legislaturas (1..%s).",
                    domain_val.upper(),
                    len(jobs),
                    current_leg,
                )
            else:
                jobs = [{"legislatura_id": current_leg}]
                logger.info("[%s] Legislatura atual: %s.", domain_val.upper(), current_leg)

            def leg_mapper(job: dict) -> dict:
                return {"legislatura_id": job["legislatura_id"]}

            return jobs, leg_mapper

        if domain_val == DomainType.FRENTES_MEMBROS.value:
            if self._lake is not None:
                frente_ids = self._lake.list_frente_ids_silver_or_gold(current_leg)
            else:
                frente_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.FRENTES.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )

            if not frente_ids:
                logger.error(
                    "[FRENTES_MEMBROS] Abortando: nenhuma frente no lake. Rode '%s' antes.",
                    DomainType.FRENTES.value,
                )
                return [], lambda x: {}

            if self._lake is not None:
                covered = self._lake.list_entity_ids_with_child_materialized(
                    domain_val, "id_frente"
                )
                frente_ids = filter_entity_ids_pending_child(
                    frente_ids, covered, domain_val, "frentes"
                )

            if not frente_ids:
                logger.info("[FRENTES_MEMBROS] Todas as frentes já possuem membros materializados.")
                return [], lambda x: {}

            batch_size = 20
            jobs = [
                {"frente_ids": frente_ids[i : i + batch_size]}
                for i in range(0, len(frente_ids), batch_size)
            ]
            logger.info("[FRENTES_MEMBROS] %s frentes em %s lotes.", len(frente_ids), len(jobs))

            def frentes_membros_mapper(job: dict) -> dict:
                return {"frente_ids": job["frente_ids"]}

            return jobs, frentes_membros_mapper

        if domain_val in _PROPOSICAO_CHILDREN:
            if self._lake is not None:
                proposicao_ids = self._lake.list_proposicao_ids_silver_or_gold(start, end)
            else:
                proposicao_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.PROPOSICOES.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )

            if not proposicao_ids:
                logger.error(
                    "[%s] Abortando: nenhuma proposição no lake. Rode '%s' antes.",
                    domain_val.upper(),
                    DomainType.PROPOSICOES.value,
                )
                return [], lambda x: {}

            if self._lake is not None:
                covered = self._lake.list_proposicao_ids_with_child_materialized(domain_val)
                proposicao_ids = filter_proposicao_ids_pending_child(
                    proposicao_ids, covered, domain_val
                )

            if not proposicao_ids:
                logger.info(
                    "[%s] Todas as proposições da janela já possuem dados na Silver/Gold.",
                    domain_val.upper(),
                )
                return [], lambda x: {}

            batch_size = 25
            jobs = [
                {"proposicao_ids": proposicao_ids[i : i + batch_size]}
                for i in range(0, len(proposicao_ids), batch_size)
            ]
            logger.info(
                "[%s] %s proposições em %s lotes.",
                domain_val.upper(),
                len(proposicao_ids),
                len(jobs),
            )

            def proposicao_child_mapper(job: dict) -> dict:
                return {"proposicao_ids": job["proposicao_ids"]}

            return jobs, proposicao_child_mapper

        if domain_val in _EVENTO_CHILDREN:
            if self._lake is not None:
                evento_ids = self._lake.list_evento_ids_silver_or_gold(start, end)
            else:
                evento_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.EVENTOS.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )
            if not evento_ids:
                logger.error(
                    "[%s] Abortando: nenhum evento no lake. Rode '%s' antes.",
                    domain_val.upper(),
                    DomainType.EVENTOS.value,
                )
                return [], lambda x: {}

            parent_col = "id_evento"
            if self._lake is not None:
                covered = self._lake.list_entity_ids_with_child_materialized(domain_val, parent_col)
                evento_ids = filter_entity_ids_pending_child(
                    evento_ids, covered, domain_val, "eventos"
                )
            if not evento_ids:
                logger.info(
                    "[%s] Todos os eventos da janela já materializados.", domain_val.upper()
                )
                return [], lambda x: {}

            batch_size = 20
            jobs = [
                {"evento_ids": evento_ids[i : i + batch_size]}
                for i in range(0, len(evento_ids), batch_size)
            ]
            logger.info(
                "[%s] %s eventos em %s lotes.", domain_val.upper(), len(evento_ids), len(jobs)
            )

            def evento_child_mapper(job: dict) -> dict:
                return {"evento_ids": job["evento_ids"]}

            return jobs, evento_child_mapper

        if domain_val in (DomainType.PARTIDOS_MEMBROS.value, DomainType.PARTIDOS_LIDERES.value):
            if self._lake is not None:
                partido_ids = self._lake.list_partido_ids_silver_or_gold()
            else:
                partido_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.PARTIDOS.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )
            if not partido_ids:
                logger.error(
                    "[%s] Abortando: nenhum partido no lake. Rode '%s' antes.",
                    domain_val.upper(),
                    DomainType.PARTIDOS.value,
                )
                return [], lambda x: {}

            parent_col = "id_partido"
            if self._lake is not None:
                covered = self._lake.list_entity_ids_with_child_materialized(domain_val, parent_col)
                partido_ids = filter_entity_ids_pending_child(
                    partido_ids, covered, domain_val, "partidos"
                )
            if not partido_ids:
                logger.info("[%s] Todos os partidos já materializados.", domain_val.upper())
                return [], lambda x: {}

            batch_size = 15
            jobs = [
                {
                    "partido_ids": partido_ids[i : i + batch_size],
                    "start_date": start,
                    "end_date": end,
                    "legislatura_id": current_leg,
                }
                for i in range(0, len(partido_ids), batch_size)
            ]
            logger.info(
                "[%s] %s partidos em %s lotes.", domain_val.upper(), len(partido_ids), len(jobs)
            )

            def partido_child_mapper(job: dict) -> dict:
                return {
                    "partido_ids": job["partido_ids"],
                    "start_date": job["start_date"],
                    "end_date": job["end_date"],
                    "legislatura_id": job["legislatura_id"],
                }

            return jobs, partido_child_mapper

        if domain_val == DomainType.BLOCOS_PARTIDOS.value:
            if self._lake is not None:
                bloco_ids = self._lake.list_bloco_ids_silver_or_gold(current_leg)
            else:
                bloco_ids = self._state_store.get_existing_ids(
                    table_name=DomainType.BLOCOS.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                )
            if not bloco_ids:
                logger.error(
                    "[BLOCOS_PARTIDOS] Abortando: nenhum bloco no lake. Rode '%s' antes.",
                    DomainType.BLOCOS.value,
                )
                return [], lambda x: {}

            if self._lake is not None:
                covered = self._lake.list_entity_ids_with_child_materialized(domain_val, "id_bloco")
                bloco_ids = filter_entity_ids_pending_child(
                    bloco_ids, covered, domain_val, "blocos"
                )
            if not bloco_ids:
                logger.info("[BLOCOS_PARTIDOS] Todos os blocos já materializados.")
                return [], lambda x: {}

            batch_size = 20
            jobs = [
                {"bloco_ids": bloco_ids[i : i + batch_size]}
                for i in range(0, len(bloco_ids), batch_size)
            ]
            logger.info("[BLOCOS_PARTIDOS] %s blocos em %s lotes.", len(bloco_ids), len(jobs))

            def blocos_partidos_mapper(job: dict) -> dict:
                return {"bloco_ids": job["bloco_ids"]}

            return jobs, blocos_partidos_mapper

        if domain_val == DomainType.REFERENCIAS.value:
            from ipolitico.extractors.camara.api.referencias import REFERENCE_ROUTES

            jobs = [{"routes": list(REFERENCE_ROUTES)}]
            logger.info("[REFERENCIAS] %s catálogos em 1 job.", len(REFERENCE_ROUTES))

            def referencias_mapper(job: dict) -> dict:
                return {"routes": job["routes"]}

            return jobs, referencias_mapper

        jobs = [{"start_date": start, "end_date": end}]

        def default_mapper(job: dict) -> dict:
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        return jobs, default_mapper
