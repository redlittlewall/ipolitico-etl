import asyncio
import logging

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.extractors.deputados import DeputadosExtractor
from ipolitico.extractors.proposicoes import ProposicoesExtractor
from ipolitico.sinks.sqlite_sink import SQLiteSink

# Configuração de logs para acompanhamento da extração
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_pipeline():
    """
    Orquestra o fluxo completo do ETL iPolitico.
    Segue a arquitetura modular e o SRP discutidos.
    """
    logger.info("Iniciando Pipeline de Auditoria Cidadã iPolitico...")

    # 1. Instanciação dos componentes (Desacoplados)
    client = CamaraClient()
    sink = SQLiteSink(db_path=SQLITE_DB_PATH)

    deputados_ext = DeputadosExtractor(client)
    proposicoes_ext = ProposicoesExtractor(client)
    try:
        # 2. Extração: Busca os dados da 57ª Legislatura
        logger.info("Extraindo lista de deputados federais da legislatura atual...")
        df_deputados = await deputados_ext.extract_atuaies()
        await sink.save(df_deputados, table_name="deputados")

        # 3. Fluxo de Proposições
        logger.info("📄 Extraindo proposições legislativas recentes...")
        df_proposicoes = await proposicoes_ext.extract_atuais()
        await sink.save(df_proposicoes, table_name="proposicoes")

        logger.info("Pipeline finalizado com sucesso! Dados prontos para análise.")

    except Exception as e:
        logger.error(f"Falha crítica na execução do pipeline: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_pipeline())
