from ipolitico.core.constants import DomainType, LoadStrategy
from ipolitico.pipeline.window_resolver import WindowResolver


class _MemStore:
    def __init__(self, wm=None):
        self._wm = wm

    def get_watermark(self, table_name: str, col: str):
        return self._wm


def test_window_resolver_full_load_from_earliest():
    wr = WindowResolver(_MemStore())
    start, end = wr.resolve(DomainType.DESPESAS, LoadStrategy.FULL_LOAD, None, "2020-01-01")
    assert start == "2009-01-01"
    assert end == "2020-01-01"


def test_window_resolver_incremental_watermark():
    wr = WindowResolver(_MemStore("2019-06-01T00:00:00"))
    start, end = wr.resolve(DomainType.DESPESAS, LoadStrategy.INCREMENTAL, None, "2021-01-01")
    assert start.startswith("2019-06")
    assert end == "2021-01-01"
