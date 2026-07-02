import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ipolitico.core.constants import (
    EARLIEST_DATE_MAP,
    DomainType,
    LoadStrategy,
    MedallionLayer,
    SinkType,
    SourceType,
)
from ipolitico.core.domain_spec import spec_for
from ipolitico.core.legislature import legislature_anchor_year_from_iso
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.planners.camara_jobs import JobPlanner
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.pipeline.source_router import SourceRouter
from ipolitico.pipeline.window_resolver import WindowResolver, resolve_effective_iso_window
from ipolitico.storage.datalake_repository import DataLakeRepository
from ipolitico.storage.state_store import StateStore

logger = logging.getLogger(__name__)


class PipelineManager:
    """
    Gestor de Orquestração de Domínios e Watermarks.

    Gerencia o ciclo de vida dos dados, decidindo a janela de extração com base
    em watermarks reais consultados no banco (Estratégia Incremental) ou reiniciando
    o estado desde a origem dos tempos (Full Load).

    Otimiza execuções incrementais:
    - Domínios estáveis (stable=True) com Silver existente são pulados.
    - Filhos de um domínio que não produziu dados na mesma execução são pulados.
    - Warmup pode ser desligado via flag ``warmup=False``.
    """

    def __init__(
        self,
        builder: PipelineBuilder,
        runner: PipelineRunner,
        config: Dict[str, Any],
        state_store: StateStore,
        metadata_service,
        lake_repository: Optional[DataLakeRepository] = None,
    ):
        self.builder = builder
        self.runner = runner
        self.config = config
        self.state_store = state_store
        self._metadata = metadata_service

        self._lake: Optional[DataLakeRepository] = lake_repository
        if self._lake is None and hasattr(state_store, "base_dir"):
            self._lake = DataLakeRepository.from_sink(state_store)
        if self._lake is None:
            from ipolitico.core.config import DATA_DIR

            self._lake = DataLakeRepository(DATA_DIR / "datalake")

        self._job_planner = JobPlanner(state_store=self._lake, lake_repository=self._lake)
        self._window_resolver = WindowResolver(state_store=self._lake)

        # Rastreamento de domínios que produziram dados nesta execução.
        # Usado para pular filhos cujo pai não gerou dados novos.
        self._domains_with_new_data: set[str] = set()

    async def run_domain(
        self,
        domain: DomainType,
        sink_type: SinkType,
        strategy: LoadStrategy,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        warmup: bool = True,
    ) -> None:
        logger.info(f"=== Inicializando Domínio: {domain.value.upper()} ===")

        # ── Skip domínios estáveis se já têm Silver ────────────────────────
        if self._window_resolver.should_skip_stable(domain):
            return

        domain_cfg = self.config.get("domain_configs", {}).get(domain.value)
        if not domain_cfg:
            logger.error(f"Configuração não encontrada no YAML para o domínio {domain.value}")
            return

        # ── Skip filhos se pai não produziu dados nesta execução ────────────
        spec = spec_for(domain)
        if spec and spec.depends_on:
            parent_domains_updated = {
                p.value for p in spec.depends_on if p.value in self._domains_with_new_data
            }
            parents_missing = {p.value for p in spec.depends_on} - parent_domains_updated
            if parents_missing:
                logger.info(
                    "[%s] Pais %s não produziram dados nesta execução. "
                    "Saltando filho (não há dados novos).",
                    domain.value.upper(),
                    parents_missing,
                )
                return

        current_leg = await self._metadata.get_current_legislature_id()
        legis_start = await self._metadata.get_legislature_start_date(current_leg)
        anchor_year = legislature_anchor_year_from_iso(legis_start, datetime.now().year)
        logger.debug(
            "[%s] Legislatura atual=%s dataInicio=%s ano_ancora=%s",
            domain.value.upper(),
            current_leg,
            legis_start,
            anchor_year,
        )

        start, end = self._window_resolver.resolve(domain, strategy, start_date, end_date)

        earliest_possible = EARLIEST_DATE_MAP.get(domain, "1826-04-29")
        wm_col = self._window_resolver.watermark_column(domain)

        eff_start, eff_end = resolve_effective_iso_window(
            domain,
            orchestration_start=start,
            orchestration_end=end,
            earliest_possible=earliest_possible,
            strategy=strategy,
            state_store=self._lake,
            watermark_column=wm_col,
        )
        logger.info(
            f"[{domain.value.upper()}] Janela resolvida {start}→{end}; "
            f"efetiva (piso/hoje) {eff_start}→{eff_end}"
        )

        extraction_plan = SourceRouter.plan(domain, strategy, eff_start, eff_end)
        logger.info(f"[{domain.value.upper()}] Fonte: {extraction_plan.source_type.value.upper()}")

        components = self.builder.build(
            domain_config=domain_cfg,
            sink_type=sink_type,
            source_type=extraction_plan.source_type,
            domain_name=domain.value,
        )

        jobs, extract_kwargs_mapper = self._job_planner.build(
            domain,
            eff_start,
            eff_end,
            current_leg,
            anchor_year,
            extraction_plan,
        )

        if not jobs:
            return

        # Pré-aquecimento seletivo de cache para rotas 504-prone.
        # Apenas domínios listados em WARMUP_CONFIG recebem warmup.
        # Não faz warmup para fontes Bulk (CSV) — não consomem API REST.
        if (
            warmup
            and extraction_plan.source_type != SourceType.BULK
            and hasattr(self.builder, "client")
            and self.builder.client is not None
        ):
            await self.builder.client.warmup_for_domain(domain, jobs)

        # spec já resolvido acima (linha 92)
        unique_keys: list[str] = list(spec.unique_keys) if spec else ["id"]
        t_kwargs: dict[str, Any] = {}
        if spec and spec.sub_domain:
            t_kwargs["sub_domain"] = spec.sub_domain

        if (
            extraction_plan.source_type == SourceType.BULK
            and extraction_plan.bulk_temporal_column
            and extraction_plan.bulk_eff_start_iso
            and extraction_plan.bulk_eff_end_iso
        ):
            from ipolitico.transformers.bulk_window import BulkTemporalFilter

            t_kwargs["bulk_temporal_filter"] = BulkTemporalFilter(
                column=extraction_plan.bulk_temporal_column,
                start_iso=extraction_plan.bulk_eff_start_iso,
                end_iso=extraction_plan.bulk_eff_end_iso,
            )

        data_count = await self.runner.execute(
            components=components,
            items=jobs,
            extract_kwargs_mapper=extract_kwargs_mapper,
            table_name=domain.value,
            layer=MedallionLayer.SILVER,
            unique_keys=unique_keys,
            transform_kwargs=t_kwargs,
        )

        # Rastreia pais que produziram dados para skip de filhos
        if data_count > 0:
            self._domains_with_new_data.add(domain.value)
            logger.debug(
                "[%s] Produziu %d registros — filhos não serão pulados.",
                domain.value.upper(),
                data_count,
            )
