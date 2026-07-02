"""Testes do SenadoProcessosExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.processos import SenadoProcessosExtractor


@pytest.mark.asyncio
async def test_extract_returns_dataframe():
    """
    extract() chama o endpoint /processo e retorna um DataFrame
    com os campos flat da API.
    """
    client = SenadoClient()
    extractor = SenadoProcessosExtractor(client)

    fake_processos = [
        {
            "id": 1326805,
            "codigoMateria": 603,
            "identificacao": "PDS 16/1984",
            "ementa": "Aprova o texto da Convenção...",
            "autoria": "Câmara dos Deputados",
            "tipoDocumento": "Projeto de Decreto Legislativo",
            "dataApresentacao": "1949-05-31",
            "situacaoAtual": "MATÉRIA COM A RELATORIA",
            "dataSituacaoAtual": "2023-03-23",
            "casaIdentificadora": "SF",
            "tramitando": "Sim",
        }
    ]

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo.json").respond(
            status_code=200, json=fake_processos
        )

        df = await extractor.extract()

        assert df.height == 1
        assert "id" in df.columns
        assert "identificacao" in df.columns


@pytest.mark.asyncio
async def test_extract_empty_list():
    """API retornando lista vazia → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoProcessosExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo.json").respond(
            status_code=200, json=[]
        )

        df = await extractor.extract()

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_non_list_response():
    """API retornando dict (não lista) → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoProcessosExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo.json").respond(
            status_code=200, json={"erro": "inesperado"}
        )

        df = await extractor.extract()

        assert df.is_empty()


# ── PROCESSOS_DETALHE ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_detalhe_extract_entity_ids_returns_dataframe():
    """
    SenadoProcessosDetalheExtractor.extract(entity_ids=[2904181])
    chama /processo/2904181 e retorna DataFrame com dados flat.
    """
    from ipolitico.extractors.senado.api.processos import SenadoProcessosDetalheExtractor

    client = SenadoClient()
    extractor = SenadoProcessosDetalheExtractor(client)

    fake_detail = {
        "id": 2904181,
        "codigoMateria": 236,
        "identificacao": "MSG 31/1991",
        "sigla": "MSG",
        "numero": "31",
        "ano": 1991,
        "casaIdentificadora": "CN",
        "tramitando": "Sim",
        "dataInicioEfetivo": "1991-04-15",
        "situacaoAtual": "AGUARDANDO DESIGNAÇÃO DO RELATOR",
        "dataSituacaoAtual": "2023-02-02",
        "conteudo": {
            "ementa": "Encaminha ao Congresso Nacional, as Contas do Governo Federal...",
        },
    }

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo/2904181.json").respond(
            status_code=200, json=fake_detail
        )

        df = await extractor.extract(entity_ids=[2904181])

        assert df.height == 1
        assert "id" in df.columns
        assert "identificacao" in df.columns


@pytest.mark.asyncio
async def test_detalhe_extract_empty_ids():
    """entity_ids vazio retorna DataFrame vazio."""
    from ipolitico.extractors.senado.api.processos import SenadoProcessosDetalheExtractor

    client = SenadoClient()
    extractor = SenadoProcessosDetalheExtractor(client)

    df = await extractor.extract(entity_ids=[])

    assert df.is_empty()


@pytest.mark.asyncio
async def test_detalhe_extract_multiple_ids():
    """Múltiplos entity_ids produzem múltiplas linhas no DataFrame."""
    from ipolitico.extractors.senado.api.processos import SenadoProcessosDetalheExtractor

    client = SenadoClient()
    extractor = SenadoProcessosDetalheExtractor(client)

    def _fake_processo(i: int) -> dict:
        return {
            "id": i,
            "codigoMateria": i,
            "identificacao": f"PL {i}/2024",
            "sigla": "PL",
            "casaIdentificadora": "SF",
            "tramitando": "Sim",
        }

    with respx.mock:
        for pid in [2904181, 8294609]:
            respx.get(f"https://legis.senado.leg.br/dadosabertos/processo/{pid}.json").respond(
                status_code=200, json=_fake_processo(pid)
            )

        df = await extractor.extract(entity_ids=[2904181, 8294609])

        assert df.height == 2


@pytest.mark.asyncio
async def test_detalhe_extract_404_skipped():
    """ID inexistente (404) é ignorado sem quebrar o batch."""
    from ipolitico.extractors.senado.api.processos import SenadoProcessosDetalheExtractor

    client = SenadoClient()
    extractor = SenadoProcessosDetalheExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo/1.json").respond(
            status_code=200,
            json={"id": 1, "codigoMateria": 1, "identificacao": "Teste"},
        )
        respx.get("https://legis.senado.leg.br/dadosabertos/processo/999.json").respond(
            status_code=404
        )

        df = await extractor.extract(entity_ids=[1, 999])

        assert df.height == 1


# ── PROCESSOS_EMENDAS ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_emendas_extract_returns_dataframe():
    """
    SenadoProcessosEmendasExtractor.extract() chama /processo/emenda
    e retorna DataFrame com os campos flat.
    """
    from ipolitico.extractors.senado.api.processos import SenadoProcessosEmendasExtractor

    client = SenadoClient()
    extractor = SenadoProcessosEmendasExtractor(client)

    fake_emendas = [
        {
            "id": 9540193,
            "idProcesso": 8294609,
            "identificacao": "EMENDA 2 / CSP - PL 2253/2022",
            "autoria": "Senador Sergio Moro (UNIÃO/PR)",
            "casa": "SF",
            "dataApresentacao": "2024-02-01",
            "descricaoDocumentoEmenda": "Emenda ao PL 2253/2022 - CSP",
            "tipo": "EMENDA_PARCIAL",
            "numero": "2",
            "nomeColegiado": "Comissão de Segurança Pública",
            "siglaColegiado": "CSP",
            "urlDocumentoEmenda": "http://...",
        }
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/processo/emenda.json",
            params={"dataInicio": "2024-01-01", "dataFim": "2024-01-31"},
        ).respond(status_code=200, json=fake_emendas)

        df = await extractor.extract(start_date="2024-01-01", end_date="2024-01-31")

        assert df.height == 1
        assert "id" in df.columns
        assert "autoria" in df.columns


@pytest.mark.asyncio
async def test_emendas_extract_empty_params():
    """Sem parâmetros de data, chama o endpoint sem query string."""
    from ipolitico.extractors.senado.api.processos import SenadoProcessosEmendasExtractor

    client = SenadoClient()
    extractor = SenadoProcessosEmendasExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo/emenda.json").respond(
            status_code=200, json=[]
        )

        df = await extractor.extract()

        assert df.is_empty()


# ── PROCESSOS_DOCUMENTOS ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_documentos_extract_returns_dataframe():
    """
    SenadoProcessosDocumentosExtractor.extract() chama /processo/documento
    e retorna DataFrame com os campos flat.
    """
    from ipolitico.extractors.senado.api.processos import SenadoProcessosDocumentosExtractor

    client = SenadoClient()
    extractor = SenadoProcessosDocumentosExtractor(client)

    fake_docs = [
        {
            "id": 9538518,
            "identificacao": "Termo de Adesão - SF245968923787",
            "autoria": "Senador Jorge Seif (PL/SC)",
            "casaEnteRecebedor": "SF",
            "casaRecebedora": "CN",
            "dataDocumento": "2023-10-31",
            "dataRecebimento": "2024-01-08",
            "descricao": "Termo de Adesão...",
            "descricaoTipo": "Termo de Adesão",
            "siglaTipo": "TERMO_ADESAO",
            "siglaEnteRecebedor": "NPFG",
            "nomeEnteRecebedor": "Núcleo de premiações",
            "urlDocumento": "http://...",
        }
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/processo/documento.json",
            params={"dataInicio": "2024-01-01", "dataFim": "2024-01-31"},
        ).respond(status_code=200, json=fake_docs)

        df = await extractor.extract(start_date="2024-01-01", end_date="2024-01-31")

        assert df.height == 1
        assert "id" in df.columns
        assert "descricaoTipo" in df.columns


@pytest.mark.asyncio
async def test_documentos_extract_empty():
    """API retornando lista vazia → DataFrame vazio."""
    from ipolitico.extractors.senado.api.processos import SenadoProcessosDocumentosExtractor

    client = SenadoClient()
    extractor = SenadoProcessosDocumentosExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo/documento.json").respond(
            status_code=200, json=[]
        )

        df = await extractor.extract()

        assert df.is_empty()
