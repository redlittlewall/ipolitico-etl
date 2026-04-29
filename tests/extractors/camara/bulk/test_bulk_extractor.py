"""
Testes Unitários dos Extratores Bulk (Dumps Massivos).
Focado em validar o fluxo Disk-to-Database (Streaming),
limpeza nuclear de cabeçalhos e a lógica de descompactação de ZIPs governamentais.
"""

from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.extractors.camara.bulk.votacoes_bulk import VotosBulkExtractor


# --- CLASSES DUMMY PARA TESTAR A HERANÇA E ERROS DE INTEGRAÇÃO ---
class UnmappedBulk(BaseBulkExtractor):
    domain_name = "dominio_fantasma"


class MissingYearBulk(BaseBulkExtractor):
    domain_name = "despesas"  # Sabemos que despesas exige ano no registry


class EmptyDomainBulk(BaseBulkExtractor):
    domain_name = ""


class ValidZipBulk(BaseBulkExtractor):
    domain_name = "despesas"


class ValidCsvBulk(BaseBulkExtractor):
    domain_name = "deputados"


# Classe Falsa (Dummy) para testarmos a classe Base isoladamente
class DummyBulkExtractor(BaseBulkExtractor):
    domain_name = "dummy"

    def _build_url(self, year=None):
        # Simulamos uma URL que baixa um ZIP para testarmos a ramificação de extração
        return "http://dadosabertos.camara.leg.br/arquivos/dummy/csv/dummy.csv.zip"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        return df


@pytest.fixture
def mock_client():
    """Mock do CamaraClient que sempre diz que o download foi um sucesso."""
    client = AsyncMock()
    client.download_file = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_sink():
    """Mock do consumidor (Sink) que vai receber os chunks de dados."""
    return AsyncMock()


@pytest.mark.asyncio
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.scan_csv")
@patch("ipolitico.extractors.camara.bulk.base_bulk.zipfile.ZipFile")
async def test_base_bulk_extraction_flow(mock_zipfile, mock_scan_csv, mock_client, mock_sink):
    """
    CRÍTICO: Testa o fluxo completo de um Dump ZIP.
    Garante que o arquivo é descompactado, lido via Lazy API e que a
    Limpeza Nuclear de BOM (Byte Order Mark) ocorre antes do Sink.
    """
    # 1. Configurando o Mock do ZipFile
    mock_zip_instance = MagicMock()
    mock_zip_instance.namelist.return_value = ["dummy_extraido.csv"]
    mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

    # 2. Configurando o Mock do Polars (Simulando a leitura de um chunk "sujo" do governo)
    df_sujo = pl.DataFrame(
        {
            'ï»¿"id"': [1, 2],  # BOM e aspas nojentas que vêm da Câmara
            "nome": ["A", "B"],
        }
    )
    mock_lazyframe = MagicMock()
    # O collect_batches retorna um iterador de DataFrames (chunks)
    mock_lazyframe.collect_batches.return_value = [df_sujo]
    mock_scan_csv.return_value = mock_lazyframe

    # 3. Execução
    ext = DummyBulkExtractor(mock_client)
    await ext.extract(sink_func=mock_sink, unique_keys="id")

    # 4. Asserções de Descompactação
    mock_client.download_file.assert_called_once()
    mock_zip_instance.extract.assert_called_once_with("dummy_extraido.csv", mock.ANY)

    # 5. Asserções de Limpeza e Streaming
    mock_sink.assert_called_once()
    df_limpo, table_name, unique_keys = mock_sink.call_args[0]

    assert table_name == "dummy"
    # A Limpeza Nuclear tem que ter destruído o BOM e as aspas, sobrando só "id"
    assert "id" in df_limpo.columns
    assert 'ï»¿"id"' not in df_limpo.columns

    # Valida se as colunas de auditoria foram injetadas
    assert "captured_at" in df_limpo.columns
    assert "updated_at" in df_limpo.columns


