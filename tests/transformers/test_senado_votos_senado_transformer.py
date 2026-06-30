"""Testes do SenadoVotosTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.votos_senado_transformer import (
    SenadoVotosTransformer,
)


class TestSenadoVotosTransformer:
    """Testes do contrato SILVER para votos_senado."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoVotosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": 6954,
                    "codigoParlamentar": 5672,
                    "nomeParlamentar": "Alan Rick",
                    "siglaPartidoParlamentar": "MDB",
                    "siglaUFParlamentar": "AC",
                    "siglaVotoParlamentar": "Sim",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["votacao_id"][0] == 6954
        assert out["codigo_parlamentar"][0] == 5672
        assert out["nome_parlamentar"][0] == "Alan Rick"
        assert out["sigla_partido"][0] == "MDB"
        assert out["sigla_uf"][0] == "AC"
        assert out["voto"][0] == "Sim"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoVotosTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras (sexo, descricao) são descartadas."""
        tr = SenadoVotosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": 6954,
                    "codigoParlamentar": 5672,
                    "nomeParlamentar": "Alan Rick",
                    "siglaPartidoParlamentar": "MDB",
                    "siglaUFParlamentar": "AC",
                    "siglaVotoParlamentar": "Sim",
                    "sexoParlamentar": "M",
                    "descricaoVotoParlamentar": "Voto normal",
                }
            ]
        )
        out = tr.transform(raw)

        assert "sexoParlamentar" not in out.columns
        assert "descricaoVotoParlamentar" not in out.columns
        assert out.height == 1

    def test_type_coercion(self):
        """Campos numéricos são coeridos."""
        tr = SenadoVotosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": "6954",
                    "codigoParlamentar": "5672",
                    "nomeParlamentar": "Alan Rick",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["votacao_id"] == pl.Int64
        assert out.schema["codigo_parlamentar"] == pl.Int64
        assert out.schema["nome_parlamentar"] == pl.String
