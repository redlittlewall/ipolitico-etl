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


def test_list_orgao_ids_in_window_filters_by_gold_without_pandas(tmp_path: Path):
    """
    Filtra órgãos ativos na janela via DuckDB sem depender de pandas/numpy.

    O gold/orgaos_detalhe tem dataInicio/dataFim: apenas o órgão 1 está ativo
    na janela. Sem a correção (fetchall em vez de .df()), duckdb tenta importar
    numpy e falha, caindo no fallback que retorna todos os IDs.
    """
    repo = DataLakeRepository(tmp_path)
    gold_org = tmp_path / "gold" / "orgaos"
    gold_org.mkdir(parents=True)
    pl.DataFrame({"id": [1, 2, 3]}).write_parquet(gold_org / "orgaos.parquet")
    gold_det = tmp_path / "gold" / "orgaos_detalhe"
    gold_det.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": [1, 2, 3],
            "dataInicio": ["2024-01-01", "2023-01-01", "2020-01-01"],
            "dataFim": [None, "2023-12-31", "2020-12-31"],
        }
    ).write_parquet(gold_det / "orgaos_detalhe.parquet")

    ids = repo.list_orgao_ids_in_window("2024-03-01", "2024-03-31")

    assert ids == [1]


def test_list_deputy_ids_for_legislature_bounds_with_gold_without_pandas(tmp_path: Path):
    """
    Filtra deputados por idLegislatura via DuckDB sem pandas/numpy.

    Com gold/deputados presente, o filtro deve retornar apenas o id 102 (leg 56).
    Sem a correção, .df() falha por falta de numpy e cai no fallback [999].
    """
    repo = DataLakeRepository(tmp_path)
    gold = tmp_path / "gold" / "deputados"
    gold.mkdir(parents=True)
    pl.DataFrame(
        {"id": [101, 102, 103], "idLegislatura": [55, 56, 57]}
    ).write_parquet(gold / "deputados.parquet")

    ids = repo.list_deputy_ids_for_legislature_bounds(56, 56, silver_fallback_ids=[999])

    assert ids == [102]
