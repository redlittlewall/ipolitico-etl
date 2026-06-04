"""Estratégias de geração de jobs por tipo de domínio (Strategy Pattern).

Cada classe concreta encapsula a lógica de como um ou mais domínios geram
jobs e mapeadores para extração. Substitui a cadeia if-elif em
`CamaraJobPlanner.build()` e é registrada em `STRATEGY_REGISTRY`.
"""

from __future__ import annotations

import calendar
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

from ipolitico.core.constants import EARLIEST_DATE_MAP, DomainType, MedallionLayer, SourceType
from ipolitico.core.domain_spec import DomainSpec
from ipolitico.pipeline.deputy_universe import resolve_deputy_ids_for_calendar_window
from ipolitico.pipeline.effective_window import resolve_calendar_years
from ipolitico.pipeline.job_resume import (
    filter_deputado_child_jobs,
    filter_despesas_api_jobs,
    filter_entity_ids_pending_child,
    filter_votacao_ids_pending_votos,
)
from ipolitico.pipeline.source_router import ExtractionPlan
from ipolitico.storage.datalake_repository import DataLakeRepository
from ipolitico.storage.state_store import StateStore

logger = logging.getLogger(__name__)


class DomainJobStrategy(ABC):
    """Interface para estratégia de geração de jobs de um domínio."""

    @abstractmethod
    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        """
        Gera a lista de jobs e o mapper de kwargs para um domínio.

        Args:
            domain: Tipo do domínio.
            spec: DomainSpec com metadados do domínio.
            start: Data de início da janela (ISO).
            end: Data de fim da janela (ISO).
            current_leg: ID da legislatura atual.
            anchor_year: Ano âncora da legislatura atual.
            extraction_plan: Plano de extração (API vs Bulk).
            state_store: Store para consulta de watermarks/IDs.
            lake: Repositório do Data Lake (pode ser None).

        Returns:
            Tupla (jobs, mapper) onde jobs é uma lista de dicionários
            e mapper transforma cada job em kwargs de extração.
        """


# ─── Implementações Concretas ────────────────────────────────────────────────


class DeputadosStrategy(DomainJobStrategy):
    """Estratégia para o domínio deputados (legislatura ou date-range)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        if start == EARLIEST_DATE_MAP[DomainType.DEPUTADOS]:
            jobs = [{"legislatura_id": leg} for leg in range(1, current_leg + 1)]
            logger.info(
                "[%s] Estratégia Histórica. Iterando da Legislatura 1 até a atual (%s).",
                domain.value.upper(),
                current_leg,
            )
        else:
            jobs = [{"start_date": start, "end_date": end}]
            logger.info("[%s] Recorte temporal: %s a %s.", domain.value.upper(), start, end)

        def deputados_mapper(job: dict) -> dict:
            if "legislatura_id" in job:
                return {"legislatura_id": job["legislatura_id"]}
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        return jobs, deputados_mapper


class DespesasStrategy(DomainJobStrategy):
    """Estratégia para o domínio despesas (Bulk por ano ou API deputado×ano)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        start_year, end_year = resolve_calendar_years(start, end)

        if extraction_plan.source_type == SourceType.BULK:
            jobs = [{"year": y} for y in range(start_year, end_year + 1)]

            def despesas_bulk_mapper(job: dict) -> dict:
                return {"year": job["year"]}

            logger.info(
                "[%s] BULK CEAP por ano: %s arquivos (%s-%s).",
                domain.value.upper(),
                len(jobs),
                start_year,
                end_year,
            )
            return jobs, despesas_bulk_mapper

        deputados_ids = resolve_deputy_ids_for_calendar_window(
            start_iso=start,
            end_iso=end,
            current_legislature_id=current_leg,
            anchor_year=anchor_year,
            lake=lake,
            state_store=state_store,
        )
        if not deputados_ids:
            logger.warning(
                "[%s] Nenhum deputado encontrado no State Store! "
                "Execute o pipeline de '%s' primeiro.",
                domain.value.upper(),
                DomainType.DEPUTADOS.value,
            )
            return [], lambda x: {}

        jobs = []
        for dep_id in deputados_ids:
            for year in range(start_year, end_year + 1):
                jobs.append({"deputado_id": dep_id, "year": year})

        if lake is not None:
            covered = lake.list_deputy_expense_year_pairs()
            jobs = filter_despesas_api_jobs(jobs, covered)

        logger.info(
            "[%s] Criados %s micro-lotes (deputados na janela: %s, anos %s..%s).",
            domain.value.upper(),
            len(jobs),
            len(deputados_ids),
            start_year,
            end_year,
        )

        def despesas_mapper(job: dict) -> dict:
            return {"deputado_id": job["deputado_id"], "year": job["year"]}

        return jobs, despesas_mapper


