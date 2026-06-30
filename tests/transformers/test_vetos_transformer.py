"""Testes do contrato Silver para vetos presidenciais."""

import polars as pl

from ipolitico.transformers.senado.vetos_transformer import (
    VetosDetalheTransformer,
    VetosPresidenciaisTransformer,
)


class TestVetosPresidenciaisTransformer:
    """Testes do contrato SILVER para vetos_presidenciais."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = VetosPresidenciaisTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": 12345,
                    "Ano": 2020,
                    "Numero": "1",
                    "Tipo": "Total",
                    "CasaOrigem": "CN",
                    "SiglaProposicao": "PL 100/2020",
                    "Ementa": "Aprova o texto...",
                    "Autor": "Executivo",
                    "DataApreciacao": "2020-06-15",
                    "Resultado": "Mantido",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 12345
        assert out["ano"][0] == 2020
        assert out["tipo"][0] == "Total"
        assert out["resultado"][0] == "Mantido"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = VetosPresidenciaisTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = VetosPresidenciaisTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "12345",
                    "Ano": "2020",
                    "Numero": "1",
                    "SiglaProposicao": "PL 100/2020",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["ano"] == pl.Int64
        assert out.schema["numero"] == pl.String
        assert out.schema["sigla_proposicao"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: link) são descartadas."""
        tr = VetosPresidenciaisTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": 12345,
                    "Ano": 2020,
                    "Numero": "1",
                    "link": "http://exemplo.com/veto",
                    "texto": "Texto adicional",
                }
            ]
        )
        out = tr.transform(raw)

        assert "link" not in out.columns
        assert "texto" not in out.columns


class TestVetosDetalheTransformer:
    """Testes do contrato SILVER para vetos_detalhe."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = VetosDetalheTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": 12345,
                    "DataVotacao": "2020-06-15",
                    "Resultado": "Mantido",
                    "DescricaoResultado": "Veto mantido pelo Congresso Nacional",
                    "TotalParlamentares": 513,
                    "TotalSim": 350,
                    "TotalNao": 120,
                    "TotalAbstencao": 43,
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 12345
        assert out["data_votacao"][0] == "2020-06-15"
        assert out["resultado"][0] == "Mantido"
        assert out["total_sim"][0] == 350
        assert out["total_nao"][0] == 120

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = VetosDetalheTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos."""
        tr = VetosDetalheTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "12345",
                    "TotalParlamentares": "513",
                    "TotalSim": "350",
                    "TotalNao": "120",
                    "TotalAbstencao": "43",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["total_parlamentares"] == pl.Int64
        assert out.schema["total_sim"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: observacao) são descartadas."""
        tr = VetosDetalheTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": 12345,
                    "DataVotacao": "2020-06-15",
                    "observacao": "Observação extra",
                    "detalhes": "Mais detalhes",
                }
            ]
        )
        out = tr.transform(raw)

        assert "observacao" not in out.columns
        assert "detalhes" not in out.columns
