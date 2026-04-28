import argparse
import asyncio
import time
from datetime import datetime
from enum import Enum

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.core.logger import setup_logger
from ipolitico.extractors.camara.bulk.factory import CamaraExtractorFactory
from ipolitico.sinks.datalake_sink import DataLakeSink
from ipolitico.sinks.sqlite_sink import SQLiteSink

logger = setup_logger()

"""
Orquestrador Principal do ETL iPolitico.
Responsável por gerir o ciclo de vida da extração de dados,
garantindo tolerância a falhas através de processamento em lotes (chunking).
"""

DOMAINS_EARLIEST_DATES = {
    "deputados": "1826-04-29",
    "proposicoes": "1988-01-01",
    "votacoes": "1991-01-01",
    "despesas": "2009-01-01",
}


class LoadStrategy(Enum):
    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"


def chunk_list(lst: list, n: int):
    """Gera lotes de tamanho n a partir de uma lista para salvamento progressivo."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def run_pipeline(
    sink,
    state_store,
    start_date: str = None,
    end_date: str = None,
    strategy: LoadStrategy = LoadStrategy.INCREMENTAL,
    source: str = "api",
    # domains: list = None,
):
    """
    Executa a pipeline de extração, transformação e carregamento (ETL).

    Delega as extrações aos 'Extractors' instanciados dinamicamente via Factory,
    podendo operar de forma cirúrgica com micro-batching (API) ou através do
    consumo massivo de arquivos estáticos (Bulk). Os resultados são persistidos
    no 'sink', enquanto o controle de estado fica isolado no 'state_store'.

    Args:
        sink (SQLiteSink | DataLakeSink): Destino final dos dados pesados.
        state_store (SQLiteSink): Banco de metadados para controle de watermarks e IDs/
        start_date (str, optional): Data de início ('YYYY-MM-DD'). Se None e a estratégia
            for INCREMENTAL, o sistema calculará o 'watermark' automaticamente.
        end_date (str, optional): Data de fim ('YYYY-MM-DD'). Se None, assume a data atual.
        strategy (LoadStrategy): FULL_LOAD (limpa o período) ou INCREMENTAL (aplica Upsert).
        source (str): Origem dos dados. "api" (paginação JSON) ou "bulk" (Dumps CSV/ZIP).

    Raises:
        Exception: Propaga exceções críticas caso a rede falhe após todas as
            tentativas de retry backoff se esgotarem.
    """

    client = CamaraClient()

    # Injeção Dinâmica: O Orquestrador recebe os extratores sem saber se são API ou BULK
    deputados_ext = CamaraExtractorFactory.get_extractor("deputados", source, client, state_store)
    despesas_ext = CamaraExtractorFactory.get_extractor("despesas", source, client, state_store)
    proposicoes_ext = CamaraExtractorFactory.get_extractor(
        "proposicoes", source, client, state_store
    )
    votacoes_ext = CamaraExtractorFactory.get_extractor("votacoes", source, client, state_store)

    try:
        is_full = strategy == LoadStrategy.FULL_LOAD
        actual_start = start_date

        start_year = datetime.strptime(actual_start or "2023-01-01", "%Y-%m-%d").year
        end_year = datetime.strptime(
            end_date or datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d"
        ).year
        anos_alvo = list(range(start_year, end_year + 1))

        # ==========================================
        # 1. DEPUTADOS
        # ==========================================
        logger.info(f"Sincronizando Deputados via {source.upper()}...")

        if source == "bulk":
            await deputados_ext.extract(sink.save, unique_keys="id")

        else:
            await deputados_ext.extract(
                sink.save, start_date=actual_start, end_date=end_date, full_load=is_full
            )

        deputados_ids = state_store.get_existing_ids("deputados")

        # DETALHES CADASTRAIS (Sempre via API)
        if deputados_ids:
            existent_ids = state_store.get_existing_ids("deputados_detalhes")
            ids_to_load = [d for d in deputados_ids if d not in existent_ids]

            if ids_to_load:
                logger.info(
                    f"     ∟ Baixando detalhes de {len(ids_to_load)} deputados (Via API)..."
                )
                detalhes_ext = CamaraExtractorFactory.get_extractor(
                    "deputados", "api", client, state_store
                )
                await detalhes_ext.extract_detalhes(sink.save, ids_to_load)
            else:
                logger.info("     ∟ Detalhes cadastrais já estão atualizados.")

        # ==========================================
        # 2. DESPESAS
        # ==========================================
        if source == "bulk":
            logger.info(f"Sincronizando Despesas de {start_year} a {end_year} via BULK (CSV)...")
            for ano in anos_alvo:
                await despesas_ext.extract(
                    sink.save, unique_keys=["id_deputado", "numDocumento", "codDocumento"], year=ano
                )
        else:
            if is_full:
                start_despesas = start_date or DOMAINS_EARLIEST_DATES["despesas"]
                end_despesas = end_date or datetime.now().strftime("%Y-%m-%d")
                logger.warning(
                    f"[FULL LOAD] Limpando Despesas ({start_despesas} a {end_despesas})..."
                )
                await sink.delete_period(
                    "despesas", start_despesas, end_despesas, date_column="dataDocumento"
                )
            else:
                start_despesas = (
                    state_store.get_watermark("despesas", "dataDocumento") or "2023-02-01"
                )
                end_despesas = end_date or datetime.now().strftime("%Y-%m-%d")
                logger.info(
                    f"Sincronizando Despesas a partir de "
                    f"{start_despesas} até {end_despesas} via API..."
                )

            await despesas_ext.extract(
                sink.save,
                deputados_ids=deputados_ids,
                start_date=start_despesas,
                end_date=end_despesas,
            )

        # ==========================================
        # 3. PROPOSIÇÕES
        # ==========================================
        if source == "bulk":
            logger.info(f"Sincronizando Proposições de {start_year} a {end_year} via BULK...")
            for ano in anos_alvo:
                await proposicoes_ext.extract(sink.save, unique_keys="id", year=ano)
        else:
            if is_full:
                start_prop = start_date or DOMAINS_EARLIEST_DATES["proposicoes"]
                end_prop = end_date or datetime.now().strftime("%Y-%m-%d")
                logger.warning(f"[FULL LOAD] Limpando Proposições ({start_prop} a {end_prop})...")
                await sink.delete_period(
                    "proposicoes", start_prop, end_prop, date_column="dataApresentacao"
                )
            else:
                start_prop = (
                    state_store.get_watermark("proposicoes", "dataApresentacao") or "2023-02-01"
                )
                end_prop = end_date or datetime.now().strftime("%Y-%m-%d")

            logger.info(
                f"Sincronizando Proposições a partir de {start_prop} até {end_prop} via API..."
            )
            await proposicoes_ext.extract(sink.save, start_prop, end_prop)

        # ==========================================
        # 4. VOTAÇÕES E VOTOS NOMINAIS
        # ==========================================
        if source == "bulk":
            logger.info(f"Sincronizando Votações e Votos de {start_year} a {end_year} via BULK...")
            for ano in anos_alvo:
                await votacoes_ext.extract(sink.save, unique_keys="id", year=ano)

                votos_ext = CamaraExtractorFactory.get_extractor("votos", "bulk", client)
                await votos_ext.extract(
                    sink.save, unique_keys=["idVotacao", "deputado_id"], year=ano
                )
        else:
            if is_full:
                start_votacoes = start_date or DOMAINS_EARLIEST_DATES["votacoes"]
                end_votacoes = end_date or datetime.now().strftime("%Y-%m-%d")
                logger.warning(
                    f"[FULL LOAD] Limpando Votações ({start_votacoes} a {end_votacoes})..."
                )
                await sink.delete_period(
                    "votacoes", start_votacoes, end_votacoes, date_column="data"
                )
            else:
                start_votacoes = state_store.get_watermark("votacoes", "data") or "1991-01-01"
                end_votacoes = end_date or datetime.now().strftime("%Y-%m-%d")

            await votacoes_ext.extract(sink.save, start_date=start_votacoes, end_date=end_votacoes)

        logger.info("Pipeline finalizado com sucesso!")

    except Exception as e:
        logger.error(f"Falha crítica capturada no orquestrador: {e}")
        raise
    finally:
        await client.close()


async def main():
    parser = argparse.ArgumentParser(description="Motor ETL iPolitico - Dados da Câmara")

    parser.add_argument(
        "--source",
        type=str,
        choices=["api", "bulk"],
        default="api",
        help="Origem dos dados: 'api' (paginada) ou 'bulk' (arquivos massivos)",
    )
    parser.add_argument(
        "--sink",
        type=str,
        choices=["sqlite", "datalake"],
        default="sqlite",
        help="Destino dos dados (sqlite transacional ou datalake parquet).",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["incremental", "full_load"],
        default="incremental",
        help="Estratégia de sincronização.",
    )
    # parser.add_argument(
    #     "--domains",
    #     nargs="+",
    #     default=None,
    #     help="Lista de domínios a processar",
    # )

    parser.add_argument("--start-date", type=str, default=None, help="Data Inicial (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="Data Final (YYYY-MM-DD)")

    args = parser.parse_args()

    start_time = time.perf_counter()
    logger.info("=" * 60)
    logger.info(
        f" Iniciando iPolitico | Origem: {args.source.upper()} | Sink: {args.sink.upper()}"
        f" | Estratégia: {args.strategy.upper()}"
    )
    logger.info("=" * 60)

    state_store = SQLiteSink(db_path=SQLITE_DB_PATH)
    data_sink = SQLiteSink(db_path=SQLITE_DB_PATH) if args.sink == "sqlite" else DataLakeSink()

    if args.strategy == "full_load" and not args.start_date:
        hoje = datetime.now().strftime("%Y-%m-%d")
        primeiro_dia_mes = datetime.now().strftime("%Y-%m-01")
        actual_start, actual_end = primeiro_dia_mes, hoje
    else:
        actual_start, actual_end = args.start_date, args.end_date

    strat_enum = (
        LoadStrategy.FULL_LOAD if args.strategy == "full_load" else LoadStrategy.INCREMENTAL
    )

    await run_pipeline(
        sink=data_sink,
        state_store=state_store,
        start_date=actual_start,
        end_date=actual_end,
        strategy=strat_enum,
        source=args.source,
        # domains=args.domains,
    )

    logger.info(f"Tempo total: {time.perf_counter() - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
