import argparse
import asyncio
import logging
import time
from pathlib import Path

import yaml

from ipolitico.core.client import CamaraClient
from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.manager import PipelineManager
from ipolitico.pipeline.optimizer import DataLakeOptimizer
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.sinks.datalake_sink import DataLakeSink

logger = logging.getLogger(__name__)


def load_config(file_path: Path) -> dict:
    """Carrega as definições dinâmicas de pipeline em formato YAML."""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main():
    """
    Ponto de Entrada (CLI).
    Lê os parâmetros do usuário, monta as peças e aciona o Gestor. Nenhuma
    regra de negócio ou IFs de domínio ocorrem aqui.
    """
    parser = argparse.ArgumentParser(description="Motor ETL iPolitico")
    parser.add_argument(
        "--source", type=str, default="api", help="Descontinuado - O YAML gerencia a origem."
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Executa a consolidação (Camada Gold) via DuckDB após a ingestão.",
    )
    parser.add_argument(
        "--strategy",
        type=LoadStrategy,
        choices=list(LoadStrategy),
        default=LoadStrategy.INCREMENTAL,
    )
    parser.add_argument(
        "--domains", nargs="+", type=DomainType, choices=list(DomainType), default=list(DomainType)
    )
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)

    args = parser.parse_args()

    start_time = time.perf_counter()
    logger.info("=" * 60)
    logger.info(
        f" iPolitico ETL (Ingestão) | Destino: DATALAKE  |"
        f" Estratégia: {args.strategy.value.upper()}",
    )
    logger.info("=" * 60)

    # Carregar Configuração Remota
    config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "camara_pipeline.yaml"
    pipeline_config = load_config(config_path)

    # Inicializar Infraestrutura Base
    client = CamaraClient()
    builder = PipelineBuilder(client)
    runner = PipelineRunner()

    state_store = DataLakeSink()

    manager = PipelineManager(builder, runner, pipeline_config, state_store)

    try:
        # Orquestrar Domínios
        for domain in args.domains:
            await manager.run_domain(
                domain=domain,
                sink_type=SinkType.DATALAKE,
                strategy=args.strategy,
                start_date=args.start_date,
                end_date=args.end_date,
            )

            if args.optimize and args.sink == SinkType.DATALAKE:
                logger.info(f"=== Otimizando Camada Gold para {domain.value.upper()} ===")
                optimizer = DataLakeOptimizer()
                optimizer.compact_and_deduplicate(domain.value)
    except Exception as e:
        logger.error(f"Falha catastrófica no ETL: {e}")
    finally:
        await client.close()
        logger.info(f"Tempo total de execução: {time.perf_counter() - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