class TimeWindowStrategy(DomainJobStrategy):
    """Estratégia para domínios com janela temporal mensal (proposicoes, votacoes, eventos)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        start_year = int(start.split("-")[0])
        start_month = int(start.split("-")[1])
        end_year = int(end.split("-")[0])
        end_month = int(end.split("-")[1])

        jobs: list[dict[str, Any]] = []
        if extraction_plan.source_type == SourceType.BULK:
            for y in range(start_year, end_year + 1):
                jobs.append({"year": y})
            logger.info("[%s] BULK por ano: %s lotes.", domain.value.upper(), len(jobs))

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

        logger.info("[%s] Criados %s micro-lotes mensais.", domain.value.upper(), len(jobs))

        def time_mapper(job: dict) -> dict:
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        return jobs, time_mapper


class DeputyChildStrategy(DomainJobStrategy):
    """Estratégia para domínios filhos de deputados (estáticos e temporais).

    Args:
        include_date_range: Se True, inclui janela temporal nos jobs.
    """

    def __init__(self, include_date_range: bool = False) -> None:
        self.include_date_range = include_date_range

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        deputados_ids = resolve_deputy_ids_for_calendar_window(
            start_iso=start,
            end_iso=end,
            current_legislature_id=current_leg,
            anchor_year=anchor_year,
            lake=lake,
            state_store=state_store,
        )
        if not deputados_ids:
            logger.error(
                "[%s] Abortando: nenhum deputado no lake. Rode '%s' antes.",
                domain.value.upper(),
                DomainType.DEPUTADOS.value,
            )
            return [], lambda x: {}

        if self.include_date_range:
            jobs = [
                {"deputado_id": dep_id, "start_date": start, "end_date": end}
                for dep_id in deputados_ids
            ]

            def temporal_child_mapper(job: dict) -> dict:
                return {
                    "deputado_id": job["deputado_id"],
                    "start_date": job["start_date"],
                    "end_date": job["end_date"],
                }
        else:
            jobs = [{"deputado_id": dep_id} for dep_id in deputados_ids]

            def static_child_mapper(job: dict) -> dict:
                return {"deputado_id": job["deputado_id"]}

        if lake is not None:
            covered = lake.list_deputy_ids_in_child_table(domain.value)
            jobs = filter_deputado_child_jobs(jobs, covered)

        logger.info(
            "[%s] %s jobs (%s requisição/deputado).",
            domain.value.upper(),
            len(jobs),
            "1" if not self.include_date_range else "1+janela",
        )

        mapper = static_child_mapper if not self.include_date_range else temporal_child_mapper
        return jobs, mapper


class VotosStrategy(DomainJobStrategy):
    """Estratégia para o domínio votos (batch de votacao_ids)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        if lake is not None:
            votacoes_ids = lake.list_votacao_ids_silver_or_gold(start, end)
        else:
            votacoes_ids = state_store.get_existing_ids(
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

        if lake is not None:
            covered_votos = lake.list_votacao_ids_with_votos_materialized()
            votacoes_ids = filter_votacao_ids_pending_votos(votacoes_ids, covered_votos)

        if not votacoes_ids:
            logger.info("[VOTOS] Todas as votações da janela já possuem votos na Silver/Gold.")
            return [], lambda x: {}

        batch_size = 20
        jobs = [
            {"votacao_ids": votacoes_ids[i : i + batch_size]}
            for i in range(0, len(votacoes_ids), batch_size)
        ]
        logger.info("[VOTOS] Orquestrando %s votações em %s lotes.", len(votacoes_ids), len(jobs))

        def votos_mapper(job: dict) -> dict:
            return {"votacao_ids": job["votacao_ids"]}

        return jobs, votos_mapper


class OrientacoesStrategy(DomainJobStrategy):
    """Estratégia para o domínio orientacoes (batch de votacao_ids)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        if lake is not None:
            votacoes_ids = lake.list_votacao_ids_silver_or_gold(start, end)
        else:
            votacoes_ids = state_store.get_existing_ids(
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

        if lake is not None:
            covered = lake.list_votacao_ids_with_orientacoes_materialized()
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


class OrgaosStrategy(DomainJobStrategy):
    """Estratégia para o domínio orgaos (1 job com janela)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        jobs = [{"start_date": start, "end_date": end}]
        logger.info("[%s] 1 job (janela %s a %s).", domain.value.upper(), start, end)

        def orgaos_mapper(job: dict) -> dict:
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        return jobs, orgaos_mapper


class PartidosStrategy(DomainJobStrategy):
    """Estratégia para o domínio partidos (1 job + legislatura)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        jobs = [
            {
                "start_date": start,
                "end_date": end,
                "legislatura_id": current_leg,
            }
        ]
        logger.info("[%s] 1 job com legislatura %s.", domain.value.upper(), current_leg)

        def partidos_mapper(job: dict) -> dict:
            return {
                "start_date": job["start_date"],
                "end_date": job["end_date"],
                "legislatura_id": job["legislatura_id"],
            }

        return jobs, partidos_mapper


class LegislaturaScopeStrategy(DomainJobStrategy):
    """Estratégia para domínios com escopo por legislatura (blocos, frentes)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        if start == EARLIEST_DATE_MAP.get(
            DomainType(domain.value), EARLIEST_DATE_MAP[DomainType.DEPUTADOS]
        ):
            jobs = [{"legislatura_id": leg} for leg in range(1, current_leg + 1)]
            logger.info(
                "[%s] Histórico: %s legislaturas (1..%s).",
                domain.value.upper(),
                len(jobs),
                current_leg,
            )
        else:
            jobs = [{"legislatura_id": current_leg}]
            logger.info("[%s] Legislatura atual: %s.", domain.value.upper(), current_leg)

        def leg_mapper(job: dict) -> dict:
            return {"legislatura_id": job["legislatura_id"]}

        return jobs, leg_mapper


class _ParentBatchedBuilder:
    """Builder helper para construir estratégias de batch parametrizadas.

    Cada instância é usada como callable de resolução de IDs pais dentro de
    `ParentBatchedStrategy`.
    """


class ParentBatchedStrategy(DomainJobStrategy):
    """Estratégia parametrizada para domínios que iteram sobre IDs pais.

    Args:
        parent_key: Nome da chave no job dict (ex: "orgao_ids", "evento_ids").
        batch_size: Tamanho do lote.
        resolve_fn: Função que retorna lista de IDs pais.
            Assinatura: (lake, state_store, start, end, current_leg, domain_val) -> list[Any]
        extra_params: Parâmetros extras estáticos incluídos em cada job.
            Pode ser um dict fixo ou uma callable(start, end, current_leg) -> dict
            para parâmetros que variam por chamada de build().
        parent_col: Nome da coluna do pai para filtro de materialização.
    """

    def __init__(
        self,
        parent_key: str,
        batch_size: int,
        resolve_fn: Callable[..., list[Any]],
        extra_params: dict[str, Any] | Callable[[str, str, int], dict[str, Any]] | None = None,
        parent_col: str | None = None,
    ) -> None:
        self.parent_key = parent_key
        self.batch_size = batch_size
        self.resolve_fn = resolve_fn
        self.extra_params = extra_params or {}
        self.parent_col = parent_col or parent_key.replace("_ids", "")

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        domain_val = domain.value

        parent_ids = self.resolve_fn(
            lake=lake,
            state_store=state_store,
            start=start,
            end=end,
            current_leg=current_leg,
            domain_val=domain_val,
        )
        if not parent_ids:
            logger.error("[%s] Abortando: nenhum ID pai no lake.", domain_val.upper())
            return [], lambda x: {}

        if lake is not None:
            covered = lake.list_entity_ids_with_child_materialized(domain_val, self.parent_col)
            parent_ids = filter_entity_ids_pending_child(
                parent_ids, covered, domain_val, self.parent_col
            )
        if not parent_ids:
            logger.info("[%s] Todos os pais já materializados.", domain_val.upper())
            return [], lambda x: {}

        # Resolve extra params: suporta dict estático OU callable(start, end, current_leg)
        resolved_extra = (
            self.extra_params(start, end, current_leg)
            if callable(self.extra_params)
            else self.extra_params
        )

        jobs = [
            {self.parent_key: parent_ids[i : i + self.batch_size], **resolved_extra}
            for i in range(0, len(parent_ids), self.batch_size)
        ]
        logger.info(
            "[%s] %s IDs pais em %s lotes.",
            domain_val.upper(),
            len(parent_ids),
            len(jobs),
        )

        def parent_batched_mapper(job: dict) -> dict:
            return {**job}

        return jobs, parent_batched_mapper


class DetailStrategy(DomainJobStrategy):
    """Estratégia para domínios de detalhe (*_detalhe), com batch entity_ids."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        domain_val = domain.value
        entity_ids, upstream = self._resolve_detail_entity_ids(
            domain_val, start, end, current_leg, anchor_year, lake, state_store
        )
        if not entity_ids:
            logger.error(
                "[%s] Abortando: nenhum ID no lake. Rode '%s' antes.",
                domain_val.upper(),
                upstream,
            )
            return [], lambda x: {}

        if lake is not None:
            covered = lake.list_entity_ids_with_child_materialized(domain_val, "id")
            entity_ids = filter_entity_ids_pending_child(
                entity_ids, covered, domain_val, "entidades"
            )
        if not entity_ids:
            logger.info("[%s] Detalhes já materializados.", domain_val.upper())
            return [], lambda x: {}

        batch_size = 25
        jobs = [
            {"entity_ids": entity_ids[i : i + batch_size]}
            for i in range(0, len(entity_ids), batch_size)
        ]
        logger.info("[%s] %s IDs em %s lotes.", domain_val.upper(), len(entity_ids), len(jobs))

        def detail_mapper(job: dict) -> dict:
            return {"entity_ids": job["entity_ids"]}

        return jobs, detail_mapper

    @staticmethod
    def _resolve_detail_entity_ids(
        domain_val: str,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        lake: DataLakeRepository | None,
        state_store: StateStore,
    ) -> tuple[list[Any], str]:
        """Resolve IDs de entidades para processamento de detalhe."""
        if domain_val == DomainType.DEPUTADOS_DETALHE.value:
            ids = resolve_deputy_ids_for_calendar_window(
                start_iso=start,
                end_iso=end,
                current_legislature_id=current_leg,
                anchor_year=anchor_year,
                lake=lake,
                state_store=state_store,
            )
            return ids, DomainType.DEPUTADOS.value

        if domain_val == DomainType.ORGAOS_DETALHE.value:
            if lake:
                return lake.list_orgao_ids_silver_or_gold(), DomainType.ORGAOS.value
            return (
                state_store.get_existing_ids(
                    table_name=DomainType.ORGAOS.value,
                    layer=MedallionLayer.SILVER.value,
                    column="id",
                ),
                DomainType.ORGAOS.value,
            )

        if domain_val == DomainType.EVENTOS_DETALHE.value:
            if lake:
                return lake.list_evento_ids_silver_or_gold(start, end), DomainType.EVENTOS.value
            return [], DomainType.EVENTOS.value

        if domain_val == DomainType.VOTACOES_DETALHE.value:
            if lake:
                return (
                    lake.list_votacao_ids_silver_or_gold(start, end),
                    DomainType.VOTACOES.value,
                )
            return [], DomainType.VOTACOES.value

        if domain_val == DomainType.FRENTES_DETALHE.value:
            if lake:
                return lake.list_frente_ids_silver_or_gold(current_leg), DomainType.FRENTES.value
            return [], DomainType.FRENTES.value

        if domain_val == DomainType.PARTIDOS_DETALHE.value:
            if lake:
                return lake.list_partido_ids_silver_or_gold(), DomainType.PARTIDOS.value
            return [], DomainType.PARTIDOS.value

        if domain_val == DomainType.GRUPOS_DETALHE.value:
            if lake:
                return lake.list_grupo_ids_silver_or_gold(), DomainType.GRUPOS.value
            return [], DomainType.GRUPOS.value

        if domain_val == DomainType.LEGISLATURAS_DETALHE.value:
            if start == EARLIEST_DATE_MAP[DomainType.LEGISLATURAS]:
                return list(range(1, current_leg + 1)), DomainType.LEGISLATURAS.value
            return [current_leg], DomainType.LEGISLATURAS.value

        if domain_val == DomainType.BLOCOS_DETALHE.value:
            if lake:
                return lake.list_bloco_ids_silver_or_gold(current_leg), DomainType.BLOCOS.value
            return [], DomainType.BLOCOS.value

        if domain_val == DomainType.PROPOSICOES_DETALHE.value:
            if lake:
                return (
                    lake.list_proposicao_ids_silver_or_gold(start, end),
                    DomainType.PROPOSICOES.value,
                )
            return [], DomainType.PROPOSICOES.value

        return [], ""


class ReferenciasStrategy(DomainJobStrategy):
    """Estratégia para o domínio referencias (1 job com rotas fixas)."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        # Import lazy para evitar dependência circular
        from ipolitico.extractors.camara.api.referencias import REFERENCE_ROUTES

        jobs = [{"routes": list(REFERENCE_ROUTES)}]
        logger.info("[REFERENCIAS] %s catálogos em 1 job.", len(REFERENCE_ROUTES))

        def referencias_mapper(job: dict) -> dict:
            return {"routes": job["routes"]}

        return jobs, referencias_mapper


class DefaultWindowStrategy(DomainJobStrategy):
    """Estratégia fallback: 1 job com janela temporal."""

    def build(
        self,
        domain: DomainType,
        spec: DomainSpec,
        start: str,
        end: str,
        current_leg: int,
        anchor_year: int,
        extraction_plan: ExtractionPlan,
        state_store: StateStore,
        lake: DataLakeRepository | None,
    ) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]:
        jobs = [{"start_date": start, "end_date": end}]

        def default_mapper(job: dict) -> dict:
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        return jobs, default_mapper


