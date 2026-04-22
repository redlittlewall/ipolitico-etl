import polars as pl
import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.proposicoes import ProposicoesExtractor


@pytest.mark.asyncio
async def test_extract_proposicoes_atuais_success():
    """
    Valida se o extrator de proposições organiza os dados corretamente.
    """
    client = CamaraClient()
    extractor = ProposicoesExtractor(client)

    fake_payload = [
        {"id": 1001, "siglaTipo": "PL", "ementa": "Marco Legal da IA", "ano": 2024},
        {"id": 1002, "siglaTipo": "PEC", "ementa": "Reforma do Estado", "ano": 2024},
    ]

    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/proposicoes").respond(
            status_code=200, json={"dados": fake_payload}
        )

        df = await extractor.extract_atuais()

        assert isinstance(df, pl.DataFrame)
        assert df.height == 2
        assert df["siglaTipo"][0] == "PL"
        assert df["ementa"][1] == "Reforma do Estado"
