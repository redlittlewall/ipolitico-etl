"""Testes do SenadoSenadoresTransformer — contrato Silver para senadores."""

import polars as pl

from ipolitico.transformers.senado.senadores_transformer import (
    SenadoSenadoresTransformer,
)


def _raw_senador_row(
    codigo: str = "5672",
    nome: str = "Alan Rick",
    nome_completo: str = "Alan Rick Miranda",
    sexo: str = "Masculino",
    uf: str = "AC",
    codigo_mandato: str = "596",
    descricao: str = "Titular",
    primeira_leg: str = "57",
    segunda_leg: str = "58",
) -> dict:
    """Helper para criar uma linha bruta (como sai da API via flatten_response)."""
    return {
        "IdentificacaoParlamentar": {
            "CodigoParlamentar": codigo,
            "NomeParlamentar": nome,
            "NomeCompletoParlamentar": nome_completo,
            "SexoParlamentar": sexo,
        },
        "Mandatos": {
            "Mandato": [
                {
                    "CodigoMandato": codigo_mandato,
                    "UfParlamentar": uf,
                    "DescricaoParticipacao": descricao,
                    "PrimeiraLegislaturaDoMandato": {"NumeroLegislatura": primeira_leg},
                    "SegundaLegislaturaDoMandato": {"NumeroLegislatura": segunda_leg},
                }
            ]
        },
    }


class TestSenadoSenadoresTransformer:
    """Testes do contrato SILVER para senadores."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada no Silver."""
        tr = SenadoSenadoresTransformer()
        raw = pl.DataFrame([_raw_senador_row()])
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 5672
        assert out["nome"][0] == "Alan Rick"
        assert out["uf"][0] == "AC"
        assert out["primeira_legislatura"][0] == 57
        assert out["segunda_legislatura"][0] == 58

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoSenadoresTransformer()
        raw = pl.DataFrame()
        out = tr.transform(raw)
        assert out.is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = SenadoSenadoresTransformer()
        raw = pl.DataFrame([_raw_senador_row()])
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["nome"] == pl.String
        assert out.schema["primeira_legislatura"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas extras no input (ex: Telefones) são descartadas."""
        tr = SenadoSenadoresTransformer()
        row = _raw_senador_row()
        row["coluna_extra"] = "deve sumir"
        raw = pl.DataFrame([row])
        out = tr.transform(raw)

        assert "coluna_extra" not in out.columns
        assert out.height == 1

    def test_multiple_records(self):
        """Múltiplos senadores são processados corretamente."""
        tr = SenadoSenadoresTransformer()
        raw = pl.DataFrame(
            [
                _raw_senador_row(codigo="5672", nome="Alan Rick"),
                _raw_senador_row(codigo="5982", nome="Alessandro Vieira"),
            ]
        )
        out = tr.transform(raw)

        assert out.height == 2
        assert out["codigo"].to_list() == [5672, 5982]

    def test_missing_identificacao_fields(self):
        """Campos opcionais ausentes na API viram null."""
        tr = SenadoSenadoresTransformer()
        row = {
            "IdentificacaoParlamentar": {
                "CodigoParlamentar": "5672",
                "NomeParlamentar": "Alan Rick",
                # NomeCompleto ausente
                "SexoParlamentar": "Masculino",
            },
            "Mandatos": {
                "Mandato": [
                    {
                        "CodigoMandato": "596",
                        "UfParlamentar": "AC",
                        "DescricaoParticipacao": "Titular",
                        "PrimeiraLegislaturaDoMandato": {"NumeroLegislatura": "57"},
                        "SegundaLegislaturaDoMandato": {"NumeroLegislatura": "58"},
                    }
                ]
            },
        }
        raw = pl.DataFrame([row])
        out = tr.transform(raw)

        assert out["nome_completo"].is_null().all()
        assert out["codigo"][0] == 5672