# ─── Helpers de resolução para ParentBatchedStrategy ────────────────────────


def _resolve_orgao_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    **kwargs: Any,
) -> list[Any]:
    if lake:
        return lake.list_orgao_ids_silver_or_gold()
    return state_store.get_existing_ids(
        table_name=DomainType.ORGAOS.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )


def _resolve_evento_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    start: str,
    end: str,
    **kwargs: Any,
) -> list[Any]:
    if lake:
        return lake.list_evento_ids_silver_or_gold(start, end)
    return state_store.get_existing_ids(
        table_name=DomainType.EVENTOS.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )


def _resolve_proposicao_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    start: str,
    end: str,
    **kwargs: Any,
) -> list[Any]:
    if lake:
        return lake.list_proposicao_ids_silver_or_gold(start, end)
    return state_store.get_existing_ids(
        table_name=DomainType.PROPOSICOES.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )


def _resolve_partido_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    **kwargs: Any,
) -> list[Any]:
    if lake:
        return lake.list_partido_ids_silver_or_gold()
    return state_store.get_existing_ids(
        table_name=DomainType.PARTIDOS.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )


def _resolve_frente_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    current_leg: int,
    **kwargs: Any,
) -> list[Any]:
    if lake:
        return lake.list_frente_ids_silver_or_gold(current_leg)
    return state_store.get_existing_ids(
        table_name=DomainType.FRENTES.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )


