"""
Testes para transformers de entidades institucionais e novos domínios bulk-only.
"""

import polars as pl
import pytest
from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.camara.institutional_transformer import (
    CamaraFuncionariosTransformer,
    CamaraTecadCategoriasTransformer,
    CamaraTecadTermosTransformer,
)


class TestCamaraFuncionariosTransformer:
    """Transformer para funcionários da Câmara (bulk-only snapshot)."""

    @pytest.fixture
    def transformer(self):
        return CamaraFuncionariosTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.FUNCIONARIOS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_minimal_columns(self, transformer):
        """Campos mínimos são tipados e selecionados corretamente."""
        raw = pl.DataFrame(
            {
                "ponto": ["P_1234", "P_5678"],
                "codGrupo": ["1", "2"],
                "grupo": ["Quadro Efetivo", "CNE"],
                "nome": ["Ana Silva", "Carlos Souza"],
                "cargo": ["Técnico", "Analista"],
                "lotacao": ["Setor A", "Setor B"],
                "atoNomeacao": ["", ""],
                "dataNomeacao": ["", "2023-01-15"],
                "dataInicioHistorico": ["2020-03-01", "2020-05-10"],
                "dataPubNomeacao": ["", ""],
                "funcao": ["FC-1", ""],
                "uriLotacao": [
                    "https://dadosabertos.camara.leg.br/api/v2/orgaos/100046",
                    "",
                ],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["ponto"] == pl.String
        assert result.schema["codGrupo"] == pl.Int64
        assert result.schema["nome"] == pl.String
        # Verifica valores após cast
        pontos = result["ponto"].to_list()
        assert "P_1234" in pontos
        assert result["codGrupo"].to_list() == [1, 2]

    def test_transform_missing_column_adds_null(self, transformer):
        """Coluna faltante no CSV ganha NULL, não quebra."""
        raw = pl.DataFrame(
            {
                "ponto": ["P_001"],
                "codGrupo": ["1"],
                "grupo": ["Teste"],
                "nome": ["Teste"],
                "cargo": [""],
                "lotacao": [""],
                "dataInicioHistorico": ["2020-01-01"],
                # demais colunas ausentes
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["uriLotacao"] == pl.String
        assert result["uriLotacao"][0] is None


class TestCamaraTecadCategoriasTransformer:
    """Transformer para categorias TECAD (bulk-only snapshot)."""

    @pytest.fixture
    def transformer(self):
        return CamaraTecadCategoriasTransformer()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "codCategoria": ["200", "300"],
                "categoria": ["Administração Pública", "Agricultura"],
                "codSubCategoria": ["200", "301"],
                "subCategoria": ["Administração Pública", "Pecuária"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["codCategoria"] == pl.Int64
        assert result["codCategoria"].to_list() == [200, 300]
        assert result["codSubCategoria"].to_list() == [200, 301]

    def test_transform_empty(self, transformer):
        raw = pl.DataFrame(
            {
                "codCategoria": pl.Series([], dtype=pl.String),
                "categoria": pl.Series([], dtype=pl.String),
                "codSubCategoria": pl.Series([], dtype=pl.String),
                "subCategoria": pl.Series([], dtype=pl.String),
            }
        )
        result = transformer.transform(raw)
        assert result.is_empty()


class TestCamaraTecadTermosTransformer:
    """Transformer para termos TECAD (bulk-only snapshot)."""

    @pytest.fixture
    def transformer(self):
        return CamaraTecadTermosTransformer()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "codTermo": ["46892", "51668"],
                "termo": ["1ª Guerra Mundial", "14º salário"],
                "categorias": ["Identificador", "Trabalho e Emprego"],
                "subcategorias": ["Identificador de Tempo", "Trabalho e Emprego"],
                "notasExplicativas": ["", ""],
                "notasHistoricas": ["", ""],
                "notasAplicativas": ["", ""],
                "fontes": ["", ""],
                "use": ["Primeira Guerra Mundial", "Décimo quarto salário"],
                "usadoPara": ["", ""],
                "termosEspecificos": ["", ""],
                "termosGenericos": ["", ""],
                "termosRelacionados": ["", ""],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["codTermo"] == pl.Int64
        assert result["codTermo"].to_list() == [46892, 51668]
        assert "use" in result.columns

    def test_transform_empty(self, transformer):
        raw = pl.DataFrame(
            {
                "codTermo": pl.Series([], dtype=pl.String),
                "termo": pl.Series([], dtype=pl.String),
            }
        )
        result = transformer.transform(raw)
        assert result.is_empty()
