import asyncio
import time
from datetime import datetime
from enum import Enum

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.core.logger import setup_logger
from ipolitico.extractors.camara.deputados import DeputadosExtractor
from ipolitico.extractors.camara.despesas import DespesasExtractor
from ipolitico.extractors.camara.proposicoes import ProposicoesExtractor
from ipolitico.extractors.camara.votacoes import VotacoesExtractor
from ipolitico.sinks.sqlite_sink import SQLiteSink

logger = setup_logger()

"""
Orquestrador Principal do ETL iPolitico.
Responsável por gerir o ciclo de vida da extração de dados da API da Câmara dos Deputados,
garantindo tolerância a falhas através de processamento em lotes (chunking) e consistência
histórica via estratégias de carga (Full Load vs Incremental).
"""

DOMAINS_EARLIEST_DATES = {
    "deputados": "1826-04-29",
    "proposicoes": "1988-01-01",
    "votacoes": "1991-01-01",
    "despesas": "2009-01-01",
}


class LoadStrategy(Enum):
    """
    Define as estratégias de sincronização permitidas no pipeline.

    Attributes:
        FULL_LOAD: Limpa (DELETE) a janela temporal selecionada na base de dados antes de
                   inserir os novos dados. Previne a acumulação de registos "fantasmas"
                   (dados apagados na origem).
        INCREMENTAL: Mantém os dados existentes e utiliza UPSERT para adicionar dados novos
                     ou atualizar os que sofreram alterações.
    """

    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"


