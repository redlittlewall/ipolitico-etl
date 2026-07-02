"""Testes do transformer institucional do Senado (comissões)."""

import polars as pl
import pytest

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.senado.institutional_transformer import (
    SenadoComissoesDetalheTransformer,
    SenadoComissoesListaTransformer,
    SenadoComissoesMembrosTransformer,
    SenadoComissoesReunioesTransformer,
)


class TestSenadoComissoesListaTransformer:
    """Transformer para o domínio comissoes_senado (lista)."""

    @pytest.fixture
    def transformer(self):
        return SenadoComissoesListaTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.COMISSOES_SENADO.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_minimal_columns(self, transformer):
        """Campos com nomes da API são renomeados e tipados."""
        raw = pl.DataFrame(
            {
                "Codigo": ["38", "40"],
                "Sigla": ["CAE", "CAS"],
                "Nome": ["Comissão de Assuntos Econômicos", "Comissão de Assuntos Sociais"],
                "DataInicio": ["1900-01-01", "1900-01-01"],
                "Publica": ["S", "S"],
                "CodigoTipoColegiado": ["21", "21"],
                "SiglaTipoColegiado": ["PERMANENTE", "PERMANENTE"],
                "DescricaoTipoColegiado": ["Comissão Permanente", "Comissão Permanente"],
                "SiglaCasa": ["SF", "SF"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["codigo"] == pl.Int64
        assert result.schema["sigla"] == pl.String
        assert result.schema["sigla_casa"] == pl.String
        assert result["codigo"].to_list() == [38, 40]

    def test_transform_missing_column_adds_null(self, transformer):
        """Coluna 'finalidade' faltante é adicionada como NULL."""
        raw = pl.DataFrame(
            {
                "Codigo": ["38"],
                "Sigla": ["CAE"],
                "Nome": ["Comissão"],
                "DataInicio": ["1900-01-01"],
                "Publica": ["S"],
                "CodigoTipoColegiado": ["21"],
                "SiglaTipoColegiado": ["PERMANENTE"],
                "DescricaoTipoColegiado": ["Permanente"],
                "SiglaCasa": ["SF"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result["finalidade"][0] is None


class TestSenadoComissoesDetalheTransformer:
    """Transformer para o domínio comissoes_detalhe."""

    @pytest.fixture
    def transformer(self):
        return SenadoComissoesDetalheTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.COMISSOES_DETALHE.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_serializes_struct_columns(self, transformer):
        """Colunas struct (Cargos, etc.) são serializadas para JSON string."""
        raw = pl.DataFrame(
            {
                "CodigoColegiado": ["38"],
                "NomeColegiado": ["Comissão de Assuntos Econômicos"],
                "SiglaColegiado": ["CAE"],
                "DataInicio": ["01/01/1900"],
                "Cargos": [{"Cargo": [{"TipoCargo": "PRESIDENTE"}]}],
                "Requerimentos": [{}],
                "QuantidadesMembros": [{"Distribuicao": {"Senadores": "54"}}],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["codigo"] == pl.Int64
        assert result.schema["cargos"] == pl.String
        assert "PRESIDENTE" in result["cargos"][0]

    def test_transform_missing_structs(self, transformer):
        """Sem struct columns, não quebra."""
        raw = pl.DataFrame(
            {
                "CodigoColegiado": ["38"],
                "NomeColegiado": ["Comissão"],
                "SiglaColegiado": ["CAE"],
                "DataInicio": ["01/01/1900"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result["cargos"][0] is None
        assert result["requerimentos"][0] is None
        assert result["quantidades_membros"][0] is None


class TestSenadoComissoesReunioesTransformer:
    """Transformer para o domínio comissoes_reunioes (agenda)."""

    @pytest.fixture
    def transformer(self):
        return SenadoComissoesReunioesTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.COMISSOES_REUNIOES.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        """Campos com nomes da API são renomeados e tipados."""
        raw = pl.DataFrame(
            {
                "codigo": ["13683"],
                "versao": ["2026-03-19T02:03:51.827"],
                "descricao": ["33ª, Extraordinária"],
                "titulo": ["33ª Reunião Extraordinária"],
                "CodigoColegiado": ["834"],
                "SiglaColegiado": ["CDH"],
                "NomeColegiado": ["Comissão de Direitos Humanos"],
                "dataInicio": ["2025-06-30T09:30:00.000"],
                "local": ["Anexo II"],
                "situacao": ["Realizada"],
                "status": ["Realizada"],
                "secreta": ["false"],
                "tipoPresenca": ["Presencial"],
                "realizada": ["true"],
                "confirmada": ["false"],
                "codigoSituacao": ["6"],
                "linkECidadania": ["https://example.com"],
                "urlUltimaPautaSimplesPublicada": ["https://example.com/pauta"],
                "urlUltimaPautaCheiaPublicada": ["https://example.com/cheia"],
                "urlUltimoResultadoPublicado": ["https://example.com/resultado"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["codigo"] == pl.Int64
        assert result.schema["codigo_colegiado"] == pl.Int64
        assert result.schema["codigo_situacao"] == pl.Int64
        assert result["codigo"].to_list() == [13683]
        assert result["codigo_colegiado"].to_list() == [834]

    def test_transform_missing_columns_adds_null(self, transformer):
        """Colunas opcionais faltantes viram NULL."""
        raw = pl.DataFrame(
            {
                "codigo": ["13683"],
                "versao": ["2026-03-19"],
                "dataInicio": ["2025-06-30"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result["titulo"][0] is None
        assert result["local"][0] is None


class TestSenadoComissoesMembrosTransformer:
    """Transformer para o domínio comissoes_membros."""

    @pytest.fixture
    def transformer(self):
        return SenadoComissoesMembrosTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.COMISSOES_MEMBROS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        """Campos com nomes da API são renomeados e tipados."""
        raw = pl.DataFrame(
            {
                "CodigoComissao": ["38"],
                "SiglaComissao": ["CAE"],
                "NomeComissao": ["Comissão de Assuntos Econômicos"],
                "NomeMembro": ["Alan Rick"],
                "CodigoMembro": ["5672"],
                "TipoVaga": ["Titular"],
                "IndicadorVagaAtiva": ["Sim"],
                "DataInicioMembroVaga": ["2025-11-26"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["codigo_comissao"] == pl.Int64
        assert result.schema["codigo_membro"] == pl.Int64
        assert result.schema["nome_membro"] == pl.String
        assert result["codigo_comissao"].to_list() == [38]
        assert result["codigo_membro"].to_list() == [5672]
