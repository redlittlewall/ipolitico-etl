"""Despesas Bulk: aliases CEAP → contrato Silver no CamaraDespesasTransformer."""

import polars as pl
from ipolitico.transformers.camara.despesas_transformer import CamaraDespesasTransformer


def test_despesas_transformer_bulk_aliases_and_currency():
    tr = CamaraDespesasTransformer()

    df_sujo = pl.DataFrame(
        {
            "nuDeputadoId": ["100"],
            "datEmissao": ["2026-05-10T14:00:00"],
            "vlrLiquido": ["1.234,56"],
            "vlrDocumento": ["-150,00"],
            "codDocumento": ["1"],
            "tipoDespesa": ["TE"],
            "tipoDocumento": ["TD"],
            "numDocumento": ["N"],
            "parcela": ["1"],
            "ano": ["2026"],
            "mes": ["5"],
            "coluna_inutil": ["lixo"],
        }
    )

    df_limpo = tr.transform(df_sujo)

    assert "id_deputado" in df_limpo.columns
    assert "nuDeputadoId" not in df_limpo.columns
    assert "coluna_inutil" not in df_limpo.columns

    assert df_limpo["id_deputado"][0] == 100
    assert df_limpo["valorLiquido"][0] == 1234.56
    assert df_limpo["valorDocumento"][0] == -150.00
    assert df_limpo["dataDocumento"].dtype == pl.String


def test_despesas_transformer_txt_fornecedor_alias():
    tr = CamaraDespesasTransformer()
    df_sujo = pl.DataFrame(
        {
            "txtFornecedor": ["Posto Gasolina"],
            "codDocumento": ["9"],
            "valorLiquido": ["10,00"],
            "nuDeputadoId": ["1"],
            "datEmissao": ["2026-01-01"],
            "tipoDespesa": ["x"],
            "tipoDocumento": ["y"],
            "numDocumento": ["n"],
            "parcela": ["0"],
            "ano": ["2026"],
            "mes": ["1"],
        }
    )

    df_limpo = tr.transform(df_sujo)

    assert "nomeFornecedor" in df_limpo.columns
    assert df_limpo["nomeFornecedor"][0] == "Posto Gasolina"
