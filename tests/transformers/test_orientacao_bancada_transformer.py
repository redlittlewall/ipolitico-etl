"""Testes do SenadoOrientacaoBancadaTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.orientacao_bancada_transformer import (
    SenadoOrientacaoBancadaTransformer,
)


class TestSenadoOrientacaoBancadaTransformer:
    """Testes do contrato SILVER para orientacao_bancada."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoOrientacaoBancadaTransformer()
        raw = pl.DataFrame(
            [
                {
                    "dataSessao": "2025-01-15",
                    "codigoMateria": 167447,
                    "siglaPartido": "PT",
                    "orientacao": "Sim",
                    "codigoVotacao": 6954,
                },
                {
                    "dataSessao": "2025-01-15",
                    "codigoMateria": 167447,
                    "siglaPartido": "PL",
                    "orientacao": "Não",
                    "codigoVotacao": 6954,
                },
            ]
        )
        out = tr.transform(raw)

        assert out.height == 2
        assert out["sigla_partido"][0] == "PT"
        assert out["orientacao"][0] == "Sim"
        assert out["sigla_partido"][1] == "PL"
        assert out["codigo_votacao"][0] == 6954

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoOrientacaoBancadaTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos de string para Int64."""
        tr = SenadoOrientacaoBancadaTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoVotacao": "6954",
                    "codigoMateria": "167447",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["codigo_votacao"] == pl.Int64
        assert out.schema["codigo_materia"] == pl.Int64
