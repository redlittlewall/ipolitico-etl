"""Testes do SenadoMandatosTransformer — contrato Silver."""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.senado.senadores_mandatos_transformer import (
    SenadoMandatosTransformer,
)


def _raw_mandato_row(
    codigo: str = "5672",
    codigo_mandato: str = "1001",
    uf: str = "AC",
    descricao: str = "Titular",
    primeira_leg: str = "57",
    segunda_leg: str = "57",
    partido: str = "PP",
    data_inicio: str = "2023-02-01",
    data_fim: str = "2027-01-31",
) -> dict:
    """Helper para criar uma linha bruta de mandato (como sai da API)."""
    return {
        "CodigoParlamentar": codigo,
        "CodigoMandato": codigo_mandato,
        "Uf": uf,
        "DescricaoParticipacao": descricao,
        "PrimeiraLegislatura": primeira_leg,
        "SegundaLegislatura": segunda_leg,
        "SiglaPartido": partido,
        "DataInicio": data_inicio,
        "DataFim": data_fim,
    }


class TestSenadoMandatosTransformer:
    """Testes do contrato SILVER para senadores_mandatos."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada no Silver."""
        tr = SenadoMandatosTransformer()
        raw = pl.DataFrame([_raw_mandato_row()])
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 5672
        assert out["codigo_mandato"][0] == 1001
        assert out["uf"][0] == "AC"
        assert out["descricao_participacao"][0] == "Titular"
        assert out["primeira_legislatura"][0] == 57
        assert out["segunda_legislatura"][0] == 57
        assert out["sigla_partido"][0] == "PP"
        assert out["data_inicio"][0] == "2023-02-01"
        assert out["data_fim"][0] == "2027-01-31"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoMandatosTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = SenadoMandatosTransformer()
        raw = pl.DataFrame([_raw_mandato_row()])
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["codigo_mandato"] == pl.Int64
        assert out.schema["primeira_legislatura"] == pl.Int64
        assert out.schema["uf"] == pl.String
        assert out.schema["sigla_partido"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras no input são descartadas."""
        tr = SenadoMandatosTransformer()
        row = _raw_mandato_row()
        row["coluna_extra"] = "deve sumir"
        raw = pl.DataFrame([row])
        out = tr.transform(raw)

        assert "coluna_extra" not in out.columns
        assert out.height == 1

    def test_contract_strict(self):
        """Saída respeita exatamente o contrato Silver (colunas + tipos)."""
        tr = SenadoMandatosTransformer()
        raw = pl.DataFrame([_raw_mandato_row()])
        out = tr.transform(raw)

        contract = SILVER_SCHEMAS[DomainType.SENADORES_MANDATOS.value]
        assert list(out.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert out.schema[col] == dtype, f"{col}: esperado {dtype}, obtido {out.schema[col]}"
