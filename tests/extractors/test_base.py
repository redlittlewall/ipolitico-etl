import polars as pl
import pytest

from ipolitico.extractors.base import BaseExtractor


class _ConcreteExtractor(BaseExtractor):
    base_url: str = "https://api.example.com/v2"

    async def extract(self, **kwargs):
        return pl.DataFrame({"x": [1]})


class _FormattedExtractor(BaseExtractor):
    base_url: str = "https://api.example.com/v2"
    source_url_format: str | None = "https://api.example.com/v2/entity/{resource_id}"

    async def extract(self, **kwargs):
        return pl.DataFrame({"x": [1]})


@pytest.mark.asyncio
async def test_base_extractor_extract_returns_dataframe():
    ext = _ConcreteExtractor()
    df = await ext.extract()
    assert df.height == 1


def test_base_extractor_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        BaseExtractor()


# ── _source_url infrastructure tests ──────────────────────────────────────────


def test_build_source_url_with_resource_id():
    """build_source_url deve usar source_url_format quando resource_id é fornecido."""
    ext = _FormattedExtractor()
    url = ext.build_source_url("deputados", resource_id="42")
    assert url == "https://api.example.com/v2/entity/42"


def test_build_source_url_endpoint_only():
    """build_source_url deve concatenar base_url + endpoint quando não há resource_id."""
    ext = _ConcreteExtractor()
    url = ext.build_source_url("deputados")
    assert url == "https://api.example.com/v2/deputados"


def test_build_source_url_with_params():
    """build_source_url deve incluir query params ordenados quando fornecidos."""
    ext = _ConcreteExtractor()
    url = ext.build_source_url(
        "deputados/1/despesas",
        params={"ano": "2024", "mes": "1", "ordem": "ASC"},
    )
    assert url == "https://api.example.com/v2/deputados/1/despesas?ano=2024&mes=1&ordem=ASC"
