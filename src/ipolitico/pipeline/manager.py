import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from ipolitico.core.constants import (
    EARLIEST_DATE_MAP,
    ApiParams,
    DomainType,
    LoadStrategy,
    MedallionLayer,
    SinkType,
)
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.sinks.base import BaseSink

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
    ):
        """
        Inicializa o gestor do pipeline.

        Args:
            builder (PipelineBuilder): Responsável pela injeção de dependências.
            runner (PipelineRunner): Motor de concorrência.
            config (Dict[str, Any]): Configurações de domínio e subdomínio do YAML.
            state_store (BaseSink): Interface de conexão com o banco para leitura de watermarks.
        """
        self.builder = builder
        self.runner = runner
        self.config = config
        self.state_store = state_store

    def _resolve_watermark_column(self, domain: DomainType) -> str:
        """Define a coluna oficial de Data/Tempo para ser usada como Watermark em cada domínio."""
        mapping = {
            DomainType.DEPUTADOS: "dataHoraInicio",
            DomainType.DESPESAS: "dataDocumento",
            DomainType.PROPOSICOES: "dataApresentacao",
            DomainType.VOTACOES: "data",
        }
        return mapping.get(domain, "data")

    def _resolve_dates(
        self,
        domain: DomainType,
        strategy: LoadStrategy,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Calcula a janela de tempo real baseada na estratégia (Incremental vs Full Load).

        Args:
            domain (DomainType): O domínio sendo avaliado.
            strategy (LoadStrategy): Full Load ou Incremental.
            start_date (str, optional): Data inicial manual via CLI.
            end_date (str, optional): Data final manual via CLI.

        Returns:
            Tuple[str, str]: Tupla contendo a data inicial e final seguras (YYYY-MM-DD).
        """
        actual_end = end_date or datetime.now().strftime("%Y-%m-%d")

        if start_date:
            return start_date, actual_end

        earliest_possible = EARLIEST_DATE_MAP.get(domain, "1826-04-29")

        if strategy == LoadStrategy.FULL_LOAD:
            actual_start = earliest_possible
            logger.info(
                f"[{domain.value.upper()}] Estratégia FULL LOAD."
                f" Iniciando extração do zero a partir de {actual_start}."
            )
        else:
            # Estratégia INCREMENTAL: Consulta o State Store real
            watermark_col = self._resolve_watermark_column(domain)
            watermark = self.state_store.get_watermark(domain.value, watermark_col)

            if watermark:
                # Retorna apenas a data crua do timestamp
                actual_start = str(watermark).split("T")[0]
                logger.info(
                    f"[{domain.value.upper()}] Estratégia INCREMENTAL."
                    f" Retomando da última marca d'água: {actual_start}."
                )
            else:
                actual_start = earliest_possible
                logger.info(
                    f"[{domain.value.upper()}] Tabela sem histórico."
                    f" Iniciando carga inicial a partir de {actual_start}."
                )

        return actual_start, actual_end

    async def run_domain(
        self,
        domain: DomainType,
        sink_type: SinkType,
        strategy: LoadStrategy,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> None:
        """
        Inicia a orquestração de um domínio específico, delegando tarefas aos workers.
        """
        logger.info(f"=== Inicializando Domínio: {domain.value.upper()} ===")

        domain_cfg = self.config.get("domain_configs", {}).get(domain.value)
        if not domain_cfg:
            logger.error(f"Configuração não encontrada no YAML para o domínio {domain.value}")
            return

        # Constrói as dependências (Builder)
        components = self.builder.build(domain_config=domain_cfg, sink_type=sink_type)

        # Resolve as datas consultando o banco
        start, end = self._resolve_dates(domain, strategy, start_date, end_date)

        # Define o trabalho (Jobs)
        # O Runner processará as tarefas. Como nosso fluxo temporal não está quebrando a data
        # ano a ano aqui, passamos a fatia inteira.
        jobs = [{"start_date": start, "end_date": end}]

        def extract_kwargs_mapper(job: dict) -> dict:
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        # 4. Executa o fluxo assíncrono (Runner)
        await self.runner.execute(
            components=components,
            items=jobs,
            extract_kwargs_mapper=extract_kwargs_mapper,
            table_name=domain.value,
            layer=MedallionLayer.SILVER,
            unique_keys=ApiParams.ID.value
            if domain != DomainType.DESPESAS
            else [ApiParams.DEPUTADO_ID.value, "numDocumento", "codDocumento"],
        )
