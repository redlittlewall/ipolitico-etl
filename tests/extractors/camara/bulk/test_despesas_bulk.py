"""Despesas Bulk: aliases CEAP → contrato Silver no CamaraDespesasTransformer."""

import polars as pl

from ipolitico.transformers.bulk_window import BulkTemporalFilter
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


def test_despesas_transformer_ceap_ide_documento_and_br_date():
    """Colunas reais do dump Ano-{ano}.csv (ideDocumento, DD/MM/YYYY)."""
    tr = CamaraDespesasTransformer()
    df_ceap = pl.DataFrame(
        {
            "nuDeputadoId": ["204379"],
            "ideDocumento": ["12345"],
            "txtNumero": ["DOC-1"],
            "numParcela": ["1"],
            "numAno": ["2023"],
            "numMes": ["6"],
            "txtDescricao": ["MANUTENÇÃO DE ESCRITÓRIO"],
            "indTipoDocumento": ["Recibo"],
            "datEmissao": ["15/06/2023"],
            "vlrLiquido": ["100,50"],
            "vlrDocumento": ["100,50"],
            "txtFornecedor": ["Fornecedor X"],
            "txtCNPJCPF": ["00000000000191"],
        }
    )

    df_limpo = tr.transform(
        df_ceap,
        bulk_temporal_filter=BulkTemporalFilter(
            column="dataDocumento", start_iso="2023-01-01", end_iso="2023-12-31"
        ),
    )

    assert df_limpo.height == 1
    assert df_limpo["codDocumento"][0] == 12345
    assert df_limpo["dataDocumento"][0] == "2023-06-15"
    assert df_limpo["valorLiquido"][0] == 100.50


def test_despesas_transformer_ceap_both_deputado_columns():
    tr = CamaraDespesasTransformer()
    df_ceap = pl.DataFrame(
        {
            "nuDeputadoId": ["204379"],
            "ideCadastro": ["160510"],
            "ideDocumento": ["99"],
            "datEmissao": ["01/03/2024"],
            "vlrLiquido": ["10,00"],
            "vlrDocumento": ["10,00"],
            "txtDescricao": ["X"],
            "indTipoDocumento": ["R"],
            "txtNumero": ["1"],
            "numParcela": ["0"],
            "numAno": ["2024"],
            "numMes": ["3"],
        }
    )

    df_limpo = tr.transform(df_ceap)

    assert df_limpo.height == 1
    assert df_limpo["id_deputado"][0] == 204379
