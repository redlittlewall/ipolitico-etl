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


def test_window_resolver_full_load_votos_desde_1991():
    """Issue 02: VOTOS não pode cair no default 1826-04-29."""
    wr = WindowResolver(_MemStore())
    start, end = wr.resolve(DomainType.VOTOS, LoadStrategy.FULL_LOAD, None, "2020-01-01")
    assert start == "1991-01-01"
    assert end == "2020-01-01"


def test_window_resolver_friendly_log_quando_clamped(caplog):
    """Issue 02: log amigável quando o piso dominial eleva a janela."""
    import logging

    wr = WindowResolver(_MemStore())
    with caplog.at_level(logging.INFO, logger="ipolitico.pipeline.window_resolver"):
        start, end = wr.resolve(
            DomainType.DESPESAS, LoadStrategy.INCREMENTAL, "1800-01-01", "2020-01-01"
        )
    assert start == "2009-01-01"
    assert end == "2020-01-01"
    assert (
        "Extraindo despesas — filtro de 1800-01-01, "
        "iniciando em 2009-01-01 por ser a janela temporal disponível" in caplog.text
    )
