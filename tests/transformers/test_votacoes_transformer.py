"""Transformer de votações: Struct da API e contrato Silver."""

import polars as pl
from ipolitico.core.constants import DomainType
from ipolitico.transformers.camara.votacoes_transformer import CamaraVotacoesTransformer


def test_votacoes_transformer_nested_proposicao_objeto():
    tr = CamaraVotacoesTransformer()
    df = pl.DataFrame(
        {
            "id": ["v1"],
            "uri": ["u"],
            "data": ["2025-01-15T10:00:00"],
            "dataHoraRegistro": ["2025-01-15T10:05:00"],
            "siglaOrgao": ["PLEN"],
            "uriOrgao": ["uo"],
            "proposicaoObjeto": [{"uri": "http://proposicao/1", "id": 99}],
            "descricao": ["desc"],
            "aprovacao": [1],
        }
    )

    out = tr.transform(df, sub_domain=DomainType.VOTACOES.value)

    assert out.height == 1
    assert out["proposicaoObjeto"][0] == "http://proposicao/1"


def test_votacoes_transformer_aprovacao_string_coercion():
    tr = CamaraVotacoesTransformer()
    df = pl.DataFrame(
        {
            "id": ["v2"],
            "uri": ["u"],
            "data": ["2025-01-15T10:00:00"],
            "dataHoraRegistro": ["2025-01-15T10:05:00"],
            "siglaOrgao": ["CCJC"],
            "uriOrgao": ["uo"],
            "descricao": ["d"],
            "aprovacao": ["1"],
        }
    )

    out = tr.transform(df, sub_domain=DomainType.VOTACOES.value)

    assert out.height == 1
    assert out["aprovacao"][0] == 1
