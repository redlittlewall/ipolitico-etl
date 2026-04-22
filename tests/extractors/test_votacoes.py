import polars as pl
import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.votacoes import VotacoesExtractor


@pytest.mark.asyncio
async def test_extract_votos_success():
    client = CamaraClient()
    extractor = VotacoesExtractor(client)
    votacao_id = "2200-1"

    fake_votos = [
        {"voto": "Sim", "deputado_nome": "Deputado X", "id_deputado": 1},
        {"voto": "Não", "deputado_nome": "Deputado Y", "id_deputado": 2},
    ]

    with respx.mock:
        url = f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{votacao_id}/votos"
        respx.get(url).respond(status_code=200, json={"dados": fake_votos})

        df = await extractor.extract_votos_por_votacao(votacao_id)

        assert isinstance(df, pl.DataFrame)
        assert "id_votacao" in df.columns
        assert df["id_votacao"][0] == votacao_id
        assert df.height == 2
