"""Tests for CamaraDetalheTransformer with blocos_detalhe and proposicoes_detalhe schemas."""

import polars as pl
import pytest
from ipolitico.core.constants import DomainType
from ipolitico.transformers.camara.detalhe_transformer import CamaraDetalheTransformer


@pytest.fixture
def transformer():
    return CamaraDetalheTransformer()


class TestBlocosDetalheTransform:
    def test_transform_blocos_detalhe_schema(self, transformer):
        """CamaraDetalheTransformer deve transformar DataFrame para schema blocos_detalhe."""
        raw = pl.DataFrame(
            {
                "id": [1, 2],
                "idLegislatura": [56, 56],
                "nome": ["Bloco A", "Bloco B"],
                "uri": ["https://...", "https://..."],
                "federacao": [True, False],
            }
        )
        result = transformer.transform(raw, sub_domain=DomainType.BLOCOS_DETALHE.value)

        assert not result.is_empty()
        assert result.schema["id"] == pl.Int64
        assert result.schema["federacao"] == pl.Boolean

    def test_transform_blocos_detalhe_adiciona_colunas_faltantes(self, transformer):
        """Colunas ausentes no DataFrame bruto devem ser preenchidas com None."""
        raw = pl.DataFrame({"id": [1]})
        result = transformer.transform(raw, sub_domain=DomainType.BLOCOS_DETALHE.value)

        assert "federacao" in result.columns
        assert result["federacao"].to_list() == [None]


class TestProposicoesDetalheTransform:
    def test_transform_proposicoes_detalhe_schema(self, transformer):
        """CamaraDetalheTransformer deve transformar DataFrame para schema proposicoes_detalhe."""
        raw = pl.DataFrame(
            {
                "id": [257161],
                "uri": ["https://..."],
                "siglaTipo": ["PL"],
                "codTipo": [139],
                "numero": [1234],
                "ano": [2026],
                "ementa": ["Test ementa"],
                "ementaDetalhada": ["Test ementa detalhada"],
                "dataApresentacao": ["2026-01-15T10:00:00"],
                "uriOrgaoNumerador": ["https://..."],
                "statusProposicao": ['{"dataHora": "2026-01-15T10:00:00"}'],
                "uriAutores": ["https://..."],
                "descricaoTipo": ["Projeto de Lei"],
                "keywords": ["teste"],
                "urlInteiroTeor": ["https://..."],
            }
        )
        result = transformer.transform(raw, sub_domain=DomainType.PROPOSICOES_DETALHE.value)

        assert not result.is_empty()
        assert result.schema["id"] == pl.Int64
        assert result.schema["dataApresentacao"] == pl.Datetime
        assert result.schema["statusProposicao"] == pl.String

    def test_transform_proposicoes_detalhe_vazio_retorna_vazio(self, transformer):
        """DataFrame vazio deve retornar vazio sem erro."""
        raw = pl.DataFrame()
        result = transformer.transform(raw, sub_domain=DomainType.PROPOSICOES_DETALHE.value)

        assert result.is_empty()


class TestDeputadosDetalheTransform:
    """Testes do CamaraDetalheTransformer com schema deputados_detalhe."""

    def test_data_falecimento_null_nao_quebra(self, transformer):
        """dataFalecimento null para deputados vivos nao deve quebrar str.slice."""
        raw = pl.DataFrame(
            {
                "id": [1, 2],
                "nome": ["Alice", "Bob"],
                "dataFalecimento": [None, None],
                "dataNascimento": ["1970-01-15", "1980-06-20"],
                "cpf": ["123.456.789-00", "987.654.321-00"],
                "siglaPartido": ["PT", "PSDB"],
                "siglaUf": ["SP", "RJ"],
                "sexo": ["F", "M"],
                "site": ["https://alice", "https://bob"],
                "situacao": ["Ativo", "Ativo"],
                "condicaoEleitoral": ["Titular", "Titular"],
                "gabinete": ['{"nome":"A"}', '{"nome":"B"}'],
            }
        )
        result = transformer.transform(raw, sub_domain=DomainType.DEPUTADOS_DETALHE.value)

        assert result.height == 2
        assert result["dataFalecimento"].dtype == pl.String
        assert result["dataFalecimento"].to_list() == [None, None]
        assert result["dataNascimento"].to_list() == ["1970-01-15", "1980-06-20"]
