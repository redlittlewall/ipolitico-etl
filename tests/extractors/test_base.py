import polars as pl
import pytest

from ipolitico.extractors.base import BaseExtractor


class _ConcreteExtractor(BaseExtractor):
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