def chunk_list(lst: list, n: int):
    """Gera lotes de tamanho n a partir de uma lista para salvamento progressivo."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def run_pipeline(
    start_date: str = None, end_date: str = None, strategy: LoadStrategy = LoadStrategy.INCREMENTAL
):
    """
    Executa a pipeline de extração, transformação e carregamento (ETL).

    Delega as extrações aos 'Extractors' correspondentes e persiste os resultados
    utilizando a estratégia de salvaguarda definida. O processo utiliza lotes
    para garantir que a memória RAM não é esgotada e que o progresso é gravado
    gradualmente em caso de falha de rede.

    Args:
        start_date (str, optional): Data de início no formato 'YYYY-MM-DD'.
            Se None, o sistema calculará o 'watermark' (última data) da base de dados.
        end_date (str, optional): Data de fim no formato 'YYYY-MM-DD'. Se None, assume a data atual.
        strategy (LoadStrategy): A estratégia de carga a aplicar. Padrão: INCREMENTAL.

    Raises:
        Exception: Propaga exceções críticas caso as tentativas de extração (retry backoff) falhem.
    """
    client = CamaraClient()
    sink = SQLiteSink(db_path=SQLITE_DB_PATH)
    # metadata = CamaraMetadataService(client)

    deputados_ext = DeputadosExtractor(client, state_store=sink)
    despesas_ext = DespesasExtractor(client, state_store=sink)
    proposicoes_ext = ProposicoesExtractor(client, state_store=sink)
    votacoes_ext = VotacoesExtractor(client, state_store=sink)

    try:
        is_full = strategy == LoadStrategy.FULL_LOAD

        actual_start = start_date

        logger.info(f"Modo: {strategy.value} | Data Informada: {actual_start or 'Nenhuma'}")

        # --- DEPUTADOS ---
        logger.info("Sincronizando Deputados (Lista Base)...")
        df_deputados = await deputados_ext.extract(
            start_date=actual_start, end_date=end_date, full_load=is_full
        )

        if not df_deputados.is_empty():
            await sink.save(df_deputados, "deputados", unique_keys="id")

        deputados_ids = await deputados_ext.get_all_ids()

        # --- DETALHES CADASTRAIS  ---
        existent_ids = sink.get_existing_ids("deputados_detalhes")
        ids_to_load = [d for d in deputados_ids if d not in existent_ids]

        if ids_to_load:
            logger.info(f"     ∟ Baixando detalhes pendentes de {len(ids_to_load)} deputados...")
            tamanho_lote = 50
            total_lotes = (len(ids_to_load) + tamanho_lote - 1) // tamanho_lote
            checkpoint = max(1, total_lotes // 4)

            for i, batch_ids in enumerate(chunk_list(ids_to_load, tamanho_lote), 1):
                df_detalhes = await deputados_ext.extract_detalhes(batch_ids)
                if not df_detalhes.is_empty():
                    await sink.save(df_detalhes, "deputados_detalhes", unique_keys="id")

                if i == 1 or i == total_lotes or i % checkpoint == 0:
                    percentual = (i / total_lotes) * 100
                    logger.info(f"       ⏳ Progresso: {percentual:.0f}% (Lote {i}/{total_lotes})")
        else:
            logger.info("     ∟ Detalhes cadastrais já estão atualizados.")

        # --- DESPESAS  ---
        # O Orquestrador determina os limites temporais
        if is_full:
            start_despesas = start_date or DOMAINS_EARLIEST_DATES["despesas"]
            end_despesas = end_date or datetime.now().strftime("%Y-%m-%d")
            logger.warning(
                f"[FULL LOAD] Limpando e Sincronizando Despesas "
                f"({start_despesas} a {end_despesas})..."
            )
            await sink.delete_period(
                "despesas", start_despesas, end_despesas, date_column="dataDocumento"
            )
        else:
            start_despesas = sink.get_watermark("despesas", "dataDocumento") or "2023-02-01"
            end_despesas = end_date or datetime.now().strftime("%Y-%m-%d")
            logger.info(
                f"Sincronizando Despesas a partir de {start_despesas} até {end_despesas}..."
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
                percentual = (i / total_lotes_desp) * 100
                logger.info(f"     ⏳ Progresso: {percentual:.0f}% (Lote {i}/{total_lotes_desp})")

        # --- PROPOSIÇÕES ---
        if is_full:
            start_prop = start_date or DOMAINS_EARLIEST_DATES["proposicoes"]
            end_prop = end_date or datetime.now().strftime("%Y-%m-%d")
            logger.warning(
                f"[FULL LOAD] Limpando e Sincronizando Proposições ({start_prop} a {end_prop})..."
            )
            await sink.delete_period("proposicoes", start_prop, end_prop, "dataApresentacao")
        else:
            start_prop = sink.get_watermark("proposicoes", "dataApresentacao") or "2023-02-01"
            end_prop = end_date or datetime.now().strftime("%Y-%m-%d")
            logger.info(f"Sincronizando Proposições a partir de {start_prop} até {end_prop}...")

        df_proposicoes = await proposicoes_ext.extract(start_prop, end_prop)

        if not df_proposicoes.is_empty():
            await sink.save(df_proposicoes, "proposicoes", unique_keys="id")

        # --- VOTAÇÕES E VOTOS NOMINAIS ---
        if is_full:
            start_votacoes = start_date or DOMAINS_EARLIEST_DATES["votacoes"]
            end_votacoes = end_date or datetime.now().strftime("%Y-%m-%d")
            logger.warning(
                f"[FULL LOAD] Limpando e Sincronizando Votações "
                f"({start_votacoes} a {end_votacoes})..."
            )
            await sink.delete_period("votacoes", start_votacoes, end_votacoes, date_column="data")
        else:
            start_votacoes = sink.get_watermark("votacoes", "data") or "1991-01-01"
            end_votacoes = end_date or datetime.now().strftime("%Y-%m-%d")
            logger.info(
                f"Sincronizando Votações a partir de {start_votacoes} até {end_votacoes}..."
            )

        df_votacoes = await votacoes_ext.extract(start_date=start_votacoes, end_date=end_votacoes)

        if not df_votacoes.is_empty():
            await sink.save(df_votacoes, "votacoes", unique_keys="id")

            votacoes_ids = df_votacoes["id"].to_list()
            tamanho_lote_votos = 50
            total_lotes_votos = (len(votacoes_ids) + tamanho_lote_votos - 1) // tamanho_lote_votos
            checkpoint_votos = max(1, total_lotes_votos // 4)

            logger.info(
                f"     ∟ Extraindo votos nominais de {len(votacoes_ids)} votações encontradas..."
            )

            for i, batch_ids in enumerate(chunk_list(votacoes_ids, tamanho_lote_votos), 1):
                df_votos = await votacoes_ext.extract_votos(batch_ids)

                if not df_votos.is_empty():
                    await sink.save(df_votos, "votos", unique_keys=["idVotacao", "deputado_id"])

                if i == 1 or i == total_lotes_votos or i % checkpoint_votos == 0:
                    percentual = (i / total_lotes_votos) * 100
                    logger.info(
                        f"       Progresso: {percentual:.0f}% (Lote {i}/{total_lotes_votos})"
                    )

        logger.info("Pipeline finalizado com sucesso!")

    except Exception as e:
        logger.error(f"Falha crítica capturada no orquestrador: {e}")
        raise
    finally:
        await client.close()


async def main():
    start_time = time.perf_counter()
    logger.info("Iniciando iPolitico...")
    # Pega o primeiro dia do mês atual e o dia de hoje
    hoje = datetime.now().strftime("%Y-%m-%d")
    primeiro_dia_mes = datetime.now().strftime("%Y-%m-01")

    # Primeira execução: FULL LOAD restrito a este mês para criar a base e injetar os dados
    await run_pipeline(start_date=primeiro_dia_mes, end_date=hoje, strategy=LoadStrategy.FULL_LOAD)
    logger.info(f"Tempo total: {time.perf_counter() - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
