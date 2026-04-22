import sqlite3

import polars as pl
import pytest
from ipolitico.sinks.sqlite_sink import SQLiteSink


@pytest.mark.asyncio
async def test_sqlite_sink_save_success(tmp_path):
    """
    Testa se o SQLiteSink salva um DataFrame corretamente no disco.
    Usamos tmp_path do pytest para criar um banco temporário que se apaga sozinho.
    """
    db_file = tmp_path / "test_ipolitico.db"
    sink = SQLiteSink(db_path=str(db_file))

    # Criamos um dado fake seguindo o padrão de 'deputados'
    df = pl.DataFrame(
        {"id": [1, 2], "nome": ["Deputado A", "Deputado B"], "siglaPartido": ["P1", "P2"]}
    )

    # Executa a carga
    await sink.save(df, table_name="deputados_teste")

    # Validação: Abrimos o banco e checamos se o dado está lá
    with sqlite3.connect(str(db_file)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM deputados_teste")
        count = cursor.fetchone()[0]

        cursor.execute("SELECT nome FROM deputados_teste WHERE id = 1")
        nome = cursor.fetchone()[0]

    assert count == 2
    assert nome == "Deputado A"
