import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

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
            # DomainType.DEPUTADOS: "id",
            DomainType.DESPESAS: "dataDocumento",
            DomainType.PROPOSICOES: "dataApresentacao",
            DomainType.VOTACOES: "data",
        }
        return mapping.get(domain)

    def _resolve_dates(
        self,
        domain: DomainType,
        strategy: LoadStrategy,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Calcula a janela de tempo real baseada na estratégia (Incremental vs Full Load).
        Trata entidades dimensionais de forma isolada, forçando a janela completa.

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

        # Busca a data mais antiga possível para o domínio (ex: 1826 para deputados)
        earliest_possible = EARLIEST_DATE_MAP.get(domain.value, "1826-04-29")

        if strategy == LoadStrategy.FULL_LOAD:
            actual_start = earliest_possible
            logger.info(
                f"[{domain.value.upper()}] Estratégia FULL LOAD."
                f" Iniciando extração do zero a partir de {actual_start}."
            )
            return actual_start, actual_end

        watermark_col = self._resolve_watermark_column(domain)

        # SRP e Defensive Programming:
        # Se não há coluna de watermark configurada, é uma tabela dimensional (ex: Deputados).
        # Assumimos a janela completa e deixamos o UPSERT do Sink atualizar o que mudou.
        if not watermark_col:
            logger.info(
                f"[{domain.value.upper()}] Entidade dimensional detectada."
                " Assumindo janela completa para atualização (UPSERT)."
            )
            return earliest_possible, actual_end

        # Estratégia INCREMENTAL para Fatos: Consulta o State Store real
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

    def _generate_jobs(
        self, domain: DomainType, start: str, end: str
    ) -> Tuple[List[Dict[str, Any]], Callable[[Dict[str, Any]], Dict[str, Any]]]:
        """
        Gera os micro-lotes (jobs) baseados na regra de negócio da entidade.

        Args:
            domain (DomainType): O domínio sendo extraído.
            start (str): Data inicial da janela de orquestração.
            end (str): Data final da janela de orquestração.

        Returns:
            Tuple[List[Dict], Callable]: Uma tupla contendo a lista de jobs
            e a função mapper que adapta as chaves para os kwargs do Extrator.
        """
        domain_val = domain.value if hasattr(domain, "value") else str(domain)

        if domain_val == DomainType.DESPESAS.value:
            # Regra Específica: Despesas exigem iteração por (Deputado, Ano)
            deputados_ids = self.state_store.get_existing_ids(
                DomainType.DEPUTADOS.value, ApiParams.ID.value
            )

            if not deputados_ids:
                logger.warning(
                    f"[{domain_val.upper()}] Nenhum deputado encontrado no State Store! "
                    f"Execute o pipeline de '{DomainType.DEPUTADOS.value}' primeiro."
                )
                return [], lambda x: {}

            start_year = int(start.split("-")[0])
            end_year = int(end.split("-")[0])

            jobs = []
            for dep_id in deputados_ids:
                for year in range(start_year, end_year + 1):
                    jobs.append({"deputado_id": dep_id, "year": year})

            logger.info(f"[{domain_val.upper()}] Criados {len(jobs)} micro-lotes (Deputado x Ano).")

            def despesas_mapper(job: dict) -> dict:
                return {"deputado_id": job["deputado_id"], "year": job["year"]}

            return jobs, despesas_mapper

        # Regra Padrão: Apenas envia o range de tempo
        jobs = [{"start_date": start, "end_date": end}]

        def default_mapper(job: dict) -> dict:
            return {"start_date": job["start_date"], "end_date": job["end_date"]}

        return jobs, default_mapper

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

        # Define o trabalho (Jobs) e o mapeador de parâmetros
        jobs, extract_kwargs_mapper = self._generate_jobs(domain, start, end)

        if not jobs:
            return

        # Resolve Chaves Primárias para Upsert Seguro
        unique_keys = ApiParams.ID.value
        domain_val = domain.value if hasattr(domain, "value") else str(domain)
        if domain_val == DomainType.DESPESAS.value:
            unique_keys = [ApiParams.DEPUTADO_ID.value, "numDocumento", "codDocumento"]

        # Executa o fluxo assíncrono (Runner)
        await self.runner.execute(
            components=components,
            items=jobs,
            extract_kwargs_mapper=extract_kwargs_mapper,
            table_name=domain.value,
            layer=MedallionLayer.SILVER,
            unique_keys=unique_keys,
        )
