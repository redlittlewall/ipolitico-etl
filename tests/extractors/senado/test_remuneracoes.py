"""Testes do SenadoRemuneracoesExtractor — comportamento público (issue 08).

Prior art: ``tests/extractors/senado/test_servidores.py`` — client mockado via
``respx`` sobre a URL real da API adm-dadosabertos.
"""

import pytest
import respx

from ipolitico.core.config import SENADO_ADM_API_BASE_URL
from ipolitico.core.senado_adm_client import SenadoAdmClient
from ipolitico.extractors.senado.api.remuneracoes import SenadoRemuneracoesExtractor

_MONTH_URL = f"{SENADO_ADM_API_BASE_URL}/servidores/remuneracoes/2026/7"
_CURRENT_MONTH_URL = f"{SENADO_ADM_API_BASE_URL}/servidores/remuneracoes/2026/8"


def _raw_row(
    sequencial: int = 2341271,
    nome: str = "AILTON OLIVEIRA DE ALMEIDA",
    tipo_folha: str = "Normal",
) -> dict:
    """Monta uma linha bruta de remuneração como a API devolve (20 campos).

    Args:
        sequencial: Sequencial do servidor.
        nome: Nome do servidor.
        tipo_folha: ``Normal`` ou ``Suplementar`` (folha suplementar é dado real).

    Returns:
        Dict com os 20 campos brutos (valores monetários em string BR).
    """
    return {
        "abono_permanencia": "0,00",
        "ano": 2026,
        "auxilios": "0,00",
        "diarias": "0,00",
        "faltas": "0,00",
        "funcao_comissionada": "9.876,54",
        "gratificacao_natalina": "0,00",
        "horas_extras": "0,00",
        "imposto_renda": "2.345,67",
        "mes": 7,
        "nome": nome,
        "outras_eventuais": "0,00",
        "previdencia": "-9.463,65",
        "remuneracao_basica": "1.234,56",
        "remuneracao_liquida": "-9.463,65",
        "reversao_teto_constitucional": "0,00",
        "sequencial": sequencial,
        "tipo_folha": tipo_folha,
        "vantagens_indenizatorias": "0,00",
        "vantagens_pessoais": "0,00",
    }


class TestSenadoRemuneracoesExtractor:
    """Extrator mensal — 1 chamada por (ano, mês), lista top-level."""

    @pytest.mark.asyncio
    async def test_extract_chama_endpoint_ano_mes(self):
        """
        ``extract(year, month)`` faz UMA chamada a
        ``/servidores/remuneracoes/2026/7`` e devolve DataFrame com os 20 campos
        brutos (valores monetários ainda em string BR).
        """
        client = SenadoAdmClient()
        extractor = SenadoRemuneracoesExtractor(client)

        with respx.mock:
            route = respx.get(_MONTH_URL).respond(200, json=[_raw_row()])
            df = await extractor.extract(year=2026, month=7)

        assert route.call_count == 1  # sem loop de páginas
        assert df.height == 1
        assert "sequencial" in df.columns
        assert "nome" in df.columns
        assert "tipo_folha" in df.columns
        assert "remuneracao_basica" in df.columns  # string BR preservada no bruto
        assert df["remuneracao_basica"][0] == "1.234,56"

    @pytest.mark.asyncio
    async def test_extract_source_url_aponta_para_ano_mes(self):
        """
        ``_source_url`` = URL da API com ano/mês (replayável até o arquivo
        mensal). Primeira coluna.
        """
        client = SenadoAdmClient()
        extractor = SenadoRemuneracoesExtractor(client)

        with respx.mock:
            respx.get(_MONTH_URL).respond(200, json=[_raw_row()])
            df = await extractor.extract(year=2026, month=7)

        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url == _MONTH_URL

    @pytest.mark.asyncio
    async def test_extract_404_retorna_dataframe_vazio(self):
        """
        Falso 404 (mês anterior ao início da série, ex: 2012-12) → DataFrame
        vazio (o client já devolve ``[]``; 404 é ausência, não exceção).
        """
        client = SenadoAdmClient()
        extractor = SenadoRemuneracoesExtractor(client)

        with respx.mock:
            respx.get(_MONTH_URL).respond(404)
            df = await extractor.extract(year=2026, month=7)

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_mes_corrente_nao_publicado_lista_vazia(self):
        """
        Mês corrente ainda não publicado = HTTP 200 com body ``[\n\n]`` (não 404)
        → DataFrame vazio, sem ``_source_url``. Não confundir com 404.
        """
        client = SenadoAdmClient()
        extractor = SenadoRemuneracoesExtractor(client)

        with respx.mock:
            respx.get(_CURRENT_MONTH_URL).respond(200, content=b"[\n\n]")
            df = await extractor.extract(year=2026, month=8)

        assert df.is_empty()
        assert "_source_url" not in df.columns

    @pytest.mark.asyncio
    async def test_extract_requer_ano_e_mes(self):
        """Ano/mês ausentes → ValueError (domínio mensal exige os dois)."""
        client = SenadoAdmClient()
        extractor = SenadoRemuneracoesExtractor(client)

        with pytest.raises(ValueError):
            await extractor.extract(year=2026)
        with pytest.raises(ValueError):
            await extractor.extract(month=7)
