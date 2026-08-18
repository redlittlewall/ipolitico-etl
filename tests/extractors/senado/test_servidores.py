"""Testes do SenadoServidoresExtractor — comportamento público (issue 07).

Prior art: ``tests/extractors/senado/test_senadores.py`` — client mockado via
``respx`` sobre a URL real da API adm-dadosabertos.
"""

import pytest
import respx

from ipolitico.core.config import SENADO_ADM_API_BASE_URL
from ipolitico.core.senado_adm_client import SenadoAdmClient
from ipolitico.extractors.senado.api.servidores import SenadoServidoresExtractor

_ROSTER_URL = f"{SENADO_ADM_API_BASE_URL}/servidores/servidores"


def _raw_servidor(
    sequencial: int = 3008398,
    nome: str = "AARÃO PRADO BAYMA",
    lotacao: dict | None = None,
    categoria: dict | None = None,
    cedido: dict | None = None,
) -> dict:
    """Monta uma linha bruta do roster como a API devolve (12 campos).

    Args:
        sequencial: Sequencial do servidor (chave de dedup da Silver).
        nome: Nome do servidor.
        lotacao: Objeto lotacao ou None (testa ausência do aninhado).
        categoria: Objeto categoria ou None.
        cedido: Objeto cedido ou None (servidor não cedido).

    Returns:
        Dict com os 12 campos brutos, aninhamentos preservados.
    """
    return {
        "ano_admissao": "2011",
        "cargo": "Secretário Parlamentar",
        "categoria": categoria or {"codigo": "CARGO EM COMISSÃO", "nome": "Cargo em comissão"},
        "cedido": cedido,
        "especialidade": None,
        "funcao": "Assessoria",
        "lotacao": lotacao
        or {
            "sigla": "E1JVIA",
            "nome": "Escritório de Apoio 1 do Senador Jorge Viana",
        },
        "nome": nome,
        "padrao": None,
        "sequencial": sequencial,
        "situacao": "DESLIGADO",
        "vinculo": "COMISSIONADO",
    }


class TestSenadoServidoresExtractor:
    """Extrator do roster — 1 chamada, sem paginação, lista top-level."""

    @pytest.mark.asyncio
    async def test_extract_chama_colecao_e_retorna_dataframe(self):
        """
        ``extract()`` faz UMA chamada a ``/servidores/servidores`` (sem paginação)
        e devolve DataFrame com os 12 campos brutos, aninhamentos preservados.
        """
        client = SenadoAdmClient()
        extractor = SenadoServidoresExtractor(client)
        payload = [_raw_servidor(), _raw_servidor(sequencial=3008399, nome="BELTRANO")]

        with respx.mock:
            route = respx.get(_ROSTER_URL).respond(200, json=payload)
            df = await extractor.extract()

        assert route.call_count == 1  # sem loop de páginas
        assert df.height == 2
        assert "sequencial" in df.columns
        assert "nome" in df.columns
        # Aninhamentos preservados no DataFrame bruto (transformer desaninha)
        assert "lotacao" in df.columns
        assert "categoria" in df.columns
        assert "cedido" in df.columns

    @pytest.mark.asyncio
    async def test_extract_source_url_aponta_para_a_colecao(self):
        """
        ``_source_url`` = URL da coleção (sem ``pagina`` — a API ignora o
        parâmetro). Primeira coluna, replayável até o roster.
        """
        client = SenadoAdmClient()
        extractor = SenadoServidoresExtractor(client)

        with respx.mock:
            respx.get(_ROSTER_URL).respond(200, json=[_raw_servidor()])
            df = await extractor.extract()

        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url == _ROSTER_URL
        assert "pagina" not in url

    @pytest.mark.asyncio
    async def test_extract_404_retorna_dataframe_vazio(self):
        """Falso 404 (recurso sem dados) → DataFrame vazio (client devolve [])."""
        client = SenadoAdmClient()
        extractor = SenadoServidoresExtractor(client)

        with respx.mock:
            respx.get(_ROSTER_URL).respond(404)
            df = await extractor.extract()

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_lista_vazia_retorna_dataframe_vazio(self):
        """API responde 200 com lista vazia → DataFrame vazio, sem _source_url."""
        client = SenadoAdmClient()
        extractor = SenadoServidoresExtractor(client)

        with respx.mock:
            respx.get(_ROSTER_URL).respond(200, json=[])
            df = await extractor.extract()

        assert df.is_empty()
