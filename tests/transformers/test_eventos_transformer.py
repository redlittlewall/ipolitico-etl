import polars as pl

from ipolitico.transformers.camara.eventos_transformer import CamaraEventosTransformer


def test_eventos_transformer_datetime_and_orgaos_json():
    tr = CamaraEventosTransformer()
    df = pl.DataFrame(
        {
            "id": [1],
            "uri": ["u"],
            "descricao": ["Sessão"],
            "descricaoTipo": ["Ordinária"],
            "dataHoraInicio": ["2024-03-01T14:00:00"],
            "dataHoraFim": ["2024-03-01T18:00:00"],
            "situacao": ["Encerrada"],
            "orgaos": [None],
        }
    )
    out = tr.transform(df)
    assert out.height == 1
    assert out["dataHoraInicio"].dtype == pl.Datetime
