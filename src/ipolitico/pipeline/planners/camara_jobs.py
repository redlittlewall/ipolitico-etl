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
    filter_proposicao_ids_pending_child,
    filter_votacao_ids_pending_votos,
)
from ipolitico.pipeline.source_router import ExtractionPlan
from ipolitico.storage.datalake_repository import DataLakeRepository

logger = logging.getLogger(__name__)


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

        if domain_val in (DomainType.PROFISSÕES.value, DomainType.OCUPACOES.value):
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
            logger.info(
                "[%s] %s jobs (1 requisição por deputado na janela).",
                domain_val.upper(),
                len(jobs),
            )

            def child_mapper(job: dict) -> dict:
                return {"deputado_id": job["deputado_id"]}

            return jobs, child_mapper

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

        if domain_val == DomainType.ORGAOS.value:
            jobs = [{"start_date": start, "end_date": end}]
            logger.info("[%s] 1 job (janela %s a %s).", domain_val.upper(), start, end)

            def orgaos_mapper(job: dict) -> dict:
                return {"start_date": job["start_date"], "end_date": job["end_date"]}

            return jobs, orgaos_mapper

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

        if domain_val in (DomainType.TRAMITACOES.value, DomainType.AUTORES.value):
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

        if domain_val == DomainType.DISCURSOS.value:
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
                    "[DISCURSOS] Abortando: nenhum deputado no lake. Rode '%s' antes.",
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

            logger.info("[DISCURSOS] %s jobs (deputado × janela).", len(jobs))

            def discursos_mapper(job: dict) -> dict:
                return {
                    "deputado_id": job["deputado_id"],
                    "start_date": job["start_date"],
                    "end_date": job["end_date"],
                }

            return jobs, discursos_mapper

        jobs = [{"start_date": start, "end_date": end}]

        def default_mapper(job: dict) -> dict:
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        return jobs, default_mapper
