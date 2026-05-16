"""Proposições Bulk: datas e contrato no CamaraProposicoesTransformer."""

import polars as pl
from ipolitico.transformers.camara.proposicoes_transformer import CamaraProposicoesTransformer


def test_proposicoes_transformer_datetime():
    tr = CamaraProposicoesTransformer()
    df_sujo = pl.DataFrame(
        {
            "id": [1],
            "uri": ["u"],
            "siglaTipo": ["PL"],
            "numero": [1],
            "ano": [2026],
            "ementa": ["e"],
            "dataApresentacao": ["2026-05-10T14:00:00"],
        }
    )

    df_limpo = tr.transform(df_sujo)

    assert df_limpo["dataApresentacao"].dtype == pl.Datetime


def test_proposicoes_transformer_missing_mandatory_returns_empty():
    tr = CamaraProposicoesTransformer()
    df_sujo = pl.DataFrame({"outra_coluna": ["PL 123/2026"]})

    df_limpo = tr.transform(df_sujo)

    assert df_limpo.is_empty()
