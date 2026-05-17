import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ipolitico.core.constants import (
    EARLIEST_DATE_MAP,
    ApiParams,
    DomainType,
    LoadStrategy,
    MedallionLayer,
    SinkType,
    SourceType,
)
from ipolitico.core.legislature import legislature_anchor_year_from_iso
from ipolitico.core.schemas import DESPESAS_PARTITION_KEYS
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.effective_window import resolve_effective_iso_window
from ipolitico.pipeline.planners.camara_jobs import CamaraJobPlanner
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.pipeline.source_router import SourceRouter
from ipolitico.pipeline.window_resolver import WindowResolver
from ipolitico.services.metadata import CamaraMetadataService
from ipolitico.sinks.base import BaseSink
from ipolitico.storage.datalake_repository import DataLakeRepository

logger = logging.getLogger(__name__)


class PipelineManager:
    """
    Gestor de Orquestração de Domínios e Watermarks.

    Gerencia o ciclo de vida dos dados, decidindo a janela de extração com base
    em watermarks reais consultados no banco (Estratégia Incremental) ou reiniciando
    o estado desde a origem dos tempos (Full Load).
    """

    def __init__(
        self,
        builder: PipelineBuilder,
        runner: PipelineRunner,
        config: Dict[str, Any],
        state_store: BaseSink,
        metadata_service: Optional[CamaraMetadataService] = None,
        lake_repository: Optional[DataLakeRepository] = None,
    ):
        self.builder = builder
        self.runner = runner
        self.config = config
        self.state_store = state_store
        self._metadata = metadata_service or CamaraMetadataService(builder.client)

        self._lake: Optional[DataLakeRepository] = lake_repository
        if self._lake is None and hasattr(state_store, "base_dir"):
            self._lake = DataLakeRepository.from_sink(state_store)

        self._job_planner = CamaraJobPlanner(self.state_store, self._lake)
        self._window_resolver = WindowResolver(self.state_store)

    async def run_domain(
        self,
        domain: DomainType,
        sink_type: SinkType,
        strategy: LoadStrategy,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> None:
        logger.info(f"=== Inicializando Domínio: {domain.value.upper()} ===")

        domain_cfg = self.config.get("domain_configs", {}).get(domain.value)
        if not domain_cfg:
            logger.error(f"Configuração não encontrada no YAML para o domínio {domain.value}")
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
            state_store=self.state_store,
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

        unique_keys = ApiParams.ID.value
        domain_val = domain.value if hasattr(domain, "value") else str(domain)
        t_kwargs: Dict[str, Any] = {}

        if domain_val == DomainType.DESPESAS.value:
            unique_keys = list(DESPESAS_PARTITION_KEYS)
        elif domain_val == DomainType.VOTOS.value:
            unique_keys = [ApiParams.DEPUTADO_ID.value, "votacao_id"]
            t_kwargs["sub_domain"] = "votos"
        elif domain_val == DomainType.VOTACOES.value:
            t_kwargs["sub_domain"] = "votacoes"
        elif domain_val in (DomainType.PROFISSÕES.value, DomainType.OCUPACOES.value):
            unique_keys = ["id_deputado", "titulo", "entidade", "anoInicio"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.DISCURSOS.value:
            unique_keys = ["id_deputado", "dataHoraInicio"]
        elif domain_val == DomainType.TRAMITACOES.value:
            unique_keys = ["id_proposicao", "sequencia"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.AUTORES.value:
            unique_keys = ["id_proposicao", "ordemAssinatura", "nome"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.ORIENTACOES.value:
            unique_keys = ["votacao_id", "codPartidoBloco", "codTipoLideranca"]
        elif domain_val == DomainType.ORGAOS_MEMBROS.value:
            unique_keys = ["id_orgao", "id", "codTitulo", "dataInicio"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.FRENTES_MEMBROS.value:
            unique_keys = ["id_frente", "id", "codTitulo", "dataInicio"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val in (DomainType.RELACIONADAS.value, DomainType.TEMAS.value):
            unique_keys = (
                ["id_proposicao", "id"]
                if domain_val == DomainType.RELACIONADAS.value
                else ["id_proposicao", "tema"]
            )
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.PROPOSICOES_VOTACOES.value:
            unique_keys = ["id_proposicao", "id"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.DEPUTADOS_FRENTES.value:
            unique_keys = ["id_deputado", "id"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val in (DomainType.DEPUTADOS_ORGAOS.value, DomainType.DEPUTADOS_EVENTOS.value):
            unique_keys = ["id_deputado", "id", "dataInicio"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.DEPUTADOS_HISTORICO.value:
            unique_keys = ["id_deputado", "dataStatus", "idLegislatura"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val in (
            DomainType.EVENTOS_DEPUTADOS.value,
            DomainType.EVENTOS_VOTACOES.value,
            DomainType.EVENTOS_PAUTA.value,
        ):
            unique_keys = (
                ["id_evento", "id"]
                if domain_val != DomainType.EVENTOS_PAUTA.value
                else ["id_evento", "ordem"]
            )
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.PARTIDOS_MEMBROS.value:
            unique_keys = ["id_partido", "id"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.PARTIDOS_LIDERES.value:
            unique_keys = ["id_partido", "id", "titulo", "dataInicio"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.BLOCOS_PARTIDOS.value:
            unique_keys = ["id_bloco", "id"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.REFERENCIAS.value:
            unique_keys = ["referencia", "cod", "sigla", "nome"]
        elif domain_val.endswith("_detalhe"):
            unique_keys = ["id"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val in (
            DomainType.ORGAOS_EVENTOS.value,
            DomainType.ORGAOS_VOTACOES.value,
        ):
            unique_keys = (
                ["id_orgao", "id", "dataHoraInicio"]
                if domain_val == DomainType.ORGAOS_EVENTOS.value
                else ["id_orgao", "id"]
            )
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.GRUPOS_MEMBROS.value:
            unique_keys = ["id_grupo", "id"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val == DomainType.GRUPOS_HISTORICO.value:
            unique_keys = ["id_grupo", "data", "descricao"]
            t_kwargs["sub_domain"] = domain_val
        elif domain_val in (
            DomainType.LEGISLATURAS_LIDERES.value,
            DomainType.LEGISLATURAS_MESA.value,
        ):
            unique_keys = ["id_legislatura", "id", "titulo", "dataInicio"]
            t_kwargs["sub_domain"] = domain_val

        if (
            extraction_plan.source_type == SourceType.BULK
            and extraction_plan.bulk_temporal_column
            and extraction_plan.bulk_eff_start_iso
            and extraction_plan.bulk_eff_end_iso
        ):
            t_kwargs["bulk_temporal_filter"] = (
                extraction_plan.bulk_temporal_column,
                extraction_plan.bulk_eff_start_iso,
                extraction_plan.bulk_eff_end_iso,
            )

        await self.runner.execute(
            components=components,
            items=jobs,
            extract_kwargs_mapper=extract_kwargs_mapper,
            table_name=domain.value,
            layer=MedallionLayer.SILVER,
            unique_keys=unique_keys,
            transform_kwargs=t_kwargs,
        )
