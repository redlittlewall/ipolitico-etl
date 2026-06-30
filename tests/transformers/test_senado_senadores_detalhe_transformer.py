"""Testes do SenadoSenadoresDetalheTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.senadores_detalhe_transformer import (
    SenadoSenadoresDetalheTransformer,
)


def _raw_detalhe_row(
    codigo: str = "5672",
    nome: str = "Alan Rick",
    nome_completo: str = "Alan Rick Miranda",
    sexo: str = "Masculino",
    url_foto: str = "http://foto.jpg",
    url_pagina: str = "http://perfil",
    email: str = "alan@senado.leg.br",
    data_nasc: str = "1976-10-23",
    naturalidade: str = "Rio Branco",
    uf_nat: str = "AC",
) -> dict:
    """Helper para criar uma linha bruta de detalhe (como sai da API)."""
    return {
        "IdentificacaoParlamentar": {
            "CodigoParlamentar": codigo,
            "NomeParlamentar": nome,
            "NomeCompletoParlamentar": nome_completo,
            "SexoParlamentar": sexo,
            "UrlFotoParlamentar": url_foto,
            "UrlPaginaParlamentar": url_pagina,
            "EmailParlamentar": email,
        },
        "DadosBasicosParlamentar": {
            "DataNascimento": data_nasc,
            "Naturalidade": naturalidade,
            "UfNaturalidade": uf_nat,
        },
    }


class TestSenadoSenadoresDetalheTransformer:
    """Testes do contrato SILVER para senadores_detalhe."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada no Silver."""
        tr = SenadoSenadoresDetalheTransformer()
        raw = pl.DataFrame([_raw_detalhe_row()])
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 5672
        assert out["nome"][0] == "Alan Rick"
        assert out["data_nascimento"][0] == "1976-10-23"
        assert out["naturalidade"][0] == "Rio Branco"
        assert out["uf_naturalidade"][0] == "AC"
        assert out["url_foto"][0] == "http://foto.jpg"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoSenadoresDetalheTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = SenadoSenadoresDetalheTransformer()
        raw = pl.DataFrame([_raw_detalhe_row()])
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["nome"] == pl.String
        assert out.schema["data_nascimento"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras no input são descartadas."""
        tr = SenadoSenadoresDetalheTransformer()
        row = _raw_detalhe_row()
        row["coluna_extra"] = "deve sumir"
        raw = pl.DataFrame([row])
        out = tr.transform(raw)

        assert "coluna_extra" not in out.columns
        assert out.height == 1

    def test_missing_basicos_fields(self):
        """Campos DadosBasicosParlamentar ausentes viram null."""
        tr = SenadoSenadoresDetalheTransformer()
        row = {
            "IdentificacaoParlamentar": {
                "CodigoParlamentar": "5672",
                "NomeParlamentar": "Alan Rick",
                "NomeCompletoParlamentar": "Alan Rick Miranda",
                "SexoParlamentar": "Masculino",
                "UrlFotoParlamentar": "http://foto.jpg",
                "UrlPaginaParlamentar": "http://perfil",
                "EmailParlamentar": "alan@senado.leg.br",
            },
            # DadosBasicosParlamentar completamente ausente
        }
        raw = pl.DataFrame([row])
        out = tr.transform(raw)

        assert out["data_nascimento"].is_null().all()
        assert out["naturalidade"].is_null().all()
        assert out["uf_naturalidade"].is_null().all()
        assert out["codigo"][0] == 5672
