"""Testes do SenadoRemuneracoesTransformer — contrato Silver (issue 08).

Prior art: ``tests/transformers/test_senado_servidores_transformer.py`` —
transformer puro sobre DataFrame conhecido; conversão monetária BR via
``transformers/br_locale.convert_br_currency_columns``.
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.senado.remuneracoes_transformer import (
    SenadoRemuneracoesTransformer,
)

MONTH_URL = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/remuneracoes/2026/7"


def _raw_row(
    sequencial: int = 2341271,
    nome: str = "AILTON OLIVEIRA DE ALMEIDA",
    tipo_folha: str = "Normal",
) -> dict:
    """Monta linha bruta como sai do extrator (com _source_url já injetado).

    Args:
        sequencial: Sequencial do servidor.
        nome: Nome do servidor.
        tipo_folha: ``Normal`` ou ``Suplementar``.

    Returns:
        Dict com os 20 campos brutos + ``_source_url`` da URL mensal.
    """
    return {
        "_source_url": MONTH_URL,
        "abono_permanencia": "0,00",
        "ano": 2026,
        "auxilios": "1.000,00",
        "diarias": "0,00",
        "faltas": "0,00",
        "funcao_comissionada": "9.876,54",
        "gratificacao_natalina": "0,00",
        "horas_extras": "12,34",
        "imposto_renda": "2.345,67",
        "mes": 7,
        "nome": nome,
        "outras_eventuais": "0,00",
        "previdencia": "-9.463,65",
        "remuneracao_basica": "1.234,56",
        "remuneracao_liquida": "-9.463,65",
        "reversao_teto_constitucional": "0,00",
        "sequencial": sequencial,
        "tipo_folha": tipo_folha,
        "vantagens_indenizatorias": "0,00",
        "vantagens_pessoais": "0,00",
    }


class TestSenadoRemuneracoesTransformer:
    """Contrato Silver: converte moeda BR, preserva chave e tipa estrito."""

    def test_happy_path_converte_moedas_br(self):
        """Strings BR (``"1.234,56"``, ``"-9.463,65"``) viram Float64 corretos."""
        tr = SenadoRemuneracoesTransformer()
        raw = pl.DataFrame([_raw_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.height == 1
        # Chave preservada
        assert out["sequencial"][0] == 2341271
        assert out["nome"][0] == "AILTON OLIVEIRA DE ALMEIDA"
        assert out["mes"][0] == 7
        assert out["ano"][0] == 2026
        assert out["tipo_folha"][0] == "Normal"
        # Conversão monetária
        assert out["remuneracao_basica"][0] == 1234.56
        assert out["funcao_comissionada"][0] == 9876.54
        assert out["horas_extras"][0] == 12.34
        assert out["imposto_renda"][0] == 2345.67
        assert out["auxilios"][0] == 1000.00
        # Valores negativos (proventos > vencimentos)
        assert out["previdencia"][0] == -9463.65
        assert out["remuneracao_liquida"][0] == -9463.65

    def test_tipo_folha_suplementar_preservado(self):
        """Folha suplementar é dado real — ``tipo_folha`` preservado na Silver."""
        tr = SenadoRemuneracoesTransformer()
        raw = pl.DataFrame([_raw_row(tipo_folha="Suplementar")], infer_schema_length=None)
        out = tr.transform(raw)

        assert out["tipo_folha"][0] == "Suplementar"
        assert out.height == 1

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = SenadoRemuneracoesTransformer()
        raw = pl.DataFrame([_raw_row()], infer_schema_length=None)
        out = tr.transform(raw)

        contract = SILVER_SCHEMAS[DomainType.REMUNERACOES.value]
        assert set(out.columns) == set(contract)
        assert out.columns[0] == "_source_url"
        assert out.schema["_source_url"] == pl.String
        assert out.schema["sequencial"] == pl.Int64
        assert out.schema["nome"] == pl.String
        assert out.schema["mes"] == pl.Int64
        assert out.schema["ano"] == pl.Int64
        assert out.schema["tipo_folha"] == pl.String
        # 15 campos monetários → Float64
        monetarios = [
            "remuneracao_basica",
            "vantagens_pessoais",
            "funcao_comissionada",
            "gratificacao_natalina",
            "horas_extras",
            "outras_eventuais",
            "abono_permanencia",
            "reversao_teto_constitucional",
            "imposto_renda",
            "previdencia",
            "faltas",
            "remuneracao_liquida",
            "diarias",
            "auxilios",
            "vantagens_indenizatorias",
        ]
        for col in monetarios:
            assert out.schema[col] == pl.Float64

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoRemuneracoesTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras no input (ex: futuro campo novo da API) são descartadas."""
        tr = SenadoRemuneracoesTransformer()
        row = _raw_row()
        row["campo_futuro"] = "deve sumir"
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert "campo_futuro" not in out.columns
        contract = SILVER_SCHEMAS[DomainType.REMUNERACOES.value]
        assert set(out.columns) == set(contract)
