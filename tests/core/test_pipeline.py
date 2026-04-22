import sqlite3

import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.deputados import DeputadosExtractor
from ipolitico.sinks.sqlite_sink import SQLiteSink


@pytest.mark.asyncio
async def test_pipeline_full_flow(tmp_path):
    """
    Testa o fluxo completo: API -> Extrator -> SQLiteSink.
    """
    db_file = tmp_path / "pipeline_test.db"

    # Instanciando as peças
    client = CamaraClient()
    extractor = DeputadosExtractor(client)
    sink = SQLiteSink(db_path=str(db_file))

    # Mock dos dados da Câmara
    fake_data = [{"id": 500, "nome": "Deputado Integracao", "siglaPartido": "ETL"}]

    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").respond(
            status_code=200, json={"dados": fake_data}
        )

        # Execução do fluxo que o nosso futuro Pipeline fará:
        df = await extractor.extract_atuaies()
        await sink.save(df, table_name="deputados")

    # Verificação final no banco de dados
    with sqlite3.connect(str(db_file)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM deputados")
        assert cursor.fetchone()[0] == "Deputado Integracao"
