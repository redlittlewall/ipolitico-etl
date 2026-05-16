import tempfile
from pathlib import Path

import polars as pl
import pytest
from ipolitico.core.constants import MedallionLayer
from ipolitico.sinks.datalake_sink import DataLakeSink


@pytest.fixture
def temp_datalake():
    """Gera um diretório temporário isolado para simular o DataLake."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sink = DataLakeSink(base_dir=tmpdir)
        yield sink


def _read_all_batches(sink: DataLakeSink, layer: str, table: str) -> pl.DataFrame:
    layer_dir = Path(sink.base_dir) / layer / table
    files = sorted(layer_dir.glob("*.parquet"))
    if not files:
        return pl.DataFrame()
    return pl.concat([pl.read_parquet(f) for f in files])


@pytest.mark.asyncio
async def test_datalake_save_and_append(temp_datalake):
    """Append-only: cada save gera um novo arquivo Parquet na camada."""
    layer = MedallionLayer.SILVER.value
    df1 = pl.DataFrame({"id": [1], "valor": [10.0]})
    await temp_datalake.save(df1, "financas", layer)

    df2 = pl.DataFrame({"id": [2], "valor": [20.0]})
    await temp_datalake.save(df2, "financas", layer)

    df_final = _read_all_batches(temp_datalake, layer, "financas")
    assert df_final.height == 2
    assert set(df_final["id"].to_list()) == {1, 2}


@pytest.mark.asyncio
async def test_datalake_delete_period_is_noop(temp_datalake):
    """delete_period está desabilitado no modo append-only."""
    from datetime import datetime

    df_bulk = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "data_fatura": [
                datetime(2026, 1, 5),
                datetime(2026, 2, 10),
                datetime(2026, 3, 15),
            ],
        }
    )

    file_path = Path(temp_datalake.base_dir) / "legacy.parquet"
    df_bulk.write_parquet(file_path)

    await temp_datalake.delete_period(
        table="compras", start_date="2026-02-01", end_date="2026-02-28", date_column="data_fatura"
    )

    df_result = pl.read_parquet(file_path)
    assert df_result.height == 3


@pytest.mark.asyncio
async def test_datalake_save_empty_df(temp_datalake):
    """DataFrame vazio não grava arquivo."""
    df_vazio = pl.DataFrame()
    await temp_datalake.save(df_vazio, "tabela_vazia", MedallionLayer.SILVER.value)

    layer_dir = Path(temp_datalake.base_dir) / MedallionLayer.SILVER.value / "tabela_vazia"
    assert not layer_dir.exists() or not list(layer_dir.glob("*.parquet"))


@pytest.mark.asyncio
async def test_datalake_save_with_composite_keys_appends_batches(temp_datalake):
    """unique_keys é ignorado na ingestão; dois saves geram dois lotes."""
    layer = MedallionLayer.SILVER.value
    df1 = pl.DataFrame({"id1": [1], "id2": ["A"], "valor": [10]})
    await temp_datalake.save(df1, "composta", layer, unique_keys=["id1", "id2"])

    df2 = pl.DataFrame({"id1": [1], "id2": ["A"], "valor": [99]})
    await temp_datalake.save(df2, "composta", layer, unique_keys=["id1", "id2"])

    df_result = _read_all_batches(temp_datalake, layer, "composta")
    assert df_result.height == 2


@pytest.mark.asyncio
async def test_datalake_delete_period_no_file(temp_datalake):
    await temp_datalake.delete_period("nao_existo", "2026-01-01", "2026-12-31", "data")
