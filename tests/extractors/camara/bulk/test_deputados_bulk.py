"""Deputados Bulk: normalização ocorre no CamaraDeputadosTransformer."""

import polars as pl

from ipolitico.transformers.camara.deputados_transformer import CamaraDeputadosTransformer


def test_deputados_transformer_extracts_id_from_uri():
    tr = CamaraDeputadosTransformer()
    df_sujo = pl.DataFrame(
        {"uri": ["https://dadosabertos.camara.leg.br/api/v2/deputados/12345"]},
    )
    # contrato exige colunas; preenchemos o mínimo para o cast não falhar
    df_sujo = df_sujo.with_columns(
        [
            pl.lit("N").alias("nome"),
            pl.lit("P").alias("siglaPartido"),
            pl.lit("SP").alias("siglaUf"),
            pl.lit(57).alias("idLegislatura"),
            pl.lit("http://foto").alias("urlFoto"),
        ]
    )

    df_limpo = tr.transform(df_sujo)

    assert "id" in df_limpo.columns
    assert df_limpo["id"][0] == 12345
    assert df_limpo["id"].dtype == pl.Int64


def test_deputados_transformer_renames_capitalized_id():
    tr = CamaraDeputadosTransformer()
    df_sujo = pl.DataFrame(
        {
            "Id": [99],
            "idLegislatura": [57],
            "nome": ["X"],
            "siglaPartido": ["P"],
            "siglaUf": ["RJ"],
            "urlFoto": ["u"],
        }
    )

    df_limpo = tr.transform(df_sujo)

    assert "id" in df_limpo.columns
    assert "Id" not in df_limpo.columns
    assert df_limpo["id"][0] == 99
    assert df_limpo["idLegislatura"][0] == 57


def test_deputados_transformer_contract_violation_returns_empty():
    tr = CamaraDeputadosTransformer()
    df_sujo = pl.DataFrame({"nome_parlamentar": ["Tiririca"]})

    df_limpo = tr.transform(df_sujo)

    assert df_limpo.is_empty()
