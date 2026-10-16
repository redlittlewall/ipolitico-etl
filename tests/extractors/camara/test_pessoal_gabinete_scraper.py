"""Testes unitários para o extrator e parser HTML de pessoal de gabinete da Câmara."""

from pathlib import Path

import httpx
import polars as pl
import pytest
import respx

from ipolitico.extractors.camara.scraper.pessoal_gabinete import (
    CamaraPessoalGabineteExtractor,
    parse_pessoal_gabinete_html,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


@pytest.fixture
def sample_html() -> str:
    """Carrega o fixture de HTML de pessoal de gabinete."""
    fixture_path = FIXTURES_DIR / "camara_pessoal_gabinete.html"
    return fixture_path.read_text(encoding="utf-8")


# =============================================================================
# 1. Testes isolados do parser HTML
# =============================================================================


def test_parse_pessoal_gabinete_html_success(sample_html: str):
    """Garante extração correta de linhas e colunas a partir do HTML com tabela preenchida."""
    deputado_id = 204521
    source_url = "https://www.camara.leg.br/deputados/204521/pessoal-gabinete"
    captured_at = "2026-10-15T19:00:00+00:00"

    df = parse_pessoal_gabinete_html(
        html=sample_html,
        deputado_id=deputado_id,
        source_url=source_url,
        captured_at=captured_at,
    )

    assert isinstance(df, pl.DataFrame)
    assert df.height == 4

    expected_cols = {
        "deputado_id",
        "nome_assessor",
        "cargo",
        "grupo_funcional",
        "data_exercicio",
        "captured_at",
        "_source_url",
    }
    assert set(df.columns) == expected_cols

    assert (df["deputado_id"] == deputado_id).all()
    assert (df["_source_url"] == source_url).all()
    assert (df["captured_at"] == captured_at).all()

    nomes = df["nome_assessor"].to_list()
    # Parser extrai o texto contido na célula; o trim fino ou uppercase é validado
    assert any("ANA CLARA" in n for n in nomes)
    assert any("carlos eduardo" in n.lower() for n in nomes)
    assert any("MARIA" in n for n in nomes)
    assert any("JOÃO BATISTA" in n for n in nomes)

    cargos = df["cargo"].to_list()
    assert any("SP-01" in c for c in cargos)
    assert any("SP-25" in c for c in cargos)


def test_parse_pessoal_gabinete_html_empty_table():
    """Garante retorno de DataFrame vazio quando a tabela não possui linhas no tbody."""
    html = """
    <html>
    <body>
        <table>
            <thead>
                <tr>
                    <th>Nome</th>
                    <th>Cargo</th>
                    <th>Grupo Funcional</th>
                    <th>Início do Exercício</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    </body>
    </html>
    """
    df = parse_pessoal_gabinete_html(
        html=html,
        deputado_id=123,
        source_url="https://www.camara.leg.br/deputados/123/pessoal-gabinete",
    )
    assert isinstance(df, pl.DataFrame)
    assert df.is_empty()


def test_parse_pessoal_gabinete_html_no_table():
    """Garante retorno de DataFrame vazio quando não há tabela na página (gabinete sem dados)."""
    html = """
    <html>
    <body>
        <div class="alerta">Nenhum servidor comissionado encontrado para este gabinete.</div>
    </body>
    </html>
    """
    df = parse_pessoal_gabinete_html(
        html=html,
        deputado_id=123,
        source_url="https://www.camara.leg.br/deputados/123/pessoal-gabinete",
    )
    assert isinstance(df, pl.DataFrame)
    assert df.is_empty()


def test_parse_pessoal_gabinete_html_malformed_html():
    """Garante resiliência a HTML quebrado ou malformado."""
    html = "<div><p>Texto aleatório sem fechamento de tags <table><tr><td>Incompleto"
    df = parse_pessoal_gabinete_html(html=html, deputado_id=123)
    assert isinstance(df, pl.DataFrame)
    assert df.is_empty()


def test_parse_pessoal_gabinete_html_varied_headers():
    """Garante reconhecimento de variações nos títulos das colunas."""
    html = """
    <table>
        <thead>
            <tr>
                <th>Servidor</th>
                <th>Função / Cargo</th>
                <th>Grupo</th>
                <th>Exercício</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>JOSÉ DA SILVA</td>
                <td>SECRETÁRIO PARLAMENTAR SP-02</td>
                <td>SECRETARIA PARLAMENTAR</td>
                <td>10/01/2023</td>
            </tr>
        </tbody>
    </table>
    """
    df = parse_pessoal_gabinete_html(html=html, deputado_id=999)
    assert df.height == 1
    assert "JOSÉ DA SILVA" in df["nome_assessor"][0]
    assert "SP-02" in df["cargo"][0]


# =============================================================================
# 2. Testes assíncronos do Extrator (CamaraPessoalGabineteExtractor)
# =============================================================================


@pytest.mark.asyncio
async def test_extractor_extract_success(sample_html: str):
    """Extrator busca URL correta via HTTP GET e extrai registros."""
    deputado_id = 204521
    target_url = f"https://www.camara.leg.br/deputados/{deputado_id}/pessoal-gabinete"

    with respx.mock:
        respx.get(target_url).respond(status_code=200, text=sample_html)

        extractor = CamaraPessoalGabineteExtractor()
        df = await extractor.extract(deputado_id=deputado_id)

    assert isinstance(df, pl.DataFrame)
    assert df.height == 4
    assert df["_source_url"][0] == target_url
    assert df["deputado_id"][0] == deputado_id


@pytest.mark.asyncio
async def test_extractor_extract_no_deputado_id():
    """Extrator sem deputado_id deve retornar DataFrame vazio imediatamente."""
    extractor = CamaraPessoalGabineteExtractor()
    df = await extractor.extract()
    assert isinstance(df, pl.DataFrame)
    assert df.is_empty()


@pytest.mark.asyncio
async def test_extractor_extract_404_returns_empty_df():
    """Página 404 (deputado sem gabinete/licenciado) retorna DataFrame vazio sem quebrar o fluxo."""
    deputado_id = 999999
    target_url = f"https://www.camara.leg.br/deputados/{deputado_id}/pessoal-gabinete"

    with respx.mock:
        respx.get(target_url).respond(status_code=404)

        extractor = CamaraPessoalGabineteExtractor()
        df = await extractor.extract(deputado_id=deputado_id)

    assert isinstance(df, pl.DataFrame)
    assert df.is_empty()


@pytest.mark.asyncio
async def test_extractor_retry_on_transient_error(sample_html: str):
    """Extrator retenta requisição com falha transitória 500 antes de obter sucesso via tenacity."""
    deputado_id = 204521
    target_url = f"https://www.camara.leg.br/deputados/{deputado_id}/pessoal-gabinete"

    with respx.mock:
        route = respx.get(target_url)
        route.side_effect = [
            httpx.Response(500, text="Erro interno do servidor"),
            httpx.Response(200, text=sample_html),
        ]

        extractor = CamaraPessoalGabineteExtractor()
        df = await extractor.extract(deputado_id=deputado_id)

    assert route.call_count == 2
    assert df.height == 4
