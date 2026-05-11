import argparse
import asyncio
import time
from pathlib import Path

import yaml

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.core.logger import setup_logger
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.manager import PipelineManager
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.sinks.sqlite_sink import SQLiteSink

logger = setup_logger()


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
    parser = argparse.ArgumentParser(description="Motor ETL iPolitico Enterprise")
    parser.add_argument(
        "--source", type=str, default="api", help="Descontinuado - O YAML gerencia a origem."
    )
    parser.add_argument("--sink", type=SinkType, choices=list(SinkType), default=SinkType.SQLITE)
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
        f" iPolitico Enterprise ETL | Sink: {args.sink.value.upper()} |",
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

    state_store = SQLiteSink(db_path=SQLITE_DB_PATH)

    manager = PipelineManager(builder, runner, pipeline_config, state_store)

    try:
        # Orquestrar Domínios
        for domain in args.domains:
            await manager.run_domain(
                domain=domain,
                sink_type=args.sink,
                strategy=args.strategy,
                start_date=args.start_date,
                end_date=args.end_date,
            )
    except Exception as e:
        logger.error(f"Falha catastrófica no ETL: {e}")
    finally:
        await client.close()
        logger.info(f"Tempo total de execução: {time.perf_counter() - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
