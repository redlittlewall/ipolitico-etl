import asyncio
import time

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.core.logger import setup_logger
from ipolitico.extractors.camara.deputados import DeputadosExtractor
from ipolitico.extractors.camara.despesas import DespesasExtractor
from ipolitico.extractors.camara.proposicoes import ProposicoesExtractor
from ipolitico.extractors.camara.votacoes import VotacoesExtractor
from ipolitico.sinks.sqlite_sink import SQLiteSink

logger = setup_logger()


async def run_pipeline(data_ini: str = None, data_fim: str = None):
    """
    Orquestra o fluxo completo do ETL iPolitico.
    Segue a arquitetura modular e o SRP discutidos.
    """

    client = CamaraClient()
    sink = SQLiteSink(db_path=SQLITE_DB_PATH)

    deputados_ext = DeputadosExtractor(client, state_store=sink)
    despesas_ext = DespesasExtractor(client, state_store=sink)
    proposicoes_ext = ProposicoesExtractor(client, state_store=sink)
    votacoes_ext = VotacoesExtractor(client, state_store=sink)

    try:
        # Deputados
        logger.info("Extraindo lista de deputados federais...")
        df_deputados = await deputados_ext.extract(data_inicio=data_ini, data_fim=data_fim)
        if not df_deputados.is_empty():
            await sink.save(df_deputados, "deputados", unique_keys="id")

        deputados_ids = await deputados_ext.get_all_ids()

        # Detalhes Deputados
        logger.info("Extraindo detalhes cadastrais dos deputados ...")
        df_detalhes = await deputados_ext.extract_detalhes(deputados_ids)
        if not df_detalhes.is_empty():
            await sink.save(df_detalhes, "deputados_detalhes", unique_keys="id")

        # Despesas (por deputado)
        logger.info("Extraindo despesas da Cota Parlamentar...")
        df_despesas = await despesas_ext.extract(deputados_ids)
        if not df_despesas.is_empty():
            await sink.save(
                df_despesas, "despesas", unique_keys=["id_deputado", "numDocumento", "codDocumento"]
            )

        # Proposições
        logger.info("Extraindo Proposições (Projetos de Lei...")
        logger.info("Sincronizando Proposições...")
        df_proposicoes = await proposicoes_ext.extract()
        if not df_proposicoes.is_empty():
            await sink.save(df_proposicoes, "proposicoes", unique_keys="id")

        # Votações
        logger.info("Extraindo Votações...")
        df_votacoes = await votacoes_ext.extract()

        if not df_votacoes.is_empty():
            await sink.save(df_votacoes, "votacoes", unique_keys="id")
            votacoes_ids = df_votacoes["id"].to_list()
            logger.info(f"   ∟ Extraindo votos nominais de {len(votacoes_ids)} votações...")

            df_votos = await votacoes_ext.extract_votos(votacoes_ids)
            if not df_votos.is_empty():
                await sink.save(df_votos, "votos", unique_keys=["idVotacao", "deputado_id"])
        else:
            logger.info("ℹNenhuma votação nova detectada pelo marcador incremental.")

        logger.info("Pipeline finalizado com sucesso! Dados prontos para análise.")

    except Exception as e:
        logger.error(f"Falha crítica na execução do pipeline: {e}")
        raise

    finally:
        # Garante que o client HTTP seja fechado corretamente
        await client.close()


async def main():
    start_time = time.perf_counter()
    logger.info("Iniciando Pipeline de Auditoria Cidadã iPolitico...")

    await run_pipeline(data_ini="2024-03-01", data_fim="2024-03-31")

    end_time = time.perf_counter()
    duration = end_time - start_time
    logger.info(f"Pipeline finalizado em {duration:.2f} segundos ({duration / 60:.2f} minutos).")


if __name__ == "__main__":
    asyncio.run(main())
