"""Testes do SenadoVotacoesTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.votacoes_senado_transformer import (
    SenadoVotacoesTransformer,
)


class TestSenadoVotacoesTransformer:
    """Testes do contrato SILVER para votacoes_senado."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoVotacoesTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": 6954,
                    "codigoMateria": 167447,
                    "idProcesso": 8799208,
                    "identificacao": "MPV 1291/2025",
                    "ementa": "Altera a Lei...",
                    "dataApresentacao": "2025-03-06",
                    "dataSessao": "2025-07-01",
                    "descricaoVotacao": "Votação nominal...",
                    "resultadoVotacao": "A",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["votacao_id"][0] == 6954
        assert out["identificacao"][0] == "MPV 1291/2025"
        assert out["resultado"][0] == "A"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoVotacoesTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_nested_fields_dropped(self):
        """Campos aninhados (informeLegislativo, votos) são descartados."""
        tr = SenadoVotacoesTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": 6954,
                    "codigoMateria": 167447,
                    "idProcesso": 8799208,
                    "identificacao": "MPV 1291/2025",
                    "ementa": "Altera...",
                    "dataApresentacao": "2025-03-06",
                    "dataSessao": "2025-07-01",
                    "descricaoVotacao": "Votação...",
                    "resultadoVotacao": "A",
                    "votos": [{"codigoParlamentar": 5672}],
                    "informeLegislativo": {"texto": "..."},
                }
            ]
        )
        out = tr.transform(raw)

        assert "votos" not in out.columns
        assert "informeLegislativo" not in out.columns
        assert out.height == 1

    def test_type_coercion(self):
        """Campos numéricos são coeridos."""
        tr = SenadoVotacoesTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": "6954",
                    "codigoMateria": "167447",
                    "idProcesso": "8799208",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["votacao_id"] == pl.Int64
        assert out.schema["codigo_materia"] == pl.Int64
        assert out.schema["id_processo"] == pl.Int64
