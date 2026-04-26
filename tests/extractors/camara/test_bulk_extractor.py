from unittest.mock import AsyncMock

import polars as pl
import pytest
from ipolitico.extractors.camara.bulk_extractor import CamaraBulkExtractor


@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Simula sucesso no download por padrão
    client.download_file.return_value = True
    return client


@pytest.fixture
def extractor(mock_client):
    return CamaraBulkExtractor(client=mock_client)


def test_build_url_resolves_correctly(extractor):
    """Garante que as regras de negócio das URLs (incluindo a exceção de despesas) funcionam."""
    assert (
        extractor._build_url("deputados")
        == "http://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv"
    )
    assert (
        extractor._build_url("despesas", 2023) == "http://www.camara.leg.br/cotas/Ano-2023.csv.zip"
    )
    assert (
        extractor._build_url("proposicoes", 2023)
        == "http://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-2023.csv"
    )

    with pytest.raises(ValueError):
        extractor._build_url("dominio_inexistente", 2023)


def test_standardize_schema(extractor):
    """Garante que a fase de tradução de colunas mapeia os nomes do CSV para o padrão da API."""
    # Dataframe simulando o CSV do governo
    df_csv = pl.DataFrame(
        {"nuDeputadoId": ["123"], "datEmissao": ["2023-01-01"], "colunaIgnorada": ["nao me altere"]}
    )

    df_padronizado = extractor._standardize_schema(df_csv, "despesas")

    # As colunas alvo devem ter sido traduzidas
    assert "id_deputado" in df_padronizado.columns
    assert "dataDocumento" in df_padronizado.columns
    assert "nuDeputadoId" not in df_padronizado.columns

    # Colunas não mapeadas devem permanecer intactas
    assert "colunaIgnorada" in df_padronizado.columns
