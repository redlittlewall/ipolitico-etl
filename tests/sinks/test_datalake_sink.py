import tempfile
from pathlib import Path

import polars as pl
import pytest
from ipolitico.core.constants import MedallionLayer
from ipolitico.sinks.datalake_sink import DataLakeSink


@pytest.fixture
def temp_datalake():
    """Gera um diretório temporário isolado para simular o DataLake,
    com thresholds de flush desabilitados (apenas flush explícito)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sink = DataLakeSink(base_dir=tmpdir, flush_size_mb=0, flush_interval_s=0)
        yield sink


def _read_all_batches(sink: DataLakeSink, layer: str, table: str) -> pl.DataFrame:
    layer_dir = Path(sink.base_dir) / layer / table
    files = sorted(layer_dir.glob("*.parquet"))
    if not files:
        return pl.DataFrame()
    return pl.concat([pl.read_parquet(f) for f in files])


@pytest.mark.asyncio
async def test_buffered_save_consolidates_into_one_file(temp_datalake):
    """N saves do mesmo domínio → 1 arquivo Parquet consolidado (em vez de N)."""
    layer = MedallionLayer.SILVER.value
    for i in range(3):
        df = pl.DataFrame({"id": [i], "valor": [float(i * 10)]})
        await temp_datalake.save(df, "consolidado", layer)

    # Ainda sem arquivo — dados estão no buffer
    layer_dir = Path(temp_datalake.base_dir) / layer / "consolidado"
    files_before = list(layer_dir.glob("*.parquet")) if layer_dir.exists() else []
    assert len(files_before) == 0

    # Flush explícito escreve 1 arquivo consolidado
    await temp_datalake.flush("consolidado", layer)
    files_after = sorted(layer_dir.glob("*.parquet"))
    assert len(files_after) == 1

    # Conteúdo consolidado
    result = pl.read_parquet(files_after[0])
    assert result.height == 3
    assert sorted(result["id"].to_list()) == [0, 1, 2]


@pytest.mark.asyncio
async def test_buffers_isolated_by_table(temp_datalake):
    """Buffers de domínios diferentes não se misturam."""
    layer = MedallionLayer.SILVER.value

    df_dep = pl.DataFrame({"id": [1, 2], "nome": ["Alice", "Bob"]})
    df_vot = pl.DataFrame({"id_votacao": [100], "tipo": ["Nominal"]})
    await temp_datalake.save(df_dep, "deputados", layer)
    await temp_datalake.save(df_vot, "votacoes", layer)

    # Flush apenas de deputados
    await temp_datalake.flush("deputados", layer)

    dep_files = list((Path(temp_datalake.base_dir) / layer / "deputados").glob("*.parquet"))
    vot_files = list((Path(temp_datalake.base_dir) / layer / "votacoes").glob("*.parquet"))
    assert len(dep_files) == 1
    assert len(vot_files) == 0

    dep_result = pl.read_parquet(dep_files[0])
    assert dep_result.height == 2
    assert "nome" in dep_result.columns

    # Flush de votacoes — agora deve escrever
    await temp_datalake.flush("votacoes", layer)
    vot_files = sorted((Path(temp_datalake.base_dir) / layer / "votacoes").glob("*.parquet"))
    assert len(vot_files) == 1
    vot_result = pl.read_parquet(vot_files[0])
    assert vot_result.height == 1


@pytest.mark.asyncio
async def test_datalake_save_and_append(temp_datalake):
    """Append-only: após flush, dados de múltiplos saves estão consolidados."""
    layer = MedallionLayer.SILVER.value
    df1 = pl.DataFrame({"id": [1], "valor": [10.0]})
    await temp_datalake.save(df1, "financas", layer)
    await temp_datalake.flush("financas", layer)

    df2 = pl.DataFrame({"id": [2], "valor": [20.0]})
    await temp_datalake.save(df2, "financas", layer)
    await temp_datalake.flush("financas", layer)

    df_final = _read_all_batches(temp_datalake, layer, "financas")
    assert df_final.height == 2
    assert set(df_final["id"].to_list()) == {1, 2}


@pytest.mark.asyncio
async def test_datalake_save_empty_df(temp_datalake):
    """DataFrame vazio não grava arquivo."""
    df_vazio = pl.DataFrame()
    await temp_datalake.save(df_vazio, "tabela_vazia", MedallionLayer.SILVER.value)

    layer_dir = Path(temp_datalake.base_dir) / MedallionLayer.SILVER.value / "tabela_vazia"
    assert not layer_dir.exists() or not list(layer_dir.glob("*.parquet"))


@pytest.mark.asyncio
async def test_datalake_save_with_composite_keys_appends_batches(temp_datalake):
    """unique_keys é ignorado na ingestão; após flush, ambos registros estão lá."""
    layer = MedallionLayer.SILVER.value
    df1 = pl.DataFrame({"id1": [1], "id2": ["A"], "valor": [10]})
    await temp_datalake.save(df1, "composta", layer, unique_keys=["id1", "id2"])

    df2 = pl.DataFrame({"id1": [1], "id2": ["A"], "valor": [99]})
    await temp_datalake.save(df2, "composta", layer, unique_keys=["id1", "id2"])

    await temp_datalake.flush("composta", layer)
    df_result = _read_all_batches(temp_datalake, layer, "composta")
    assert df_result.height == 2


@pytest.mark.asyncio
async def test_flush_without_data_is_noop(temp_datalake):
    """Flush sem buffer pendente não cria arquivo."""
    layer = MedallionLayer.SILVER.value
    await temp_datalake.flush("inexistente", layer)

    layer_dir = Path(temp_datalake.base_dir) / layer / "inexistente"
    assert not layer_dir.exists()


@pytest.mark.asyncio
async def test_flush_after_flush_starts_new_buffer(temp_datalake):
    """Após um flush, novos saves formam novo buffer que escreve novo arquivo."""
    layer = MedallionLayer.SILVER.value

    # Primeiro ciclo: 2 saves + flush = 1 arquivo
    await temp_datalake.save(pl.DataFrame({"id": [1]}), "ciclo", layer)
    await temp_datalake.save(pl.DataFrame({"id": [2]}), "ciclo", layer)
    await temp_datalake.flush("ciclo", layer)

    # Segundo ciclo: 2 saves + flush = outro arquivo
    await temp_datalake.save(pl.DataFrame({"id": [3]}), "ciclo", layer)
    await temp_datalake.save(pl.DataFrame({"id": [4]}), "ciclo", layer)
    await temp_datalake.flush("ciclo", layer)

    files = sorted((Path(temp_datalake.base_dir) / layer / "ciclo").glob("*.parquet"))
    assert len(files) == 2

    result = pl.concat([pl.read_parquet(f) for f in files])
    assert sorted(result["id"].to_list()) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_captured_at_preserved_in_buffer(temp_datalake):
    """Coluna captured_at é injetada por chunk e preservada no Parquet final."""
    layer = MedallionLayer.SILVER.value

    await temp_datalake.save(pl.DataFrame({"id": [1], "valor": [10.0]}), "auditoria", layer)
    await temp_datalake.save(pl.DataFrame({"id": [2], "valor": [20.0]}), "auditoria", layer)

    # Após flush, captured_at está no arquivo final
    await temp_datalake.flush("auditoria", layer)
    files = sorted((Path(temp_datalake.base_dir) / layer / "auditoria").glob("*.parquet"))
    result = pl.read_parquet(files[0])
    assert "captured_at" in result.columns
    assert result.height == 2


@pytest.mark.asyncio
async def test_flush_all_writes_all_buffers(temp_datalake):
    """flush_all() escreve todos os buffers pendentes."""
    layer = MedallionLayer.SILVER.value

    await temp_datalake.save(pl.DataFrame({"id": [1]}), "tabela_a", layer)
    await temp_datalake.save(pl.DataFrame({"id": [2]}), "tabela_b", layer)
    await temp_datalake.save(pl.DataFrame({"id": [3]}), "tabela_c", layer)

    await temp_datalake.flush_all()

    for tbl in ("tabela_a", "tabela_b", "tabela_c"):
        files = list((Path(temp_datalake.base_dir) / layer / tbl).glob("*.parquet"))
        assert len(files) == 1, f"{tbl} deveria ter 1 arquivo"

    # Buffer limpo
    assert len(temp_datalake._buffers) == 0
