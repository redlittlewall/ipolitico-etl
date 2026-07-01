"""Testes do SenadoFiliacoesTransformer — contrato Silver."""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.senado.senadores_filiacoes_transformer import (
    SenadoFiliacoesTransformer,
)


def _raw_filiacao_row(
    codigo: str = "5672",
    partido: str = "PP",
    data_filiacao: str = "2020-03-10",
    data_desfiliacao: str | None = None,
) -> dict:
    """Helper para criar uma linha bruta de filiação (como sai da API real).

    A API retorna ``Partido`` como struct aninhada.
    """
    return {
        "CodigoParlamentar": int(codigo),
        "Partido": {
            "SiglaPartido": partido,
            "DataFiliacao": data_filiacao,
            "DataDesfiliacao": data_desfiliacao,
        },
    }


class TestSenadoFiliacoesTransformer:
    """Testes do contrato SILVER para senadores_filiacoes."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada no Silver."""
        tr = SenadoFiliacoesTransformer()
        raw = pl.DataFrame([_raw_filiacao_row()])
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 5672
        assert out["sigla_partido"][0] == "PP"
        assert out["data_filiacao"][0] == "2020-03-10"
        assert out["data_desfiliacao"][0] is None

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoFiliacoesTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_type_coercion(self):
        """Campos são corretamente tipados no Silver."""
        tr = SenadoFiliacoesTransformer()
        raw = pl.DataFrame([_raw_filiacao_row()])
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["sigla_partido"] == pl.String
        assert out.schema["data_filiacao"] == pl.String
        assert out.schema["data_desfiliacao"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras no input são descartadas."""
        tr = SenadoFiliacoesTransformer()
        row = _raw_filiacao_row()
        row["coluna_extra"] = "deve sumir"
        raw = pl.DataFrame([row])
        out = tr.transform(raw)

        assert "coluna_extra" not in out.columns
        assert out.height == 1

    def test_contract_strict(self):
        """Saída respeita exatamente o contrato Silver (colunas + tipos)."""
        tr = SenadoFiliacoesTransformer()
        raw = pl.DataFrame([_raw_filiacao_row()])
        out = tr.transform(raw)

        contract = SILVER_SCHEMAS[DomainType.SENADORES_FILIACOES.value]
        assert list(out.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert out.schema[col] == dtype, f"{col}: esperado {dtype}, obtido {out.schema[col]}"

    def test_multiple_rows(self):
        """Múltiplas filiações são processadas corretamente."""
        tr = SenadoFiliacoesTransformer()
        raw = pl.DataFrame(
            [
                _raw_filiacao_row(codigo="5672", partido="PP", data_filiacao="2020-03-10"),
                _raw_filiacao_row(codigo="5672", partido="PSDB", data_filiacao="2015-02-01"),
            ]
        )
        out = tr.transform(raw)

        assert out.height == 2
        assert out["sigla_partido"].to_list() == ["PP", "PSDB"]
