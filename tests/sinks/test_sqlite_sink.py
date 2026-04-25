import os
import sqlite3

import polars as pl
import pytest
from ipolitico.sinks.sqlite_sink import SQLiteSink


@pytest.fixture
def temp_sink(tmp_path):
    """Cria um banco SQLite temporário isolado para o teste e o destrói ao final."""
    db_path = tmp_path / "test_ipolitico.db"
    sink = SQLiteSink(db_path=str(db_path))
    yield sink
    if db_path.exists():
        os.remove(db_path)


@pytest.mark.asyncio
async def test_sink_upsert_logic(temp_sink):
    """
    Testa o coração do projeto: O UPSERT baseado em Staging Tables.
    Garante que dados novos são inseridos e dados velhos são atualizados.
    """
    # 1. Primeira Carga (INSERT)
    df1 = pl.DataFrame({"id": [1], "nome": ["Deputado Original"]})
    await temp_sink.save(df1, "deputados", unique_keys="id")

    # 2. Segunda Carga (UPDATE do 1, INSERT do 2)
    df2 = pl.DataFrame({"id": [1, 2], "nome": ["Nome Corrigido", "Novo Deputado"]})
    await temp_sink.save(df2, "deputados", unique_keys="id")

    # 3. Auditoria direta no banco
    with sqlite3.connect(temp_sink.db_path) as conn:
        result = conn.execute("SELECT id, nome FROM deputados ORDER BY id").fetchall()

    assert result == [(1, "Nome Corrigido"), (2, "Novo Deputado")]


@pytest.mark.asyncio
async def test_sink_delete_period(temp_sink):
    """
    Garante que o FULL LOAD é destrutivo como deve ser (Idempotência).
    Registros dentro do período devem sumir, os de fora devem ficar.
    """
    df = pl.DataFrame(
        {"id": [10, 20, 30], "dataDocumento": ["2025-01-15", "2025-02-15", "2025-03-15"]}
    )
    await temp_sink.save(df, "despesas", unique_keys="id")

    # Simulando um FULL LOAD apenas do mês de Fevereiro
    await temp_sink.delete_period("despesas", "2025-02-01", "2025-02-28", "dataDocumento")

    with sqlite3.connect(temp_sink.db_path) as conn:
        result = conn.execute("SELECT id FROM despesas ORDER BY id").fetchall()

    # O registro 20 (Fevereiro) deve ter sumido
    assert result == [(10,), (30,)]


def test_sink_get_existing_ids(temp_sink):
    """Garante que a recuperação de IDs para o processamento de lotes funciona."""
    # Testa tabela que não existe ainda
    ids_vazios = temp_sink.get_existing_ids("tabela_fantasma")
    assert ids_vazios == []
