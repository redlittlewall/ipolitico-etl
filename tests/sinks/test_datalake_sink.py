import tempfile

import polars as pl
import pytest
from ipolitico.sinks.datalake_sink import DataLakeSink


@pytest.fixture
def temp_datalake():
    """Gera um diretório temporário isolado para simular o DataLake."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sink = DataLakeSink(base_dir=tmpdir)
        yield sink


@pytest.mark.asyncio
async def test_datalake_save_and_append(temp_datalake):
    """Testa se o Parquet é criado e se novos dados são adicionados."""
    df1 = pl.DataFrame({"id": [1], "valor": [10.0]})
    await temp_datalake.save(df1, "financas")

    df2 = pl.DataFrame({"id": [2], "valor": [20.0]})
    await temp_datalake.save(df2, "financas")

    file_path = temp_datalake.base_dir / "financas.parquet"
    assert file_path.exists()

    df_final = pl.read_parquet(file_path)
    assert df_final.height == 2
    assert df_final["id"].to_list() == [1, 2]


@pytest.mark.asyncio
async def test_datalake_delete_period_schema_drift(temp_datalake):
    """Garante que a deleção funciona mesmo com tipos diferentes (Schema Drift)."""
    from datetime import datetime

    df_bulk = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "data_fatura": [
                datetime(2026, 1, 5),
                datetime(2026, 2, 10),  # Alvo da deleção
                datetime(2026, 3, 15),
            ],
        }
    )

    file_path = temp_datalake.base_dir / "compras.parquet"
    df_bulk.write_parquet(file_path)

    # O método corrigido com .cast(pl.String) deve lidar com isso agora
    await temp_datalake.delete_period(
        table="compras", start_date="2026-02-01", end_date="2026-02-28", date_column="data_fatura"
    )

    df_result = pl.read_parquet(file_path)
    assert df_result.height == 2
    assert 2 not in df_result["id"].to_list()


@pytest.mark.asyncio
async def test_datalake_save_empty_df(temp_datalake):
    """
    O fluxo incremental não achou nada novo. O Sink deve ignorar silenciosamente
    em vez de criar um arquivo parquet quebrado.
    """
    df_vazio = pl.DataFrame()
    await temp_datalake.save(df_vazio, "tabela_vazia")

    file_path = temp_datalake.base_dir / "tabela_vazia.parquet"
    assert not file_path.exists()


@pytest.mark.asyncio
async def test_datalake_save_with_composite_keys(temp_datalake):
    """
    Testa o UPSERT usando uma lista de chaves compostas em vez de uma string simples.
    (Essencial para Votos, que usa idVotacao + deputado_id).
    """
    # Carga Inicial
    df1 = pl.DataFrame({"id1": [1], "id2": ["A"], "valor": [10]})
    await temp_datalake.save(df1, "composta", unique_keys=["id1", "id2"])

    # Nova Carga (Atualiza o valor para a mesma chave composta)
    df2 = pl.DataFrame({"id1": [1], "id2": ["A"], "valor": [99]})
    await temp_datalake.save(df2, "composta", unique_keys=["id1", "id2"])

    file_path = temp_datalake.base_dir / "composta.parquet"
    df_result = pl.read_parquet(file_path)

    # Não pode ter duplicado, deve ter atualizado o valor para 99
    assert df_result.height == 1
    assert df_result["valor"][0] == 99


@pytest.mark.asyncio
async def test_datalake_delete_period_no_file(temp_datalake):
    """
    Usuário acionou FULL_LOAD no Dia 1, mas o arquivo parquet ainda não existe.
    """
    # O método deve retornar silenciosamente sem estourar FileNotFoundError
    await temp_datalake.delete_period("nao_existo", "2026-01-01", "2026-12-31", "data")
