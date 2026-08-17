"""Issue 04 — MonthlyBulkStrategy: 1 job por (ano, mês), pulando lacunas.

O consolidado mensal da folha publica 1 arquivo por (ano, mês). A estratégia
gera 1 job por mês na janela, pulando anos inteiros sem publicação
(2011/2015/2022 — lacunas de cobertura), evitando ~2 anos de 404 inúteis.
"""

from ipolitico.core.constants import DomainType
from ipolitico.core.domain_spec import spec_for
from ipolitico.pipeline.planners.strategies import MonthlyBulkStrategy, strategy_for


def _build(start: str, end: str):
    return MonthlyBulkStrategy().build(
        domain=DomainType.FOLHA_PAGAMENTO,
        spec=spec_for(DomainType.FOLHA_PAGAMENTO),
        start=start,
        end=end,
        current_leg=57,
        anchor_year=2026,
        extraction_plan=None,
        state_store=None,
        lake=None,
    )


class TestMonthlyBulkStrategy:
    def test_um_job_por_ano_mes(self):
        jobs, _ = _build("2026-01-01", "2026-03-31")
        assert jobs == [
            {"year": 2026, "month": 1},
            {"year": 2026, "month": 2},
            {"year": 2026, "month": 3},
        ]

    def test_mapper_retorna_year_e_month(self):
        _, mapper = _build("2026-01-01", "2026-01-31")
        assert mapper({"year": 2026, "month": 1}) == {"year": 2026, "month": 1}

    def test_janela_entre_anos_clipa_meses_da_borda(self):
        jobs, _ = _build("2025-11-01", "2026-02-28")
        assert jobs == [
            {"year": 2025, "month": 11},
            {"year": 2025, "month": 12},
            {"year": 2026, "month": 1},
            {"year": 2026, "month": 2},
        ]

    def test_pula_anos_de_lacuna(self):
        jobs, _ = _build("2014-01-01", "2017-12-31")
        years = {j["year"] for j in jobs}
        assert 2015 not in years  # lacuna: 2015 não publicado
        assert {2014, 2016, 2017} <= years
        assert all(j["month"] in range(1, 13) for j in jobs)

    def test_registrada_no_registry(self):
        assert isinstance(strategy_for(DomainType.FOLHA_PAGAMENTO), MonthlyBulkStrategy)

    def test_participa_de_incremental_nao_estavel(self):
        """Folha muda todo mês → não é estável (não deve ser pulada)."""
        spec = spec_for(DomainType.FOLHA_PAGAMENTO)
        assert spec is not None
        assert spec.stable is False
