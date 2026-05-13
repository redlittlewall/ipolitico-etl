# examples/ranking_discursos.py
import sqlite3

from duckdb import pl
from ipolitico.core.config import DB_PATH
from ipolitico.core.logger import setup_logger

logger = setup_logger()


def main():
    logger.info("Auditando a tabela de atividades temporais (Discursos)...")

    try:
        conn = sqlite3.connect(DB_PATH)

        # Query 1: Quem falou mais vezes no período capturado?
        query_volume = """
            SELECT
                d.nome,
                d.siglaPartido,
                COUNT(disc.dataHoraInicio) as total_discursos
            FROM deputados_discursos disc
            JOIN deputados d ON d.id = disc.id_deputado
            GROUP BY d.id
            ORDER BY total_discursos DESC
            LIMIT 10
        """

        df_volume = pl.read_database(query=query_volume, connection=conn)

        if df_volume.is_empty():
            logger.warning("A tabela 'deputados_discursos' está vazia. O ETL temporal rodou?")
            return

        logger.info("\n=== TOP 10 DEPUTADOS MAIS DISCURSIVOS ===")
        print(df_volume)

        # Query 2: Amostragem de segurança (Validar se a transcrição não corrompeu)
        query_texto = """
            SELECT d.nome, disc.dataHoraInicio, SUBSTR(disc.transcricao, 1, 80) || '...' as excerto
            FROM deputados_discursos disc
            JOIN deputados d ON d.id = disc.id_deputado
            WHERE disc.transcricao IS NOT NULL
            ORDER BY disc.dataHoraInicio DESC
            LIMIT 5
        """
        df_textos = pl.read_database(query=query_texto, connection=conn)

        logger.info("\n=== VERIFICAÇÃO DE INTEGRIDADE DAS TRANSCRIÇÕES (Excertos) ===")
        # Configuração do Polars para não truncar a string no print
        with pl.Config(fmt_str_lengths=100):
            print(df_textos)

    except Exception as e:
        logger.error(f"Erro na auditoria temporal: {e}")
    finally:
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    main()
