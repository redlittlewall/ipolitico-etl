import logging
import sqlite3

import polars as pl

from ipolitico.core.config import DB_PATH

logger = logging.getLogger(__name__)


def main():
    logger.info("Conectando ao banco de dados...")

    try:
        conn = sqlite3.connect(DB_PATH)

        # Query: Junta a tabela de deputados com a tabela biográfica de profissões
        query = """
            SELECT
                p.titulo as profissao,
                COUNT(DISTINCT d.id) as qtd_deputados
            FROM deputados_profissoes p
            JOIN deputados d ON d.id = p.id_deputado
            GROUP BY p.titulo
            ORDER BY qtd_deputados DESC
            LIMIT 15
        """

        df_profissoes = pl.read_database(query=query, connection=conn)

        if df_profissoes.is_empty():
            logger.warning("A tabela 'deputados_profissoes' está vazia. Execute o ETL primeiro!")
            return

        logger.info("\n=== TOP 15 PROFISSÕES MAIS COMUNS NA CÂMARA ===")
        print(df_profissoes)

        # Consulta rápida sobre mandatos externos
        query_mandatos = """
            SELECT cargo, COUNT(id_deputado) as total
            FROM deputados_mandatos_externos
            GROUP BY cargo
            ORDER BY total DESC
            LIMIT 5
        """
        df_mandatos = pl.read_database(query=query_mandatos, connection=conn)
        logger.info("\n=== CARGOS ANTERIORES MAIS COMUNS (Mandatos Externos) ===")
        print(df_mandatos)

    except Exception as e:
        logger.error(f"Erro na auditoria: {e}")
    finally:
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    main()
