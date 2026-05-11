import argparse
import asyncio
import time
from datetime import datetime

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.core.constants import (
    DOMAINS_EARLIEST_DATES,
    DomainType,
    LoadStrategy,
    SinkType,
    SourceType,
)
from ipolitico.core.logger import setup_logger
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.extractors.camara.bulk.factory import CamaraExtractorFactory
from ipolitico.sinks.datalake_sink import DataLakeSink
from ipolitico.sinks.sqlite_sink import SQLiteSink

logger = setup_logger()

"""
Orquestrador Principal do ETL iPolitico.
Responsável por gerir o ciclo de vida da extração de dados,
garantindo tolerância a falhas através de processamento em lotes (chunking).
"""


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
    source: SourceType = SourceType.API,
    domains: list[DomainType] = None,
):
    """
    Executa a pipeline de extração, transformação e carregamento (ETL).

    Delega as extrações aos 'Extractors' instanciados dinamicamente via Factory,
    operando com micro-batching e Backpressure estrito.

    Args:
        sink (SQLiteSink | DataLakeSink): Destino final dos dados.
        state_store (SQLiteSink): Banco de metadados para controle de watermarks.
        start_date (str, optional): Data de início ('YYYY-MM-DD').
        end_date (str, optional): Data de fim ('YYYY-MM-DD').
        strategy (LoadStrategy): FULL_LOAD (recria período) ou INCREMENTAL (Upsert).
        source (str): Origem dos dados ("api" ou "bulk").
        domains (list[str], optional): Lista de domínios a serem extraídos.
            Padrão: ["deputados", "despesas", "proposicoes", "votacoes"].
    """

    client = CamaraClient()

    domains = domains or [
        DomainType.DEPUTADOS,
        DomainType.DESPESAS,
        DomainType.PROPOSICOES,
        DomainType.VOTACOES,
    ]

    # Injeção Dinâmica: O Orquestrador recebe os extratores sem saber se são API ou BULK
    deputados_ext = CamaraExtractorFactory.get_extractor(
        DomainType.DEPUTADOS, source, client, state_store
    )
    despesas_ext = CamaraExtractorFactory.get_extractor(
        DomainType.DESPESAS, source, client, state_store
    )
    proposicoes_ext = CamaraExtractorFactory.get_extractor(
        DomainType.PROPOSICOES, source, client, state_store
    )
    votacoes_ext = CamaraExtractorFactory.get_extractor(
        DomainType.VOTACOES, source, client, state_store
    )
    try:
        is_full = strategy == LoadStrategy.FULL_LOAD
        actual_start = start_date

        start_year = datetime.strptime(actual_start, "%Y-%m-%d").year
        end_year = datetime.strptime(
            end_date or datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d"
        ).year
        anos_alvo = list(range(start_year, end_year + 1))
        deputados_ids = []
        # ==========================================
        # 1. DEPUTADOS
        # ==========================================
        if DomainType.DEPUTADOS in domains:
            logger.info(f"Sincronizando Deputados via {source.value.upper()}...")

            if source == SourceType.BULK:
                await deputados_ext.extract(sink.save, unique_keys="id")

                logger.info("     ∟ Baixando Dumps Biográficos (Profissões e Ocupações)...")
                for sub_domain in ["deputados_profissoes", "deputados_ocupacoes"]:
                    sub_ext = BaseBulkExtractor(client)
                    sub_ext.domain_name = sub_domain
                    await sub_ext.extract(sink.save)

            else:
                await deputados_ext.extract(
                    sink.save, start_date=actual_start, end_date=end_date, full_load=is_full
                )

            # time.sleep(1)
            deputados_ids = sink.get_existing_ids(DomainType.DEPUTADOS.value)

            # DETALHES CADASTRAIS (Sempre via API)
            if deputados_ids:
                existent_ids = sink.get_existing_ids("deputados_detalhes")
                deputados_api_ext = CamaraExtractorFactory.get_extractor(
                    DomainType.DEPUTADOS, SourceType.API, client, state_store
                )
                ids_to_load = [d for d in deputados_ids if d not in existent_ids]
                if ids_to_load:
                    logger.info(
                        f"     ∟ Baixando detalhes de {len(ids_to_load)} deputados (Via API)..."
                    )

                    await deputados_api_ext.extract_detalhes(sink.save, ids_to_load)
                else:
                    logger.info("     ∟ Detalhes cadastrais já estão atualizados.")

                    # ==========================================
                    # DADOS BIOGRÁFICOS (ESTÁTICOS)
                    # ==========================================
                    bio_endpoints = [
                        ("deputados_profissoes", deputados_api_ext.extract_profissoes),
                        ("deputados_ocupacoes", deputados_api_ext.extract_ocupacoes),
                        (
                            "deputados_mandatos_externos",
                            deputados_api_ext.extract_mandatos_externos,
                        ),
                        ("deputados_frentes", deputados_api_ext.extract_frentes),
                        ("deputados_historico", deputados_api_ext.extract_historico),
                    ]

                    for table_name, extract_method in bio_endpoints:
                        existent_ids = set(sink.get_existing_ids(table_name, "id_deputado"))
                        ids_to_load = (
                            deputados_ids
                            if is_full
                            else [d for d in deputados_ids if d not in existent_ids]
                        )

                        if ids_to_load:
                            await extract_method(sink.save, ids_to_load)
                        else:
                            logger.debug(
                                f"     ∟ Tabela {table_name} atualizada. Pulando extração estática."
                            )

                    # ==========================================
                    # ATIVIDADES (TEMPORAIS)
                    # ==========================================
                    end_ativ = end_date or datetime.now().strftime("%Y-%m-%d")
                    earliest_dep = DOMAINS_EARLIEST_DATES["deputados"]

                    dep_meta = sink.get_deputados_legislaturas()

                    temporal_endpoints = [
                        (
                            "deputados_discursos",
                            "dataHoraInicio",
                            deputados_api_ext.extract_discursos,
                        ),
                        ("deputados_orgaos", "dataInicio", deputados_api_ext.extract_orgaos),
                        ("deputados_eventos", "dataHoraInicio", deputados_api_ext.extract_eventos),
                    ]

                    for table_name, date_col, extract_method in temporal_endpoints:
                        if is_full:
                            start_val = start_date or earliest_dep
                        else:
                            watermark = state_store.get_watermark(table_name, date_col)
                            start_val = start_date or (
                                str(watermark).split("T")[0] if watermark else earliest_dep
                            )

                        await extract_method(
                            sink.save, deputados_ids, start_val, end_ativ, dep_meta
                        )

        # ==========================================
        # 2. DESPESAS
        # ==========================================
        if DomainType.DESPESAS in domains:
            if source == SourceType.BULK:
                logger.info(
                    f"Sincronizando Despesas de {start_year} a {end_year} via BULK (CSV)..."
                )
                for ano in anos_alvo:
                    await despesas_ext.extract(
                        sink.save,
                        unique_keys=["id_deputado", "numDocumento", "codDocumento"],
                        year=ano,
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
                    start_despesas = start_date or (
                        str(watermark).split("T")[0]
                        if watermark
                        else DOMAINS_EARLIEST_DATES["despesas"]
                    )
                    end_despesas = end_date or datetime.now().strftime("%Y-%m-%d")
                    logger.info(
                        f"Sincronizando Despesas a partir de "
                        f"{start_despesas} até {end_despesas} via API..."
                    )

                if not deputados_ids:
                    deputados_ids = sink.get_existing_ids(DomainType.DEPUTADOS.value)

                await despesas_ext.extract(
                    sink.save,
                    deputados_ids=deputados_ids,
                    start_date=start_despesas,
                    end_date=end_despesas,
                )

        # ==========================================
        # 3. PROPOSIÇÕES
        # ==========================================
        if DomainType.PROPOSICOES in domains:
            if source == SourceType.BULK:
                logger.info(f"Sincronizando Proposições de {start_year} a {end_year} via BULK...")
                for ano in anos_alvo:
                    await proposicoes_ext.extract(sink.save, unique_keys="id", year=ano)
            else:
                if is_full:
                    start_prop = start_date or DOMAINS_EARLIEST_DATES["proposicoes"]
                    end_prop = end_date or datetime.now().strftime("%Y-%m-%d")
                    logger.warning(
                        f"[FULL LOAD] Limpando Proposições ({start_prop} a {end_prop})..."
                    )
                    await sink.delete_period(
                        "proposicoes", start_prop, end_prop, date_column="dataApresentacao"
                    )
                else:
                    start_prop = start_date or (
                        str(watermark).split("T")[0]
                        if watermark
                        else DOMAINS_EARLIEST_DATES["proposicoes"]
                    )
                    end_prop = end_date or datetime.now().strftime("%Y-%m-%d")

                logger.info(
                    f"Sincronizando Proposições a partir de {start_prop} até {end_prop} via API..."
                )
                await proposicoes_ext.extract(sink.save, start_prop, end_prop)

        # ==========================================
        # 4. VOTAÇÕES E VOTOS NOMINAIS
        # ==========================================
        if DomainType.VOTACOES in domains:
            if source == SourceType.BULK:
                logger.info(
                    f"Sincronizando Votações e Votos de {start_year} a {end_year} via BULK..."
                )
                for ano in anos_alvo:
                    await votacoes_ext.extract(sink.save, unique_keys="id", year=ano)

                    votos_ext = CamaraExtractorFactory.get_extractor(
                        DomainType.VOTOS, SourceType.BULK, client
                    )
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

                logger.info(
                    f"Sincronizando Votações a partir de "
                    f"{start_votacoes} até {end_votacoes} via API..."
                )
                await votacoes_ext.extract(
                    sink.save, start_date=start_votacoes, end_date=end_votacoes
                )

                votacoes_ids = state_store.get_existing_ids("votacoes")
                if votacoes_ids:
                    logger.info(
                        f"     ∟ Extraindo votos nominais para {len(votacoes_ids)} votações..."
                    )
                    await votacoes_ext.extract_votos(sink.save, votacoes_ids)

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
        type=SourceType,
        choices=list(SourceType),
        default=SourceType.API,
        help="Origem dos dados.",
    )
    parser.add_argument(
        "--sink",
        type=SinkType,
        choices=list(SinkType),
        default=SinkType.SQLITE,
        help="Destino dos dados.",
    )
    parser.add_argument(
        "--strategy",
        type=LoadStrategy,
        choices=list(LoadStrategy),
        default=LoadStrategy.INCREMENTAL,
        help="Estratégia de sincronização.",
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        type=DomainType,
        choices=list(DomainType),
        default=None,
        help="Lista de domínios a processar.",
    )

    parser.add_argument("--start-date", type=str, default=None, help="Data Inicial (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="Data Final (YYYY-MM-DD)")

    args = parser.parse_args()

    start_time = time.perf_counter()
    logger.info("=" * 60)
    logger.info(
        f" Iniciando iPolitico | Origem: {args.source.value.upper()}"
        f" | Sink: {args.sink.value.upper()}"
        f" | Estratégia: {args.strategy.value.upper()}"
    )
    logger.info("=" * 60)

    state_store = SQLiteSink(db_path=SQLITE_DB_PATH)

    data_sink = (
        SQLiteSink(db_path=SQLITE_DB_PATH) if args.sink == SinkType.SQLITE else DataLakeSink()
    )

    if args.strategy == LoadStrategy.FULL_LOAD and not args.start_date:
        hoje = datetime.now().strftime("%Y-%m-%d")
        primeiro_dia_mes = datetime.now().strftime("%Y-%m-01")
        actual_start, actual_end = primeiro_dia_mes, hoje
    else:
        actual_start, actual_end = args.start_date, args.end_date

    await run_pipeline(
        sink=data_sink,
        state_store=state_store,
        start_date=actual_start,
        end_date=actual_end,
        strategy=args.strategy,
        source=args.source,
        domains=args.domains,
    )

    logger.info(f"Tempo total: {time.perf_counter() - start_time:.2f}s")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
