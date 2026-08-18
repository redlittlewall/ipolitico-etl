"""Testes do SenadoDespesasCeapsExtractor — comportamento público (issue 09).

Prior art: ``tests/extractors/senado/test_remuneracoes.py`` — client mockado
via ``respx`` sobre a URL real da API adm-dadosabertos.
"""

import pytest
import respx

from ipolitico.core.config import SENADO_ADM_API_BASE_URL
from ipolitico.core.senado_adm_client import SenadoAdmClient
from ipolitico.extractors.senado.api.despesas_ceaps import SenadoDespesasCeapsExtractor

_YEAR_URL = f"{SENADO_ADM_API_BASE_URL}/senadores/despesas_ceaps/2025"


def _raw_row(
    _id: int = 2270752,
    ano: int = 2025,
    mes: int = 9,
    cod_senador: int = 475,
    valor_reembolsado: float | str = 211.55,
) -> dict:
    """Monta uma linha bruta de despesa CEAP como a API devolve (13 campos).

    Args:
        _id: Identificador da despesa.
        ano: Ano da despesa.
        mes: Mês da despesa (granularidade efetiva, payload é anual).
        cod_senador: Chave de join com o roster (``codigoParlamentar``).
        valor_reembolsado: Valor em número (API real) ou string BR
            (formato documentado no survey — o transformer lida com ambos).

    Returns:
        Dict com os 13 campos brutos do payload CEAP.
    """
    return {
        "id": _id,
        "tipoDocumento": "Nota Fiscal Eletrônica",
        "ano": ano,
        "mes": mes,
        "codSenador": cod_senador,
        "nomeSenador": "CONFÚCIO MOURA",
        "tipoDespesa": "Locomoção, hospedagem, alimentação, combustíveis e lubrificantes",
        "cpfCnpj": "16.805.309/0001-99",
        "fornecedor": "AUTO POSTO DO LAGO LTDA",
        "documento": "000042973",
        "data": "2025-09-26",
        "detalhamento": "Despesa com combustíveis",
        "valorReembolsado": valor_reembolsado,
    }


class TestSenadoDespesasCeapsExtractor:
    """Extrator anual — 1 chamada por ano, lista top-level (mesmo shape de servidores/*)."""

    @pytest.mark.asyncio
    async def test_extract_chama_endpoint_ano(self):
        """
        ``extract(ano)`` faz UMA chamada a ``/senadores/despesas_ceaps/2025`` e
        devolve DataFrame com os 13 campos brutos.
        """
        client = SenadoAdmClient()
        extractor = SenadoDespesasCeapsExtractor(client)

        with respx.mock:
            route = respx.get(_YEAR_URL).respond(200, json=[_raw_row()])
            df = await extractor.extract(ano=2025)

        assert route.call_count == 1  # sem loop de páginas
        assert df.height == 1
        assert "id" in df.columns
        assert "codSenador" in df.columns
        assert "nomeSenador" in df.columns
        assert "valorReembolsado" in df.columns
        assert "mes" in df.columns  # granularidade mensal preservada no payload anual

    @pytest.mark.asyncio
    async def test_extract_source_url_aponta_para_ano(self):
        """
        ``_source_url`` = URL da API com o ano (replayável). Primeira coluna.
        """
        client = SenadoAdmClient()
        extractor = SenadoDespesasCeapsExtractor(client)

        with respx.mock:
            respx.get(_YEAR_URL).respond(200, json=[_raw_row()])
            df = await extractor.extract(ano=2025)

        assert df.columns[0] == "_source_url"
        assert df["_source_url"][0] == _YEAR_URL

    @pytest.mark.asyncio
    async def test_extract_404_retorna_dataframe_vazio(self):
        """
        Falso 404 (ano anterior ao início da série, ex: 2007) → DataFrame vazio
        (o client já devolve ``[]``; 404 é ausência, não exceção).
        """
        client = SenadoAdmClient()
        extractor = SenadoDespesasCeapsExtractor(client)

        with respx.mock:
            respx.get(f"{SENADO_ADM_API_BASE_URL}/senadores/despesas_ceaps/2007").respond(404)
            df = await extractor.extract(ano=2007)

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_lista_vazia_retorna_dataframe_vazio(self):
        """
        HTTP 200 com lista vazia (ano sem despesas registradas) → DataFrame
        vazio, sem ``_source_url``. Ausência, não exceção.
        """
        client = SenadoAdmClient()
        extractor = SenadoDespesasCeapsExtractor(client)

        with respx.mock:
            respx.get(_YEAR_URL).respond(200, content=b"[\n\n]")
            df = await extractor.extract(ano=2025)

        assert df.is_empty()
        assert "_source_url" not in df.columns

    @pytest.mark.asyncio
    async def test_extract_requer_ano(self):
        """Ano ausente → ValueError (domínio anual exige ``ano``)."""
        client = SenadoAdmClient()
        extractor = SenadoDespesasCeapsExtractor(client)

        with pytest.raises(ValueError):
            await extractor.extract()
