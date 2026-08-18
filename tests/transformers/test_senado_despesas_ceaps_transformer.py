"""Testes do SenadoDespesasCeapsTransformer — função pura (issue 09).

Prior art: ``tests/transformers/test_senado_remuneracoes_transformer.py`` —
DataFrame conhecido → DataFrame no contrato Silver.
"""

import polars as pl

from ipolitico.transformers.senado.despesas_ceaps_transformer import (
    SenadoDespesasCeapsTransformer,
)

# Contrato Silver: ``_source_url`` + 13 campos (``valorReembolsado`` Float64).
CONTRACT_COLUMNS = [
    "_source_url",
    "id",
    "tipoDocumento",
    "ano",
    "mes",
    "codSenador",
    "nomeSenador",
    "tipoDespesa",
    "cpfCnpj",
    "fornecedor",
    "documento",
    "data",
    "detalhamento",
    "valorReembolsado",
]


def _raw_df(**overrides) -> pl.DataFrame:
    """DataFrame bruto de uma despesa CEAP como a API devolve."""
    row = {
        "_source_url": "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/2025",
        "id": 2270752,
        "tipoDocumento": "Nota Fiscal Eletrônica",
        "ano": 2025,
        "mes": 9,
        "codSenador": 475,
        "nomeSenador": "CONFÚCIO MOURA",
        "tipoDespesa": "Locomoção, hospedagem, alimentação, combustíveis e lubrificantes",
        "cpfCnpj": "16.805.309/0001-99",
        "fornecedor": "AUTO POSTO DO LAGO LTDA",
        "documento": "000042973",
        "data": "2025-09-26",
        "detalhamento": "Despesa com combustíveis",
        "valorReembolsado": 211.55,
    }
    row.update(overrides)
    return pl.DataFrame([row])


class TestSenadoDespesasCeapsTransformer:
    """Transformer puro — valor numérico passa direto; string BR converte."""

    def test_valor_numerico_passa_direto_float64(self):
        """
        A API real devolve ``valorReembolsado`` como número (float/int). O
        transformer não regride para string — vira ``Float64``.
        """
        df = SenadoDespesasCeapsTransformer().transform(_raw_df())

        assert df.schema["valorReembolsado"] == pl.Float64
        assert df["valorReembolsado"][0] == 211.55

    def test_valor_string_br_converte_via_br_locale(self):
        """
        Formato documentado no survey (``"1.234,56"``): converte via
        ``br_locale`` para ``Float64`` (1234.56). Número e string convivem.
        """
        df = SenadoDespesasCeapsTransformer().transform(_raw_df(valorReembolsado="1.234,56"))

        assert df.schema["valorReembolsado"] == pl.Float64
        assert df["valorReembolsado"][0] == 1234.56

    def test_contrato_estrito_14_colunas(self):
        """Schema Silver: 14 colunas (``_source_url`` + 13), ``valorReembolsado`` Float64."""
        df = SenadoDespesasCeapsTransformer().transform(_raw_df())

        assert df.columns == CONTRACT_COLUMNS
        assert df.schema["valorReembolsado"] == pl.Float64
        assert df.schema["id"] == pl.Int64
        assert df.schema["codSenador"] == pl.Int64
        assert df.schema["ano"] == pl.Int64
        assert df.schema["mes"] == pl.Int64
        assert df.schema["data"] == pl.String  # ISO "2025-09-26" preservado

    def test_nulos_de_campos_documentais_preservados(self):
        """
        Anos antigos (ex: 2008) têm nulo em ``data``/``documento``/``cpfCnpj`` —
        o cast estrito preserva o nulo (String nullable), não explode.
        """
        raw = _raw_df(data=None, documento=None, cpfCnpj=None)
        df = SenadoDespesasCeapsTransformer().transform(raw)

        assert df["data"][0] is None
        assert df["documento"][0] is None
        assert df["cpfCnpj"][0] is None
        assert df.height == 1

    def test_dataframe_vazio_retorna_vazio(self):
        """DataFrame vazio → retorna vazio (sem colunas adicionadas)."""
        out = SenadoDespesasCeapsTransformer().transform(pl.DataFrame())
        assert out.is_empty()
        assert out.columns == []

    def test_colunas_extras_sao_descartadas_e_ausentes_viram_nulo(self):
        """
        Colunas extras do payload (ex: ``origemDespesa``) são descartadas; campos
        obrigatórios do contrato ausentes viram nulo na ordem do contrato.
        """
        raw = pl.DataFrame(
            [
                {
                    "_source_url": "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/2025",
                    "id": 1,
                    "mes": 1,
                    "ano": 2025,
                    "codSenador": 475,
                    "nomeSenador": "CONFÚCIO MOURA",
                    "valorReembolsado": 10.0,
                    "origemDespesa": "extra",  # não existe no contrato
                }
            ]
        )
        df = SenadoDespesasCeapsTransformer().transform(raw)

        assert "origemDespesa" not in df.columns
        assert df.columns == CONTRACT_COLUMNS
        assert df["tipoDocumento"][0] is None  # ausente no bruto → nulo
        assert df["tipoDespesa"][0] is None
