"""Testes para o CamaraDeputadoChildTransformer (profissoes, ocupacoes, mandatos_externos, etc.)."""

import polars as pl
from ipolitico.transformers.camara.deputado_child_transformer import CamaraDeputadoChildTransformer


def test_profissoes_contract():
    tr = CamaraDeputadoChildTransformer()
    raw = pl.DataFrame(
        {
            "id_deputado": [1],
            "titulo": ["Engenheiro"],
            "entidade": ["CREA"],
            "anoInicio": [2010],
            "anoFim": [2020],
        }
    )
    out = tr.transform(raw, sub_domain="profissoes")
    assert out.height == 1
    assert out["titulo"][0] == "Engenheiro"


class TestMandatosExternosTransformer:
    """Testes do contrato SILVER para mandatos_externos (/deputados/{id}/mandatosExternos)."""

    def test_happy_path(self):
        """Campos mínimos do contrato produzem saída tipada."""
        tr = CamaraDeputadoChildTransformer()
        raw = pl.DataFrame(
            {
                "id_deputado": [123],
                "anoFim": [2022],
                "anoInicio": [2018],
                "cargo": ["Vereador"],
                "municipio": ["São Paulo"],
                "siglaPartidoEleicao": ["PSDB"],
                "siglaUf": ["SP"],
            }
        )
        out = tr.transform(raw, sub_domain="mandatos_externos")
        assert out.height == 1
        assert out["id_deputado"][0] == 123
        assert out["cargo"][0] == "Vereador"
        assert out["siglaUf"][0] == "SP"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = CamaraDeputadoChildTransformer()
        raw = pl.DataFrame()
        out = tr.transform(raw, sub_domain="mandatos_externos")
        assert out.is_empty()

    def test_missing_columns_added_as_null(self):
        """Colunas do contrato ausentes no input são adicionadas como NULL."""
        tr = CamaraDeputadoChildTransformer()
        raw = pl.DataFrame(
            {
                "id_deputado": [456],
                "cargo": ["Prefeito"],
            }
        )
        out = tr.transform(raw, sub_domain="mandatos_externos")
        # Todas as colunas do contrato devem existir
        assert set(out.columns) == {
            "id_deputado",
            "anoFim",
            "anoInicio",
            "cargo",
            "municipio",
            "siglaPartidoEleicao",
            "siglaUf",
        }
        # Colunas ausentes ficam como null
        assert out["anoFim"].is_null().all()
        assert out["municipio"].is_null().all()

    def test_extra_columns_dropped(self):
        """Colunas extras no input são descartadas pelo contrato."""
        tr = CamaraDeputadoChildTransformer()
        raw = pl.DataFrame(
            {
                "id_deputado": [789],
                "anoInicio": [2015],
                "anoFim": [2020],
                "cargo": ["Deputado Estadual"],
                "municipio": ["Belo Horizonte"],
                "siglaPartidoEleicao": ["PT"],
                "siglaUf": ["MG"],
                "coluna_extra": ["deve sumir"],
            }
        )
        out = tr.transform(raw, sub_domain="mandatos_externos")
        assert "coluna_extra" not in out.columns
        assert out.height == 1

    def test_type_coercion(self):
        """Tipos numéricos são coeridos mesmo se input vier como string."""
        tr = CamaraDeputadoChildTransformer()
        raw = pl.DataFrame(
            {
                "id_deputado": ["999"],
                "anoInicio": ["2020"],
                "anoFim": ["2024"],
                "cargo": ["Deputado Federal"],
                "municipio": ["Brasília"],
                "siglaPartidoEleicao": ["UNIÃO"],
                "siglaUf": ["DF"],
            }
        )
        out = tr.transform(raw, sub_domain="mandatos_externos")
        assert out.schema["id_deputado"] == pl.Int64
        assert out.schema["anoInicio"] == pl.Int64
        assert out.schema["anoFim"] == pl.Int64
        assert out.schema["cargo"] == pl.String
        assert out["id_deputado"][0] == 999

    def test_multiple_records(self):
        """Múltiplos mandatos externos para o mesmo deputado."""
        tr = CamaraDeputadoChildTransformer()
        raw = pl.DataFrame(
            {
                "id_deputado": [1, 1, 1],
                "anoInicio": [2008, 2012, 2016],
                "anoFim": [2012, 2016, 2020],
                "cargo": ["Vereador", "Prefeito", "Deputado Estadual"],
                "municipio": ["A", "B", "C"],
                "siglaPartidoEleicao": ["PV", "PSB", "PT"],
                "siglaUf": ["RJ", "RJ", "RJ"],
            }
        )
        out = tr.transform(raw, sub_domain="mandatos_externos")
        assert out.height == 3
        assert out["cargo"].to_list() == ["Vereador", "Prefeito", "Deputado Estadual"]
