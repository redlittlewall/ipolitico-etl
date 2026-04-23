import asyncio
import logging

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.extractors.deputados import DeputadosExtractor
from ipolitico.extractors.despesas import DespesasExtractor
from ipolitico.extractors.proposicoes import ProposicoesExtractor
from ipolitico.extractors.votacoes import VotacoesExtractor
from ipolitico.sinks.sqlite_sink import SQLiteSink

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_pipeline():
    """
    Orquestra o fluxo completo do ETL iPolitico.
    Segue a arquitetura modular e o SRP discutidos.
    """
    logger.info("Iniciando Pipeline de Auditoria Cidadã iPolitico...")

    # Instanciação dos componentes (Desacoplados)
    client = CamaraClient()
    sink = SQLiteSink(db_path=SQLITE_DB_PATH)

    deputados_ext = DeputadosExtractor(client, db_path=SQLITE_DB_PATH)
    despesas_ext = DespesasExtractor(client, db_path=SQLITE_DB_PATH)
    proposicoes_ext = ProposicoesExtractor(client, db_path=SQLITE_DB_PATH)
    votacoes_ext = VotacoesExtractor(client, db_path=SQLITE_DB_PATH)

    try:
        # Deputados
        logger.info("Extraindo lista de deputados federais da legislatura atual...")
        df_deputados = await deputados_ext.extract()
        await sink.save(df_deputados, table_name="deputados")

        # Despesas (por deputado)
        logger.info("Extraindo lista de despesa por deputados federais...")
        ids = await deputados_ext.get_all_ids()
        df_despesas = await despesas_ext.extract(ids)
        if not df_despesas.is_empty():
            await sink.save(df_despesas, "despesas")

        # Proposições
        logger.info("Extraindo proposições legislativas recentes...")
        logger.info("📄 Sincronizando Proposições...")
        df_prop = await proposicoes_ext.extract()
        if not df_prop.is_empty():
            await sink.save(df_prop, table_name="proposicoes")

        # Votações
        logger.info("Extraindo votações legislativas recentes...")
        df_votacoes = await votacoes_ext.extract()

        if not df_votacoes.is_empty():
            logger.info(f"{df_votacoes.height} novas votações encontradas. Salvando...")
            await sink.save(df_votacoes, table_name="votacoes")

            # Para cada nova votação, buscamos os votos nominais
            for votacao_id in df_votacoes["id"].to_list():
                logger.info(f"   ∟ Extraindo votos nominais da votação {votacao_id}...")
                df_votos = await votacoes_ext.extract_votos(votacao_id)
                if not df_votos.is_empty():
                    await sink.save(df_votos, table_name="votos")

        else:
            logger.info("ℹNenhuma votação nova detectada pelo marcador incremental.")

        logger.info("Pipeline finalizado com sucesso! Dados prontos para análise.")

    except Exception as e:
        logger.error(f"Falha crítica na execução do pipeline: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_pipeline())
