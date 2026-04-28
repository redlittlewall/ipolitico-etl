import argparse
import asyncio
import time
from datetime import datetime
from enum import Enum

import polars as pl

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
    domains: list = None,
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
        df_deputados = pl.DataFrame()

        if source == "bulk":
            df_deputados = await deputados_ext.extract()

        else:
            df_deputados = await deputados_ext.extract(
                start_date=actual_start, end_date=end_date, full_load=is_full
            )

        if not df_deputados.is_empty():
            await sink.save(df_deputados, "deputados", unique_keys="id")

        deputados_ids = []
        if not df_deputados.is_empty():
            deputados_ids = df_deputados["id"].to_list()
        else:
            deputados_ids = state_store.get_existing_ids("deputados")

        # DETALHES CADASTRAIS (Sempre via API)
        if deputados_ids:
            existent_ids = state_store.get_existing_ids("deputados_detalhes")
            ids_to_load = [d for d in deputados_ids if d not in existent_ids]

            if ids_to_load:
                logger.info(
                    f"     ∟ Baixando detalhes de {len(ids_to_load)} deputados (Via API)..."
                )
                tamanho_lote = 50
                total_lotes = (len(ids_to_load) + tamanho_lote - 1) // tamanho_lote
                checkpoint = max(1, total_lotes // 4)

                try:
                    # Instancia um extrator de API puro só para os detalhes,
                    # caso o principal seja BULK
                    detalhes_ext = CamaraExtractorFactory.get_extractor(
                        "deputados", "api", client, state_store
                    )
                    for i, batch_ids in enumerate(chunk_list(ids_to_load, tamanho_lote), 1):
                        df_detalhes = await detalhes_ext.extract_detalhes(batch_ids)
                        if not df_detalhes.is_empty():
                            await sink.save(df_detalhes, "deputados_detalhes", unique_keys="id")

                        if i == 1 or i == total_lotes or i % checkpoint == 0:
                            logger.info(
                                f"        Progresso: {(i / total_lotes) * 100:.0f}% "
                                f"(Lote {i}/{total_lotes})"
                            )
                except Exception as e:
                    logger.error(f"     ∟ A API rejeitou a extração de detalhes: {e}.")
            else:
                logger.info("     ∟ Detalhes cadastrais já estão atualizados.")

        # ==========================================
        # 2. DESPESAS
        # ==========================================
        if source == "bulk":
            logger.info(f"Sincronizando Despesas de {start_year} a {end_year} via BULK (CSV)...")
            for ano in anos_alvo:
                df_despesas = await despesas_ext.extract(year=ano)
                if not df_despesas.is_empty():
                    await sink.save(df_despesas, "despesas")
                    logger.info(f"     ∟ Ano {ano} salvo com {df_despesas.height} registros.")
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

            tamanho_lote_desp = 20
            total_lotes_desp = (len(deputados_ids) + tamanho_lote_desp - 1) // tamanho_lote_desp
            checkpoint_desp = max(1, total_lotes_desp // 4)

            for i, batch_ids in enumerate(chunk_list(deputados_ids, tamanho_lote_desp), 1):
                df_despesas = await despesas_ext.extract(
                    deputados_ids=batch_ids, start_date=start_despesas, end_date=end_despesas
                )
                if not df_despesas.is_empty():
                    await sink.save(
                        df_despesas,
                        "despesas",
                        unique_keys=["id_deputado", "numDocumento", "codDocumento"],
                    )
                if i == 1 or i == total_lotes_desp or i % checkpoint_desp == 0:
                    logger.info(
                        f"        Progresso: {(i / total_lotes_desp) * 100:.0f}% "
                        f"(Lote {i}/{total_lotes_desp})"
                    )

        # ==========================================
        # 3. PROPOSIÇÕES
        # ==========================================
        if source == "bulk":
            logger.info(f"Sincronizando Proposições de {start_year} a {end_year} via BULK...")
            for ano in anos_alvo:
                df_proposicoes = await proposicoes_ext.extract(year=ano)
                if not df_proposicoes.is_empty():
                    await sink.save(df_proposicoes, "proposicoes")
                    logger.info(f"     ∟ Ano {ano} salvo com {df_proposicoes.height} registros.")
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

            df_proposicoes = await proposicoes_ext.extract(start_prop, end_prop)
            if not df_proposicoes.is_empty():
                await sink.save(df_proposicoes, "proposicoes", unique_keys="id")

        # ==========================================
        # 4. VOTAÇÕES E VOTOS NOMINAIS
        # ==========================================
        if source == "bulk":
            logger.info(f"Sincronizando Votações e Votos de {start_year} a {end_year} via BULK...")
            for ano in anos_alvo:
                df_votacoes = await votacoes_ext.extract(year=ano)
                if not df_votacoes.is_empty():
                    await sink.save(df_votacoes, "votacoes")

                votos_ext = CamaraExtractorFactory.get_extractor("votos", "bulk", client)
                df_votos = await votos_ext.extract(year=ano)
                if not df_votos.is_empty():
                    await sink.save(df_votos, "votos")
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
                logger.info(
                    f"Sincronizando Votações a partir de "
                    f"{start_votacoes} até {end_votacoes} via API..."
                )

            df_votacoes = await votacoes_ext.extract(
                start_date=start_votacoes, end_date=end_votacoes
            )
            if not df_votacoes.is_empty():
                await sink.save(df_votacoes, "votacoes", unique_keys="id")

                votacoes_ids = df_votacoes["id"].to_list()
                tamanho_lote_votos = 50
                total_lotes_votos = (
                    len(votacoes_ids) + tamanho_lote_votos - 1
                ) // tamanho_lote_votos
                checkpoint_votos = max(1, total_lotes_votos // 4)

                logger.info(f"     ∟ Extraindo votos nominais de {len(votacoes_ids)} votações...")

                for i, batch_ids in enumerate(chunk_list(votacoes_ids, tamanho_lote_votos), 1):
                    df_votos = await votacoes_ext.extract_votos(batch_ids)
                    if not df_votos.is_empty():
                        await sink.save(df_votos, "votos", unique_keys=["idVotacao", "deputado_id"])

                    if i == 1 or i == total_lotes_votos or i % checkpoint_votos == 0:
                        logger.info(
                            f"        Progresso: {(i / total_lotes_votos) * 100:.0f}% "
                            f"(Lote {i}/{total_lotes_votos})"
                        )

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
