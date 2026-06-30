"""Testes do SenadoProcessosTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.processos_transformer import (
    SenadoProcessosTransformer,
)


class TestSenadoProcessosTransformer:
    """Testes do contrato SILVER para processos."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoProcessosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 1326805,
                    "codigoMateria": 603,
                    "identificacao": "PDS 16/1984",
                    "ementa": "Aprova o texto...",
                    "autoria": "Câmara dos Deputados",
                    "tipoDocumento": "Projeto de Decreto Legislativo",
                    "dataApresentacao": "1949-05-31",
                    "situacaoAtual": "MATÉRIA COM A RELATORIA",
                    "dataSituacaoAtual": "2023-03-23",
                    "casaIdentificadora": "SF",
                    "tramitando": "Sim",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id"][0] == 1326805
        assert out["identificacao"][0] == "PDS 16/1984"
        assert out["tramitando"][0] == "Sim"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoProcessosTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = SenadoProcessosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": "1326805",
                    "codigoMateria": "603",
                    "identificacao": "PDS 16/1984",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["id"] == pl.Int64
        assert out.schema["codigo_materia"] == pl.Int64
        assert out.schema["identificacao"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: objetivo) são descartadas."""
        tr = SenadoProcessosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 1,
                    "codigoMateria": 1,
                    "identificacao": "Teste",
                    "objetivo": "Revisora",  # não está no contrato
                    "tipoConteudo": "Apreciação",
                }
            ]
        )
        out = tr.transform(raw)

        assert "objetivo" not in out.columns
        assert "tipoConteudo" not in out.columns
