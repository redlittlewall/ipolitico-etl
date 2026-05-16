"""
Testes de Integração do SQLite Sink.
Usa um banco de dados real em arquivo temporário para garantir
que a sintaxe SQL (Upsert, Watermark, Deleção) funciona de verdade.
"""

import logging
import sqlite3
import tempfile

import polars as pl
import pytest
from ipolitico.sinks.sqlite_sink import SQLiteSink


@pytest.fixture
def temp_sqlite():
    """Gera um banco de dados SQLite real, mas que morre após o teste."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        yield SQLiteSink(db_path=tmp.name)


@pytest.mark.asyncio
async def test_sqlite_save_upsert(temp_sqlite):
    """Garante que a lógica de Upsert cria a tabela e atualiza registros sem duplicar."""
    # 1. Primeira Inserção (Cria a tabela)
    df_initial = pl.DataFrame(
        {"id": [1, 2], "nome": ["A", "B"], "updated_at": ["2026-01-01", "2026-01-01"]}
    )

    await temp_sqlite.save(df_initial, "teste_tabela", unique_keys="id")

    # 2. Inserção de Atualização (Mesmo ID, dados novos)
    df_update = pl.DataFrame(
        {
            "id": [1, 3],  # Atualiza o 1, insere o 3
            "nome": ["A_MODIFICADO", "C"],
            "updated_at": ["2026-01-02", "2026-01-02"],
        }
    )

    await temp_sqlite.save(df_update, "teste_tabela", unique_keys="id")

    # 3. Validação direto no SQL
    conn = sqlite3.connect(temp_sqlite.db_path)
    cursor = conn.cursor()

    # Verifica se não houve duplicação (devem existir os IDs 1, 2 e 3)
    cursor.execute("SELECT COUNT(*) FROM teste_tabela")
    assert cursor.fetchone()[0] == 3

    # Verifica se o Upsert modificou o dado antigo
    cursor.execute("SELECT nome FROM teste_tabela WHERE id = 1")
    assert cursor.fetchone()[0] == "A_MODIFICADO"
    conn.close()


def test_sqlite_watermark(temp_sqlite):
    """Garante que o orquestrador sabe exatamente de onde continuar a baixar."""
    df = pl.DataFrame({"id": [1, 2], "data_captura": ["2026-05-01", "2026-05-15"]})

    # Usa a função síncrona real da classe para não precisar do await no teste
    import asyncio

    asyncio.run(temp_sqlite.save(df, "tabela_watermark", unique_keys="id"))

    # Pede o maior valor da coluna temporal
    watermark = temp_sqlite.get_watermark("tabela_watermark", "data_captura")
    assert watermark == "2026-05-15"


@pytest.mark.asyncio
async def test_sqlite_save_empty_df(temp_sqlite):
    """Ignora DataFrames vazios silenciosamente."""
    df_vazio = pl.DataFrame()
    await temp_sqlite.save(df_vazio, "tabela_vazia", unique_keys="id")

    # Garante que a tabela não foi criada acidentalmente
    with sqlite3.connect(temp_sqlite.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tabela_vazia'")
        assert cursor.fetchone() is None


@pytest.mark.asyncio
async def test_sqlite_save_no_unique_keys(temp_sqlite):
    """
    Fluxo de APPEND bruto (sem UPSERT), usado quando não definimos chaves únicas.
    """
    df1 = pl.DataFrame({"nome": ["A"]})
    await temp_sqlite.save(df1, "logs_sem_chave")

    df2 = pl.DataFrame({"nome": ["B"]})
    await temp_sqlite.save(df2, "logs_sem_chave")  # Não passamos unique_keys

    with sqlite3.connect(temp_sqlite.db_path) as conn:
        res = conn.execute("SELECT nome FROM logs_sem_chave ORDER BY nome").fetchall()

    assert res == [("A",), ("B",)]


def test_sqlite_get_watermark_no_table(temp_sqlite):
    """
    Rodando incremental no Dia 1. Tabela não existe. Deve retornar None.
    """
    resultado = temp_sqlite.get_watermark("tabela_fantasma", "data")
    assert resultado is None


def test_sqlite_get_existing_ids_no_table(temp_sqlite):
    """
    Tenta buscar IDs de uma tabela que não existe.
    """
    resultado = temp_sqlite.get_existing_ids("tabela_fantasma", "id")
    assert resultado == []


@pytest.mark.asyncio
async def test_sqlite_delete_period_no_table(temp_sqlite):
    """
    Rodando FULL_LOAD no Dia 1. Não pode estourar OperationalError exposto.
    """
    # Apenas executa e garante que a exceção foi devidamente silenciada pelo except
    await temp_sqlite.delete_period("tabela_fantasma", "2026-01-01", "2026-12-31", "data")


@pytest.mark.asyncio
async def test_sqlite_get_existing_ids_empty_and_populated(temp_sqlite):
    """
    Testa o comportamento de leitura quando a tabela EXISTE,
    cobrindo tanto o cenário em que ela está vazia quanto populada.
    """
    # 1. Forçamos a criação da tabela vazia
    with sqlite3.connect(temp_sqlite.db_path) as conn:
        conn.execute("CREATE TABLE deputados_teste (id INTEGER)")

    # O Polars vai ler a tabela, ver que não tem linhas e o 'else []' será acionado
    ids_vazios = temp_sqlite.get_existing_ids("deputados_teste", "id")
    assert ids_vazios == []

    # 2. Inserimos um dado real
    with sqlite3.connect(temp_sqlite.db_path) as conn:
        conn.execute("INSERT INTO deputados_teste (id) VALUES (999)")

    # Agora a condição 'if not df.is_empty()' é acionada e retorna a lista real
    ids_cheios = temp_sqlite.get_existing_ids("deputados_teste", "id")
    assert ids_cheios == [999]


@pytest.mark.asyncio
async def test_sqlite_delete_period_success_logging(temp_sqlite, caplog):
    """
    Garante que a deleção de fato remove as linhas (rowcount > 0)
    e dispara o logger.warning de auditoria.
    O 'caplog' é uma fixture nativa do pytest para interceptar logs.
    """
    # 1. Preparamos o terreno com dados dentro e fora da janela temporal
    with sqlite3.connect(temp_sqlite.db_path) as conn:
        conn.execute("CREATE TABLE despesas_del (id INTEGER, dataDocumento TEXT)")
        # Dentro do alvo (vai ser deletado)
        conn.execute("INSERT INTO despesas_del VALUES (1, '2026-02-15')")
        # Fora do alvo (deve sobreviver)
        conn.execute("INSERT INTO despesas_del VALUES (2, '2026-04-15')")

    # 2. Executamos a deleção capturando os warnings
    with caplog.at_level(logging.WARNING):
        await temp_sqlite.delete_period(
            table="despesas_del",
            start_date="2026-02-01",
            end_date="2026-02-28",
            date_column="dataDocumento",
        )

    # 3. Validação do Banco: Somente o ID 2 deve ter sobrevivido
    with sqlite3.connect(temp_sqlite.db_path) as conn:
        res = conn.execute("SELECT id FROM despesas_del").fetchall()
        assert res == [(2,)]

    # 4. Validação da Auditoria: O log deve conter a mensagem de 1 registro eliminado
    assert "FULL_LOAD: 1 registros apagados entre 2026-02-01 e 2026-02-28" in caplog.text
