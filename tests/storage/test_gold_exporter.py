"""Testes para o exportador da camada Gold para SQL relacional (SQLite/DuckDB)."""

import sqlite3
from pathlib import Path

import duckdb
import polars as pl
from ipolitico.storage.gold_exporter import ExportFormat, GoldExporter

# ── Core export tests ────────────────────────────────────────────────────────


def test_export_sqlite_creates_tables_with_data(tmp_path: Path):
    """Exporta um domínio Gold para SQLite e verifica dados no banco."""
    gold_dir = tmp_path / "gold"
    domain_dir = gold_dir / "deputados"
    domain_dir.mkdir(parents=True)
    pl.DataFrame({"id": [1, 2], "nome": ["Alice", "Bob"], "uf": ["SP", "RJ"]}).write_parquet(
        domain_dir / "data.parquet"
    )

    output_path = str(tmp_path / "gold_export.db")
    exporter = GoldExporter(base_dir=str(tmp_path))

    tables = exporter.export_all(output_path, format=ExportFormat.SQLITE)

    assert tables == ["deputados"]

    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{output_path}' AS db (TYPE SQLITE)")
    rows = con.execute("SELECT id, nome, uf FROM db.deputados ORDER BY id").fetchall()
    con.close()

    assert rows == [(1, "Alice", "SP"), (2, "Bob", "RJ")]


def test_export_duckdb_creates_tables_with_data(tmp_path: Path):
    """Exporta um domínio Gold para DuckDB nativo e verifica dados."""
    gold_dir = tmp_path / "gold"
    domain_dir = gold_dir / "deputados"
    domain_dir.mkdir(parents=True)
    pl.DataFrame({"id": [1, 2], "nome": ["Alice", "Bob"]}).write_parquet(
        domain_dir / "data.parquet"
    )

    output_path = str(tmp_path / "gold_export.duckdb")
    exporter = GoldExporter(base_dir=str(tmp_path))

    tables = exporter.export_all(output_path, format=ExportFormat.DUCKDB)

    assert tables == ["deputados"]

    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{output_path}' AS db")
    rows = con.execute("SELECT id, nome FROM db.deputados ORDER BY id").fetchall()
    con.close()
    assert rows == [(1, "Alice"), (2, "Bob")]


def test_export_multiple_domains_sqlite(tmp_path: Path):
    """Exporta múltiplos domínios Gold para SQLite e verifica todos."""
    gold_dir = tmp_path / "gold"
    for domain, rows in [
        ("deputados", [{"id": 1, "nome": "Alice"}]),
        (
            "partidos",
            [{"id": 10, "sigla": "PT", "nome": "Partido dos Trabalhadores"}],
        ),
    ]:
        d = gold_dir / domain
        d.mkdir(parents=True)
        pl.DataFrame(rows).write_parquet(d / "data.parquet")

    output_path = str(tmp_path / "gold_export.db")
    exporter = GoldExporter(base_dir=str(tmp_path))

    tables = exporter.export_all(output_path, format=ExportFormat.SQLITE)

    assert sorted(tables) == ["deputados", "partidos"]

    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{output_path}' AS db (TYPE SQLITE)")
    dep_rows = con.execute("SELECT id, nome FROM db.deputados").fetchall()
    par_rows = con.execute("SELECT id, sigla FROM db.partidos").fetchall()
    con.close()

    assert dep_rows == [(1, "Alice")]
    assert par_rows == [(10, "PT")]


# ── Index tests ──────────────────────────────────────────────────────────────


def test_export_sqlite_creates_indices_on_pk_columns(tmp_path: Path):
    """Export SQLite cria índices nas colunas de chave primária."""
    gold_dir = tmp_path / "gold"
    domain_dir = gold_dir / "deputados"
    domain_dir.mkdir(parents=True)
    pl.DataFrame({"id": [1], "nome": ["Alice"], "uf": ["SP"]}).write_parquet(
        domain_dir / "data.parquet"
    )

    output_path = str(tmp_path / "gold_export.db")
    exporter = GoldExporter(base_dir=str(tmp_path))

    exporter.export_all(output_path, format=ExportFormat.SQLITE)

    con = sqlite3.connect(output_path)
    cursor = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'deputados'"
    )
    index_names = [row[0] for row in cursor.fetchall()]
    con.close()

    assert "idx_deputados_id" in index_names


# ── Edge-case tests ──────────────────────────────────────────────────────────


def test_export_no_gold_returns_empty(tmp_path: Path):
    """Sem dados Gold, retorna lista vazia sem criar arquivo."""
    exporter = GoldExporter(base_dir=str(tmp_path))
    output_path = str(tmp_path / "empty.duckdb")

    tables = exporter.export_all(output_path, format=ExportFormat.DUCKDB)

    assert tables == []
    assert not Path(output_path).exists()


def test_export_with_discover_skips_empty_dirs(tmp_path: Path):
    """Diretórios gold/ sem arquivo .parquet são ignorados."""
    (tmp_path / "gold" / "vazia").mkdir(parents=True)

    exporter = GoldExporter(base_dir=str(tmp_path))
    tables = exporter.discover_gold_tables()

    assert tables == []


def test_discover_gold_tables_lists_only_dirs_with_parquet(tmp_path: Path):
    """descobre apenas domínios com ao menos um Parquet Gold."""
    gold_dir = tmp_path / "gold"
    (gold_dir / "deputados").mkdir(parents=True)
    pl.DataFrame({"id": [1]}).write_parquet(gold_dir / "deputados" / "d.parquet")
    (gold_dir / "vazia").mkdir(parents=True)

    exporter = GoldExporter(base_dir=str(tmp_path))
    tables = exporter.discover_gold_tables()

    assert tables == ["deputados"]