@pytest.mark.asyncio
async def test_votos_bulk_schema_standardization(mock_client):
    """
    CRÍTICO: A Câmara muda os nomes das chaves estrangeiras entre a API e o Bulk.
    Testa se o VotosBulkExtractor normaliza 'idDeputado' para 'deputado_id'
    e o tipa como Int64, garantindo integridade referencial no banco.
    """
    ext = VotosBulkExtractor(mock_client)

    # Criamos um DataFrame com o padrão que vem no CSV do governo
    df_cru = pl.DataFrame(
        {
            "idVotacao": ["A1"],
            "idDeputado": ["12345"],  # Vem como String no CSV
            "voto": ["Sim"],
        }
    )

    # Passamos pelo padronizador interno da classe
    df_padronizado = ext._standardize_schema(df_cru)

    # Asserções rigorosas de schema
    assert "idDeputado" not in df_padronizado.columns
    assert "deputado_id" in df_padronizado.columns
    assert df_padronizado.schema["deputado_id"] == pl.Int64


# --- TESTES DE BLINDAGEM DO TEMPLATE METHOD E REGISTRY ---


def test_base_bulk_build_url_unmapped():
    """Garante que falha rápido se o domínio não existir no registry."""
    ext = UnmappedBulk(None)
    with pytest.raises(ValueError, match="não mapeado no registry"):
        ext._build_url()


def test_base_bulk_build_url_missing_year():
    """Garante que falha rápido se esquecerem o ano em Dumps anuais."""
    ext = MissingYearBulk(None)
    with pytest.raises(ValueError, match="exige o parâmetro 'year'"):
        ext._build_url()


def test_base_bulk_standardize_schema_default():
    """Testa o método abstrato devolvendo o DF intacto."""
    ext = BaseBulkExtractor(None)
    df = pl.DataFrame({"teste": [1, 2]})
    assert ext._standardize_schema(df).equals(df)


@pytest.mark.asyncio
async def test_base_bulk_extract_missing_domain():
    """O dev esqueceu de sobrescrever a classe."""
    ext = EmptyDomainBulk(None)
    with pytest.raises(NotImplementedError, match="domain_name deve ser definido"):
        await ext.extract(sink_func=AsyncMock())


# --- TESTES DE BLINDAGEM DE REDE, SISTEMA DE ARQUIVOS E CORRUPÇÃO ---


@pytest.mark.asyncio
async def test_base_bulk_extract_download_fails():
    """
    O Governo não disponibilizou o Dump (HTTP 404).
    A extração deve abortar silenciosamente e não tentar ler o disco.
    """
    client = AsyncMock()
    client.download_file.return_value = False  # Simulando o 404 do client
    ext = ValidCsvBulk(client)
    mock_sink = AsyncMock()

    await ext.extract(sink_func=mock_sink)

    # O banco de dados nunca deve ser chamado
    mock_sink.assert_not_called()


@pytest.mark.asyncio
async def test_base_bulk_extract_bad_zip_file():
    """
    Risco Crítico Governamental: O arquivo baixado tem a extensão .zip,
    mas o conteúdo é uma página HTML de erro (proxy) ou o ZIP está corrompido.
    """
    client = AsyncMock()
    mock_sink = AsyncMock()

    # Interceptamos o download para escrever um arquivo falso e corrompido no disco
    async def fake_download(url, dest):
        with open(dest, "w") as f:
            f.write("Isto não é um arquivo ZIP válido. É um HTML de erro do NGINX.")
        return True

    client.download_file.side_effect = fake_download
    ext = ValidZipBulk(client)

    # Executamos a extração. O BadZipFile deve ser capturado e o log.error acionado.
    await ext.extract(sink_func=mock_sink, year=2026)

    # O pipeline do Polars e o Sink não devem ter sido acionados
    mock_sink.assert_not_called()


@pytest.mark.asyncio
@patch("ipolitico.extractors.camara.bulk.base_bulk.pl.scan_csv")
async def test_base_bulk_extract_csv_parsing_exception(mock_scan):
    """
    Ocorreu uma falha violenta do Polars (erro de memória, disco, ou parsing irrecuperável).
    A exceção bruta genérica (Exception) deve ser pega para não matar o orquestrador inteiro.
    """
    client = AsyncMock()
    client.download_file.return_value = True  # Sucesso no download falso
    mock_sink = AsyncMock()

    # Simulamos o Polars estourando um erro catastrófico
    mock_scan.side_effect = Exception("Erro catastrófico de disco simulado")

    ext = ValidCsvBulk(client)

    # Ele DEVE capturar a exceção e sair graciosamente, sem propagar o crash
    await ext.extract(sink_func=mock_sink)

    # Obviamente, nada vai para o banco
    mock_sink.assert_not_called()
