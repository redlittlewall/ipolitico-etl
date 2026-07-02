"""Testes do SenadoOrientacaoBancadaTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.orientacao_bancada_transformer import (
    SenadoOrientacaoBancadaTransformer,
)


class TestSenadoOrientacaoBancadaTransformer:
    """Testes do contrato SILVER para orientacao_bancada."""

    def test_happy_path(self):
        """Campos completos (com ``orientacoesLideranca``) produzem saída tipada."""
        tr = SenadoOrientacaoBancadaTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoVotacaoSve": 10848,
                    "dataInicioVotacao": "2025-01-15T14:00:00",
                    "orientacoesLideranca": [
                        {"dataHora": "2025-01-15T14:10:00", "partido": "PT", "voto": "Sim"},
                        {"dataHora": "2025-01-15T14:10:05", "partido": "PL", "voto": "Não"},
                    ],
                },
            ]
        )
        out = tr.transform(raw)

        # Deve ter 2 linhas (1 por partido dentro da votação)
        assert out.height == 2
        assert out["sigla_partido"][0] == "PT"
        assert out["orientacao"][0] == "Sim"
        assert out["sigla_partido"][1] == "PL"
        assert out["codigo_votacao"][0] == 10848

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
                    "codigoVotacaoSve": "10848",
                    "dataInicioVotacao": "2025-01-15T14:00:00",
                    "orientacoesLideranca": [
                        {"partido": "PT", "voto": "Sim"},
                    ],
                },
            ]
        )
        out = tr.transform(raw)

        assert out.schema["codigo_votacao"] == pl.Int64
