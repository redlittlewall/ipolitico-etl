"""Testes unitários para o CamaraPessoalGabineteTransformer."""

from datetime import date

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.camara.pessoal_gabinete_transformer import (
    CamaraPessoalGabineteTransformer,
)


def test_transformer_happy_path():
    """Garante normalização de nomes, tipagem de datas e aderência estrita ao contrato Silver."""
    transformer = CamaraPessoalGabineteTransformer()

    raw_df = pl.DataFrame(
        {
            "deputado_id": [204521, 204521],
            "nome_assessor": ["  ana  clara  silva santos   ", "carlos   eduardo oliveira"],
            "cargo": ["secretário parlamentar sp-01", "SP-25"],
            "grupo_funcional": ["secretaria parlamentar", "GABINETE DO DEPUTADO"],
            "data_exercicio": ["01/02/2023", "2021-03-15"],
            "captured_at": ["2026-10-15T19:00:00Z", "2026-10-15T19:00:00Z"],
            "_source_url": [
                "https://www.camara.leg.br/deputados/204521/pessoal-gabinete",
                "https://www.camara.leg.br/deputados/204521/pessoal-gabinete",
            ],
        }
    )

    clean_df = transformer.transform(raw_df)

    contract = SILVER_SCHEMAS[DomainType.CAMARA_GABINETE_ASSESSORES.value]
    assert clean_df.columns == list(contract.keys())
    assert clean_df.schema == contract

    assert clean_df["nome_assessor"].to_list() == [
        "ANA CLARA SILVA SANTOS",
        "CARLOS EDUARDO OLIVEIRA",
    ]

    assert clean_df["data_exercicio"].to_list() == [
        date(2023, 2, 1),
        date(2021, 3, 15),
    ]

    assert clean_df["deputado_id"].to_list() == [204521, 204521]


def test_transformer_empty_df():
    """DataFrame vazio deve retornar vazio preservando o schema do contrato."""
    transformer = CamaraPessoalGabineteTransformer()
    empty_df = pl.DataFrame()
    out = transformer.transform(empty_df)

    assert isinstance(out, pl.DataFrame)
    assert out.is_empty()


def test_transformer_missing_optional_cols():
    """Colunas ausentes no input bruto devem ser criadas como nulas conforme o contrato."""
    transformer = CamaraPessoalGabineteTransformer()
    partial_df = pl.DataFrame(
        {
            "deputado_id": [12345],
            "nome_assessor": ["João Silva"],
        }
    )

    out = transformer.transform(partial_df)

    assert out.height == 1
    assert out["nome_assessor"][0] == "JOÃO SILVA"
    assert out["cargo"][0] is None
    assert out["data_exercicio"][0] is None


def test_transformer_invalid_date_becomes_null():
    """Datas malformadas não devem quebrar o pipeline, resultando em null."""
    transformer = CamaraPessoalGabineteTransformer()
    df = pl.DataFrame(
        {
            "deputado_id": [100],
            "nome_assessor": ["MARIA"],
            "cargo": ["SP-01"],
            "grupo_funcional": ["GAB"],
            "data_exercicio": ["data-invalida"],
            "captured_at": ["2026-10-15T19:00:00Z"],
            "_source_url": ["https://www.camara.leg.br"],
        }
    )

    out = transformer.transform(df)
    assert out["data_exercicio"][0] is None
