"""Testes do contrato Silver para discursos e notas taquigráficas."""

import polars as pl

from ipolitico.transformers.senado.discursos_transformer import (
    DiscursosPlenarioTransformer,
    DiscursosSenadorTransformer,
    DiscursosTextoTransformer,
    NotasTaquigrafiaReuniaoTransformer,
    NotasTaquigrafiaSessaoTransformer,
)


class TestDiscursosPlenarioTransformer:
    """Testes do contrato SILVER para discursos_plenario."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = DiscursosPlenarioTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": 12345,
                    "Data": "2025-03-15",
                    "TipoDiscurso": "Pela ordem",
                    "Fase": "Ordem do Dia",
                    "Resumo": "Discussão sobre o PL 123/2025",
                    "NomeParlamentar": "Sen. João Silva",
                    "SiglaPartido": "PT",
                    "UF": "SP",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 12345
        assert out["data"][0] == "2025-03-15"
        assert out["tipo_discurso"][0] == "Pela ordem"
        assert out["fase"][0] == "Ordem do Dia"
        assert out["nome_parlamentar"][0] == "Sen. João Silva"
        assert out["sigla_partido"][0] == "PT"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = DiscursosPlenarioTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = DiscursosPlenarioTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "12345",
                    "Data": "2025-03-15",
                    "TipoDiscurso": "Pela ordem",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["data"] == pl.String
        assert out.schema["tipo_discurso"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras são descartadas."""
        tr = DiscursosPlenarioTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": 12345,
                    "Data": "2025-03-15",
                    "TipoDiscurso": "Pela ordem",
                    "link_extra": "http://exemplo.com",
                }
            ]
        )
        out = tr.transform(raw)

        assert "link_extra" not in out.columns
        assert out.height == 1


class TestDiscursosSenadorTransformer:
    """Testes do contrato SILVER para senadores_discursos."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = DiscursosSenadorTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "54321",
                    "CodigoParlamentar": "123",
                    "NomeParlamentar": "Sen. João Silva",
                    "SiglaPartido": "PT",
                    "UF": "SP",
                    "Data": "2025-03-15",
                    "Hora": "14:30",
                    "TipoDiscurso": "Grande Expediente",
                    "Resumo": "Pronunciamento sobre educação",
                    "Texto": "Senhor presidente...",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 54321
        assert out["codigo_parlamentar"][0] == 123
        assert out["nome_parlamentar"][0] == "Sen. João Silva"
        assert out["sigla_partido"][0] == "PT"
        assert out["data"][0] == "2025-03-15"
        assert out["hora"][0] == "14:30"
        assert out["tipo_discurso"][0] == "Grande Expediente"
        assert out["resumo"][0] == "Pronunciamento sobre educação"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = DiscursosSenadorTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos."""
        tr = DiscursosSenadorTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "54321",
                    "CodigoParlamentar": "123",
                    "Data": "2025-03-15",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["codigo_parlamentar"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas extras são descartadas."""
        tr = DiscursosSenadorTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "54321",
                    "Data": "2025-03-15",
                    "TipoDiscurso": "Grande Expediente",
                    "meta": "extra field",
                }
            ]
        )
        out = tr.transform(raw)

        assert "meta" not in out.columns
        assert "codigo" in out.columns


class TestDiscursosTextoTransformer:
    """Testes do contrato SILVER para discursos_texto."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = DiscursosTextoTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": 12345,
                    "Texto": "Senhor presidente...",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 12345
        assert out["texto"][0] == "Senhor presidente..."

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = DiscursosTextoTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Código numérico é coerido."""
        tr = DiscursosTextoTransformer()
        raw = pl.DataFrame([{"Codigo": "12345"}])
        out = tr.transform(raw)
        assert out.schema["codigo"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas extras são descartadas."""
        tr = DiscursosTextoTransformer()
        raw = pl.DataFrame([{"Codigo": 12345, "extra": "field"}])
        out = tr.transform(raw)
        assert "extra" not in out.columns


class TestNotasTaquigrafiaSessaoTransformer:
    """Testes do contrato SILVER para notas_taquigrafia_sessao."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = NotasTaquigrafiaSessaoTransformer()
        raw = pl.DataFrame(
            [
                {
                    "IdSessao": 12345,
                    "Texto": "Notas taquigráficas da sessão...",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id_sessao"][0] == 12345
        assert out["texto"][0] == "Notas taquigráficas da sessão..."

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = NotasTaquigrafiaSessaoTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """ID numérico é coerido."""
        tr = NotasTaquigrafiaSessaoTransformer()
        raw = pl.DataFrame([{"IdSessao": "12345"}])
        out = tr.transform(raw)
        assert out.schema["id_sessao"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas extras são descartadas."""
        tr = NotasTaquigrafiaSessaoTransformer()
        raw = pl.DataFrame([{"IdSessao": 12345, "extra": "field"}])
        out = tr.transform(raw)
        assert "extra" not in out.columns


class TestNotasTaquigrafiaReuniaoTransformer:
    """Testes do contrato SILVER para notas_taquigrafia_reuniao."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = NotasTaquigrafiaReuniaoTransformer()
        raw = pl.DataFrame(
            [
                {
                    "IdReuniao": 67890,
                    "Texto": "Notas taquigráficas da reunião...",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id_reuniao"][0] == 67890
        assert out["texto"][0] == "Notas taquigráficas da reunião..."

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = NotasTaquigrafiaReuniaoTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """ID numérico é coerido."""
        tr = NotasTaquigrafiaReuniaoTransformer()
        raw = pl.DataFrame([{"IdReuniao": "67890"}])
        out = tr.transform(raw)
        assert out.schema["id_reuniao"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas extras são descartadas."""
        tr = NotasTaquigrafiaReuniaoTransformer()
        raw = pl.DataFrame([{"IdReuniao": 67890, "extra": "field"}])
        out = tr.transform(raw)
        assert "extra" not in out.columns
