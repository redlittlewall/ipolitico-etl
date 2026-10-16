"""Ticket 04 — PortalAnnualBulkStrategy: 1 job por ano com mapper {"year"}.

Os dumps anuais do Portal da Transparência (``/download-de-dados/{módulo}/{YYYY}``
— pep, viagens) têm o mesmo grid do ``AnnualWindowStrategy``, mas o mapper
devolve ``{"year": y}`` em vez de ``{"ano": y}``: o
``PortalTransparenciaBulkExtractor.extract(year, month)`` espera ``year`` para
montar a URL por convenção de segmento. ``{"ano"}`` alimentaria endpoints de API
(ex: ``/api-de-dados/emendas?ano=...``) — não o extrator bulk.
"""

from ipolitico.core.constants import DomainType
from ipolitico.core.domain_spec import spec_for
from ipolitico.pipeline.planners.strategies import (
    PortalAnnualBulkStrategy,
    strategy_for,
)


def _build(start: str, end: str):
    return PortalAnnualBulkStrategy().build(
        domain=DomainType.CG_PEP,
        spec=spec_for(DomainType.CG_PEP),
        start=start,
        end=end,
        current_leg=57,
        anchor_year=2026,
        extraction_plan=None,
        state_store=None,
        lake=None,
    )


class TestPortalAnnualBulkStrategy:
    def test_um_job_por_ano(self):
        jobs, _ = _build("2024-01-01", "2026-12-31")
        assert jobs == [
            {"year": 2024},
            {"year": 2025},
            {"year": 2026},
        ]

    def test_mapper_devolve_year(self):
        """Contraste com AnnualWindowStrategy ({"ano"}): bulk espera {"year"}."""
        _, mapper = _build("2026-01-01", "2026-12-31")
        assert mapper({"year": 2026}) == {"year": 2026}

    def test_janela_fracionada_gera_um_job_por_ano_civil(self):
        """A janela recorta por ano civil; meses são irrelevantes no dump anual."""
        jobs, _ = _build("2025-06-01", "2026-05-31")
        assert jobs == [{"year": 2025}, {"year": 2026}]

    def test_registrada_para_cg_pep_e_cg_viagens(self):
        for domain in (DomainType.CG_PEP, DomainType.CG_VIAGENS):
            assert isinstance(strategy_for(domain), PortalAnnualBulkStrategy)
