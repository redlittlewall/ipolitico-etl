"""Exportador da camada Gold (Parquet deduplicado) para SQL relacional via DuckDB."""

import logging
import sqlite3
from enum import Enum
from pathlib import Path
from typing import List

import duckdb
from ipolitico.core.constants import DomainType
from ipolitico.core.domain_spec import spec_for

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Formatos suportados para exportação da camada Gold."""

    SQLITE = "sqlite"
    DUCKDB = "duckdb"


class GoldExporter:
    """
    Exporta a camada Gold (Parquet deduplicado) para formato SQL relacional
    (SQLite ou DuckDB nativo) via DuckDB.

    Lê cada tabela Gold do diretório ``gold/{dominio}/*.parquet`` e cria uma
    tabela SQL equivalente. Para SQLite, cria índices nas colunas de chave
    primária definidas em ``domain_spec``.
    """

    def __init__(self, base_dir: str = "data/datalake"):
        """
        Args:
            base_dir: Caminho raiz do DataLake (contém bronze/, silver/, gold/).
        """
        self.base_dir = Path(base_dir)
        self.gold_dir = self.base_dir / "gold"

    def discover_gold_tables(self) -> List[str]:
        """
        Lista os nomes dos domínios que possuem ao menos um Parquet em gold/.

        Returns:
            Lista de nomes de tabelas ordenados alfabeticamente, ou lista vazia
            se o diretório gold/ não existir ou estiver vazio.
        """
        if not self.gold_dir.exists():
            return []
        return sorted(
            d.name for d in self.gold_dir.iterdir() if d.is_dir() and list(d.glob("*.parquet"))
        )

    def export_all(self, output_path: str, format: ExportFormat = ExportFormat.SQLITE) -> List[str]:
        """
        Exporta todos os domínios Gold encontrados para um banco SQL.

        Args:
            output_path: Caminho do arquivo de saída (.db para SQLite, .duckdb
                para DuckDB nativo).
            format: Formato alvo — ``ExportFormat.SQLITE`` ou
                ``ExportFormat.DUCKDB``.

        Returns:
            Lista de nomes de tabelas exportadas (vazia se nenhum dado Gold
            estiver disponível).

        Raises:
            duckdb.Error: Se a exportação falhar por erro DuckDB.
        """
        tables = self.discover_gold_tables()
        if not tables:
            logger.warning("Nenhuma tabela Gold encontrada em %s", self.gold_dir)
            return []

        con = duckdb.connect(database=":memory:")

        try:
            if format == ExportFormat.SQLITE:
                con.execute(f"ATTACH '{output_path}' AS gold_db (TYPE SQLITE)")
            else:
                con.execute(f"ATTACH '{output_path}' AS gold_db")

            for table in tables:
                gold_path = self.gold_dir / table / "*.parquet"
                logger.info("Exportando %s → gold_db.%s", table, table)
                con.execute(
                    f"CREATE TABLE gold_db.\"{table}\" AS SELECT * FROM read_parquet('{gold_path}')"
                )

        except duckdb.Error as e:
            logger.error("Falha na exportação Gold: %s", e)
            raise
        finally:
            con.close()

        # Índices SQLite — DuckDB não suporta CREATE INDEX via SQLite scanner
        if format == ExportFormat.SQLITE:
            self._create_sqlite_indices(output_path, tables)

        return tables

    def _create_sqlite_indices(self, output_path: str, tables: List[str]) -> None:
        """
        Cria índices SQLite nas colunas de chave primária via sqlite3 nativo.

        Args:
            output_path: Caminho do arquivo SQLite.
            tables: Lista de nomes de tabelas que receberão índices.
        """
        try:
            con = sqlite3.connect(output_path)
            for table in tables:
                domain = next((d for d in DomainType if d.value == table), None)
                if not domain:
                    continue
                spec = spec_for(domain)
                if not spec or not spec.unique_keys:
                    continue
                for col in spec.unique_keys:
                    idx_name = f"idx_{table}_{col}"
                    try:
                        con.execute(
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ("{col}")'
                        )
                    except sqlite3.OperationalError:
                        logger.debug(
                            "Índice não criado para %s.%s (coluna talvez não exista)",
                            table,
                            col,
                        )
            con.commit()
            con.close()
        except sqlite3.Error as e:
            logger.warning("Falha ao criar índices SQLite: %s", e)
