"""Testes para StateStore interface + DataLakeRepository como implementação."""

from pathlib import Path

import polars as pl

from ipolitico.storage.datalake_repository import DataLakeRepository
from ipolitico.storage.state_store import StateStore


class TestDataLakeRepositoryStateStore:
    """DataLakeRepository implementa StateStore corretamente."""

    def test_implements_state_store(self, tmp_path: Path):
        """DataLakeRepository é uma instância de StateStore."""
        repo = DataLakeRepository(tmp_path)
        assert isinstance(repo, StateStore)

    def test_get_existing_ids_returns_ids_from_silver(self, tmp_path: Path):
        """get_existing_ids retorna IDs distintos de arquivos Parquet na Silver."""
        repo = DataLakeRepository(tmp_path)
        silver_dir = tmp_path / "silver" / "test_table"
        silver_dir.mkdir(parents=True)
        pl.DataFrame({"id": [10, 20, 30], "nome": ["a", "b", "c"]}).write_parquet(
            silver_dir / "lote_1.parquet"
        )

        ids = repo.get_existing_ids("test_table", "silver", "id")

        assert sorted(ids) == [10, 20, 30]

    def test_get_existing_ids_returns_empty_when_no_data(self, tmp_path: Path):
        """get_existing_ids retorna lista vazia se a tabela não existe."""
        repo = DataLakeRepository(tmp_path)
        ids = repo.get_existing_ids("tabela_inexistente", "silver", "id")
        assert ids == []

    def test_get_existing_ids_dedup(self, tmp_path: Path):
        """get_existing_ids deduplica IDs repetidos entre múltiplos arquivos."""
        repo = DataLakeRepository(tmp_path)
        silver_dir = tmp_path / "silver" / "test_table"
        silver_dir.mkdir(parents=True)
        pl.DataFrame({"id": [10, 20]}).write_parquet(silver_dir / "lote_1.parquet")
        pl.DataFrame({"id": [20, 30]}).write_parquet(silver_dir / "lote_2.parquet")

        ids = repo.get_existing_ids("test_table", "silver", "id")

        assert sorted(ids) == [10, 20, 30]

    def test_get_existing_ids_gold_fallback(self, tmp_path: Path):
        """Se silver não existe mas gold sim, busca em gold."""
        repo = DataLakeRepository(tmp_path)
        gold_dir = tmp_path / "gold" / "test_table"
        gold_dir.mkdir(parents=True)
        pl.DataFrame({"id": [1, 2]}).write_parquet(gold_dir / "test_table.parquet")

        ids = repo.get_existing_ids("test_table", "silver", "id")

        assert sorted(ids) == [1, 2]

    def test_get_watermark_returns_max_value(self, tmp_path: Path):
        """get_watermark retorna o maior valor da coluna watermark."""
        repo = DataLakeRepository(tmp_path)
        silver_dir = tmp_path / "silver" / "test_table"
        silver_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "id": [1, 2, 3],
                "data": ["2024-01-01", "2024-06-15", "2024-12-31"],
            }
        ).write_parquet(silver_dir / "lote_1.parquet")

        wm = repo.get_watermark("test_table", "data")

        assert wm == "2024-12-31"

    def test_get_watermark_with_datetime_column(self, tmp_path: Path):
        """get_watermark lida com colunas do tipo datetime."""
        repo = DataLakeRepository(tmp_path)
        silver_dir = tmp_path / "silver" / "test_table"
        silver_dir.mkdir(parents=True)
        pl.DataFrame(
            {
                "id": [1, 2],
                "data": [
                    "2024-01-01T10:00:00",
                    "2024-06-15T14:30:00",
                ],
            }
        ).write_parquet(silver_dir / "lote_1.parquet")

        wm = repo.get_watermark("test_table", "data")

        # Deve retornar a string ISO com T
        assert "2024-06-15" in wm
        assert "T" in wm

    def test_get_watermark_returns_none_when_no_data(self, tmp_path: Path):
        """get_watermark retorna None se a tabela não existe."""
        repo = DataLakeRepository(tmp_path)
        wm = repo.get_watermark("tabela_inexistente", "data")
        assert wm is None
