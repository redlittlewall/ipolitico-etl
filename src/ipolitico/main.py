import asyncio
import logging

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import SQLITE_DB_PATH
from ipolitico.extractors.deputados import DeputadosExtractor
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
    extractor = DeputadosExtractor(client)
    sink = SQLiteSink(db_path=SQLITE_DB_PATH)

    try:
        # 2. Extração: Busca os dados da 57ª Legislatura
        logger.info("Extraindo lista de deputados federais da legislatura atual...")
        df_deputados = await extractor.extract_atuaies()

        # 3. Carga: Salva no Cofre SQLite
        logger.info(f"Salvando {df_deputados.height} registros no banco: {SQLITE_DB_PATH}")
        await sink.save(df_deputados, table_name="deputados")

        logger.info("Pipeline finalizado com sucesso! Dados prontos para análise.")

    except Exception as e:
        logger.error(f"Falha crítica na execução do pipeline: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_pipeline())