def _resolve_bloco_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    current_leg: int,
    **kwargs: Any,
) -> list[Any]:
    if lake:
        return lake.list_bloco_ids_silver_or_gold(current_leg)
    return state_store.get_existing_ids(
        table_name=DomainType.BLOCOS.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )


def _resolve_grupo_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    **kwargs: Any,
) -> list[Any]:
    if lake:
        return lake.list_grupo_ids_silver_or_gold()
    return state_store.get_existing_ids(
        table_name=DomainType.GRUPOS.value,
        layer=MedallionLayer.SILVER.value,
        column="id",
    )


def _resolve_legislatura_ids(
    lake: DataLakeRepository | None,
    state_store: StateStore,
    start: str,
    current_leg: int,
    **kwargs: Any,
) -> list[Any]:
    if start == EARLIEST_DATE_MAP[DomainType.LEGISLATURAS]:
        return list(range(1, current_leg + 1))
    return [current_leg]


# ─── Registry ────────────────────────────────────────────────────────────────


STRATEGY_REGISTRY: dict[DomainType, DomainJobStrategy] = {
    # Domínios raiz
    DomainType.DEPUTADOS: DeputadosStrategy(),
    DomainType.DESPESAS: DespesasStrategy(),
    DomainType.PROPOSICOES: TimeWindowStrategy(),
    DomainType.VOTACOES: TimeWindowStrategy(),
    DomainType.EVENTOS: TimeWindowStrategy(),
    DomainType.ORGAOS: OrgaosStrategy(),
    DomainType.PARTIDOS: PartidosStrategy(),
    DomainType.BLOCOS: LegislaturaScopeStrategy(),
    DomainType.FRENTES: LegislaturaScopeStrategy(),
    DomainType.GRUPOS: DefaultWindowStrategy(),
    DomainType.LEGISLATURAS: DefaultWindowStrategy(),
    # Filhos estáticos de deputado
    DomainType.PROFISSÕES: DeputyChildStrategy(include_date_range=False),
    DomainType.OCUPACOES: DeputyChildStrategy(include_date_range=False),
    DomainType.DEPUTADOS_FRENTES: DeputyChildStrategy(include_date_range=False),
    DomainType.DEPUTADOS_HISTORICO: DeputyChildStrategy(include_date_range=False),
    # Filhos temporais de deputado
    DomainType.DISCURSOS: DeputyChildStrategy(include_date_range=True),
    DomainType.DEPUTADOS_ORGAOS: DeputyChildStrategy(include_date_range=True),
    DomainType.DEPUTADOS_EVENTOS: DeputyChildStrategy(include_date_range=True),
    # Votos e orientações
    DomainType.VOTOS: VotosStrategy(),
    DomainType.ORIENTACOES: OrientacoesStrategy(),
    # Órgãos aninhados
    DomainType.ORGAOS_MEMBROS: ParentBatchedStrategy(
        parent_key="orgao_ids",
        batch_size=15,
        resolve_fn=_resolve_orgao_ids,
        extra_params=lambda start, end, _leg: {"start_date": start, "end_date": end},
        parent_col="id_orgao",
    ),
    DomainType.ORGAOS_EVENTOS: ParentBatchedStrategy(
        parent_key="orgao_ids",
        batch_size=15,
        resolve_fn=_resolve_orgao_ids,
        extra_params=lambda start, end, _leg: {"start_date": start, "end_date": end},
        parent_col="id_orgao",
    ),
    DomainType.ORGAOS_VOTACOES: ParentBatchedStrategy(
        parent_key="orgao_ids",
        batch_size=15,
        resolve_fn=_resolve_orgao_ids,
        extra_params=lambda start, end, _leg: {"start_date": start, "end_date": end},
        parent_col="id_orgao",
    ),
    # Filhos de evento
    DomainType.EVENTOS_DEPUTADOS: ParentBatchedStrategy(
        parent_key="evento_ids",
        batch_size=20,
        resolve_fn=_resolve_evento_ids,
        parent_col="id_evento",
    ),
    DomainType.EVENTOS_VOTACOES: ParentBatchedStrategy(
        parent_key="evento_ids",
        batch_size=20,
        resolve_fn=_resolve_evento_ids,
        parent_col="id_evento",
    ),
    DomainType.EVENTOS_PAUTA: ParentBatchedStrategy(
        parent_key="evento_ids",
        batch_size=20,
        resolve_fn=_resolve_evento_ids,
        parent_col="id_evento",
    ),
    # Filhos de partido
    DomainType.PARTIDOS_MEMBROS: ParentBatchedStrategy(
        parent_key="partido_ids",
        batch_size=15,
        resolve_fn=_resolve_partido_ids,
        extra_params=lambda start, end, leg: {
            "start_date": start,
            "end_date": end,
            "legislatura_id": leg,
        },
        parent_col="id_partido",
    ),
    DomainType.PARTIDOS_LIDERES: ParentBatchedStrategy(
        parent_key="partido_ids",
        batch_size=15,
        resolve_fn=_resolve_partido_ids,
        extra_params=lambda start, end, leg: {
            "start_date": start,
            "end_date": end,
            "legislatura_id": leg,
        },
        parent_col="id_partido",
    ),
    # Filhos de frente
    DomainType.FRENTES_MEMBROS: ParentBatchedStrategy(
        parent_key="frente_ids",
        batch_size=20,
        resolve_fn=_resolve_frente_ids,
        parent_col="id_frente",
    ),
    # Filhos de proposição
    DomainType.TRAMITACOES: ParentBatchedStrategy(
        parent_key="proposicao_ids",
        batch_size=25,
        resolve_fn=_resolve_proposicao_ids,
        parent_col="id_proposicao",
    ),
    DomainType.AUTORES: ParentBatchedStrategy(
        parent_key="proposicao_ids",
        batch_size=25,
        resolve_fn=_resolve_proposicao_ids,
        parent_col="id_proposicao",
    ),
    DomainType.RELACIONADAS: ParentBatchedStrategy(
        parent_key="proposicao_ids",
        batch_size=25,
        resolve_fn=_resolve_proposicao_ids,
        parent_col="id_proposicao",
    ),
    DomainType.TEMAS: ParentBatchedStrategy(
        parent_key="proposicao_ids",
        batch_size=25,
        resolve_fn=_resolve_proposicao_ids,
        parent_col="id_proposicao",
    ),
    DomainType.PROPOSICOES_VOTACOES: ParentBatchedStrategy(
        parent_key="proposicao_ids",
        batch_size=25,
        resolve_fn=_resolve_proposicao_ids,
        parent_col="id_proposicao",
    ),
    # Filhos de bloco
    DomainType.BLOCOS_PARTIDOS: ParentBatchedStrategy(
        parent_key="bloco_ids",
        batch_size=20,
        resolve_fn=_resolve_bloco_ids,
        parent_col="id_bloco",
    ),
    # Filhos de grupo
    DomainType.GRUPOS_MEMBROS: ParentBatchedStrategy(
        parent_key="grupo_ids",
        batch_size=20,
        resolve_fn=_resolve_grupo_ids,
        parent_col="id_grupo",
    ),
    DomainType.GRUPOS_HISTORICO: ParentBatchedStrategy(
        parent_key="grupo_ids",
        batch_size=20,
        resolve_fn=_resolve_grupo_ids,
        parent_col="id_grupo",
    ),
    # Filhos de legislatura
    DomainType.LEGISLATURAS_LIDERES: ParentBatchedStrategy(
        parent_key="legislatura_ids",
        batch_size=10,
        resolve_fn=_resolve_legislatura_ids,
        parent_col="id_legislatura",
    ),
    DomainType.LEGISLATURAS_MESA: ParentBatchedStrategy(
        parent_key="legislatura_ids",
        batch_size=10,
        resolve_fn=_resolve_legislatura_ids,
        parent_col="id_legislatura",
    ),
    # Detalhe
    DomainType.DEPUTADOS_DETALHE: DetailStrategy(),
    DomainType.ORGAOS_DETALHE: DetailStrategy(),
    DomainType.EVENTOS_DETALHE: DetailStrategy(),
    DomainType.VOTACOES_DETALHE: DetailStrategy(),
    DomainType.FRENTES_DETALHE: DetailStrategy(),
    DomainType.PARTIDOS_DETALHE: DetailStrategy(),
    DomainType.GRUPOS_DETALHE: DetailStrategy(),
    DomainType.LEGISLATURAS_DETALHE: DetailStrategy(),
    DomainType.BLOCOS_DETALHE: DetailStrategy(),
    DomainType.PROPOSICOES_DETALHE: DetailStrategy(),
    # Referências
    DomainType.REFERENCIAS: ReferenciasStrategy(),
}


def strategy_for(domain: DomainType) -> DomainJobStrategy:
    """Retorna a estratégia registrada para o domínio, ou a fallback DefaultWindowStrategy."""
    return STRATEGY_REGISTRY.get(domain, DefaultWindowStrategy())
