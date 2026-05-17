from ipolitico.core.constants import DomainType, LoadStrategy
from ipolitico.tools.ingestion_estimate import (
    _months_inclusive,
    estimate_camara_ingestion,
    estimate_domain,
)


def test_months_inclusive_march_only():
    assert _months_inclusive("2024-03-01", "2024-03-31") == 1


def test_months_inclusive_full_year():
    assert _months_inclusive("2024-01-01", "2024-12-31") == 12


def test_despesas_bulk_zero_http():
    est = estimate_domain(
        DomainType.DESPESAS,
        "2009-01-01",
        "2012-12-31",
        LoadStrategy.FULL_LOAD,
    )
    assert est.http_requests == 0
    assert est.bulk_downloads == 4


def test_votos_one_request_per_votacao():
    est = estimate_domain(
        DomainType.VOTOS,
        "2024-03-01",
        "2024-03-31",
        LoadStrategy.INCREMENTAL,
        votacoes_per_month=100,
    )
    assert est.http_requests == 100


def test_estimate_camara_wall_time_positive():
    est = estimate_camara_ingestion(
        [DomainType.PROFISSÕES],
        "2024-01-01",
        "2024-01-31",
        LoadStrategy.INCREMENTAL,
        deputy_count=10,
        http_concurrency=2,
        latency_sec=0.5,
    )
    assert est.total_http_requests == 10
    assert est.estimated_api_wall_seconds == 2.5
