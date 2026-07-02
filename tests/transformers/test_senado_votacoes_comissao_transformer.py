"""Testes do SenadoVotacoesComissaoTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.votacoes_comissao_transformer import (
    SenadoVotacoesComissaoTransformer,
)


class TestSenadoVotacoesComissaoTransformer:
    """Testes do contrato SILVER para votacoes_comissao."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoVotacoesComissaoTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": 1045,
                    "codigoMateria": 167447,
                    "idProcesso": 8799208,
                    "identificacao": "PL 123/2025",
                    "ementa": "Dispõe sobre...",
                    "dataApresentacao": "2025-03-06",
                    "dataSessao": "2025-07-01",
                    "descricaoVotacao": "Votação nominal...",
                    "resultadoVotacao": "A",
                    "siglaComissao": "CAE",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["votacao_id"][0] == 1045
        assert out["identificacao"][0] == "PL 123/2025"
        assert out["resultado"][0] == "A"
        assert out["sigla_comissao"][0] == "CAE"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoVotacoesComissaoTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_extra_fields_dropped(self):
        """Campos aninhados/extras são descartados."""
        tr = SenadoVotacoesComissaoTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": 1045,
                    "codigoMateria": 167447,
                    "idProcesso": 8799208,
                    "identificacao": "PL 123/2025",
                    "ementa": "Dispõe...",
                    "dataApresentacao": "2025-03-06",
                    "dataSessao": "2025-07-01",
                    "descricaoVotacao": "Votação...",
                    "resultadoVotacao": "A",
                    "siglaComissao": "CAE",
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
        tr = SenadoVotacoesComissaoTransformer()
        raw = pl.DataFrame(
            [
                {
                    "codigoSessaoVotacao": "1045",
                    "codigoMateria": "167447",
                    "idProcesso": "8799208",
                    "siglaComissao": "CAE",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["votacao_id"] == pl.Int64
        assert out.schema["codigo_materia"] == pl.Int64
        assert out.schema["id_processo"] == pl.Int64
