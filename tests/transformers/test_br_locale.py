"""
Testes do helper de locale BR para conversão de moeda (1.234,56 → Float64).
"""

import polars as pl

from ipolitico.transformers.br_locale import convert_br_currency_columns


def test_convert_single_br_column():
    """Converte uma coluna com formato BR '1.234,56' para Float64 1234.56."""
    df = pl.DataFrame({"vlrLiquido": ["1.234,56", "0,00", "1.000.000,99"]})
    result = convert_br_currency_columns(df, ["vlrLiquido"])
    assert result["vlrLiquido"].dtype == pl.Float64
    assert result["vlrLiquido"].to_list() == [1234.56, 0.0, 1000000.99]


def test_convert_multiple_br_columns():
    """Converte múltiplas colunas de moeda BR simultaneamente."""
    df = pl.DataFrame(
        {
            "vlrLiquido": ["1.234,56"],
            "vlrDocumento": ["9.999,99"],
            "nome": ["teste"],
        }
    )
    result = convert_br_currency_columns(df, ["vlrLiquido", "vlrDocumento"])
    assert result["vlrLiquido"].dtype == pl.Float64
    assert result["vlrDocumento"].dtype == pl.Float64
    assert result["vlrLiquido"][0] == 1234.56
    assert result["vlrDocumento"][0] == 9999.99
    assert result["nome"][0] == "teste"


def test_column_not_present_is_noop():
    """Coluna listada mas ausente no DataFrame não causa erro."""
    df = pl.DataFrame({"nome": ["teste"]})
    result = convert_br_currency_columns(df, ["vlrLiquido"])
    assert result.columns == ["nome"]
    assert result["nome"][0] == "teste"


def test_empty_columns_list_is_noop():
    """Lista vazia de colunas retorna o DataFrame inalterado."""
    df = pl.DataFrame({"vlrLiquido": ["1.234,56"]})
    result = convert_br_currency_columns(df, [])
    assert result["vlrLiquido"].dtype == pl.String


def test_empty_dataframe_returns_empty():
    """DataFrame vazio retorna DataFrame vazio."""
    df = pl.DataFrame({"vlrLiquido": pl.Series([], dtype=pl.String)})
    result = convert_br_currency_columns(df, ["vlrLiquido"])
    assert result.is_empty()
    assert result["vlrLiquido"].dtype == pl.Float64


def test_already_numeric_column_is_recast():
    """Coluna já Float64 é sobrescrita (comportamento consistente)."""
    df = pl.DataFrame({"vlrLiquido": [1234.56, 0.0]})
    result = convert_br_currency_columns(df, ["vlrLiquido"])
    assert result["vlrLiquido"].dtype == pl.Float64
