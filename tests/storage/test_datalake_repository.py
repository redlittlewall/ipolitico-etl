from pathlib import Path

import polars as pl
import pytest
from ipolitico.storage.datalake_repository import DataLakeRepository


@pytest.fixture
def lake_with_votacoes(tmp_path: Path) -> DataLakeRepository:
    repo = DataLakeRepository(tmp_path)
    silver = tmp_path / "silver" / "votacoes"
    silver.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["v1", "v2", "v3"],
            "data": [
                "2024-03-01T12:00:00",
                "2024-04-01T12:00:00",
                "2023-01-01T12:00:00",
            ],
        }
    ).write_parquet(silver / "lote_1.parquet")
    return repo


def test_list_votacao_ids_in_window_filters_by_data(lake_with_votacoes: DataLakeRepository):
    ids = lake_with_votacoes.list_votacao_ids_silver_or_gold("2024-03-01", "2024-03-31")
    assert ids == ["v1"]


def test_list_deputy_expense_year_pairs(tmp_path: Path):
    repo = DataLakeRepository(tmp_path)
    silver = tmp_path / "silver" / "despesas"
    silver.mkdir(parents=True)
    pl.DataFrame({"id_deputado": [10, 10, 20], "ano": [2023, 2024, 2023]}).write_parquet(
        silver / "a.parquet"
    )
    pairs = repo.list_deputy_expense_year_pairs()
    assert pairs == {(10, 2023), (10, 2024), (20, 2023)}
