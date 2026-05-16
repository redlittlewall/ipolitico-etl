"""Blindagem de schema para votações/votos via CamaraVotacoesTransformer (Bulk/API)."""

import polars as pl
from ipolitico.core.constants import DomainType
from ipolitico.transformers.camara.votacoes_transformer import CamaraVotacoesTransformer


def test_votacoes_transformer_datetime_from_bulk_strings():
    tr = CamaraVotacoesTransformer()
    df_sujo = pl.DataFrame(
        {
            "id": ["v1"],
            "uri": ["u"],
            "data": ["2026-05-10T14:00:00"],
            "dataHoraRegistro": ["2026-05-10T14:30:00"],
            "siglaOrgao": ["CCJC"],
            "uriOrgao": [""],
            "uriEvento": [""],
            "proposicaoObjeto": [""],
            "descricao": [""],
            "aprovacao": [1],
        }
    )

    df_limpo = tr.transform(df_sujo, sub_domain=DomainType.VOTACOES.value)

    assert df_limpo["data"].dtype == pl.Datetime
    assert df_limpo["dataHoraRegistro"].dtype == pl.Datetime


def test_votacoes_transformer_missing_mandatory_columns_returns_empty():
    tr = CamaraVotacoesTransformer()
    df_sujo = pl.DataFrame(
        {
            "id": ["VOT-123"],
            "uri": ["u"],
            "siglaOrgao": ["CCJC"],
            "uriOrgao": [""],
            "proposicaoObjeto": [""],
            "descricao": [""],
        }
    )

    df_limpo = tr.transform(df_sujo, sub_domain=DomainType.VOTACOES.value)

    assert df_limpo.is_empty()


def test_votos_transformer_bulk_id_deputado_rename():
    tr = CamaraVotacoesTransformer()
    df_sujo = pl.DataFrame(
        {
            "tipoVoto": ["Sim"],
            "dataRegistroVoto": ["2026-01-01"],
            "idDeputado": ["999"],
            "partido": ["X"],
            "uf": ["SP"],
            "votacao_id": ["v1"],
        }
    )

    df_limpo = tr.transform(df_sujo, sub_domain=DomainType.VOTOS.value)

    assert "idDeputado" not in df_limpo.columns
    assert "id_deputado" in df_limpo.columns
    assert df_limpo["id_deputado"][0] == 999
    assert df_limpo["id_deputado"].dtype == pl.Int64


def test_votos_transformer_missing_id_deputado_fails_contract():
    tr = CamaraVotacoesTransformer()
    df_sujo = pl.DataFrame(
        {
            "tipoVoto": ["Sim"],
            "dataRegistroVoto": ["2026-01-01"],
            "partido": ["X"],
            "uf": ["SP"],
            "votacao_id": ["v1"],
        }
    )

    df_limpo = tr.transform(df_sujo, sub_domain=DomainType.VOTOS.value)

    assert df_limpo.is_empty()
