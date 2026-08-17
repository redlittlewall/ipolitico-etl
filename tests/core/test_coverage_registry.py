"""Issue 02 — Cobertura temporal: datas reais, lacunas e fallback ausente."""

from ipolitico.core.constants import (
    COVERAGE_GAPS,
    EARLIEST_DATE_MAP,
    DomainType,
    EarliestDates,
)
from ipolitico.core.domain_spec import DomainSpec, spec_for


class TestEarliestDatesReais:
    """Datas reais de disponibilidade não devem cair no fallback 1826-04-29."""

    def test_despesas_desde_2009(self):
        assert EARLIEST_DATE_MAP[DomainType.DESPESAS] == "2009-01-01"

    def test_senadores_desde_1949(self):
        assert EARLIEST_DATE_MAP[DomainType.SENADORES] == "1949-01-01"

    def test_votos_registrado_no_map(self):
        """VOTOS estava fora do map e caía no default silencioso 1826-04-29."""
        assert DomainType.VOTOS in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.VOTOS] == "1991-01-01"

    def test_todo_domaintype_tem_entrada_explicita(self):
        """Nenhum domínio deve depender do fallback silencioso 1826-04-29."""
        missing = [d.value for d in DomainType if d not in EARLIEST_DATE_MAP]
        assert missing == []

    def test_folha_pagamento_earliest_documentado(self):
        """Consolidado da folha da Câmara documentado (issue 02/04)."""
        assert EarliestDates.FOLHA_PAGAMENTO == "2012-01-01"

    def test_remuneracoes_senado_earliest_documentado(self):
        """Remunerações do Senado documentado desde 2013 (issue 08)."""
        assert EarliestDates.REMUNERACOES == "2013-01-01"

    def test_despesas_ceaps_senado_earliest_documentado(self):
        """Despesas de CEAPS do Senado documentado desde 2008 (issue 09)."""
        assert EarliestDates.DESPESAS_CEAPS == "2008-01-01"

    def test_spec_votos_usa_1991(self):
        spec = spec_for(DomainType.VOTOS)
        assert spec is not None
        assert spec.earliest_iso == "1991-01-01"


class TestCoverageGapsRegistry:
    """Notas de lacunas no meio da série registradas por nome de domínio."""

    def test_folha_pagamento_lacunas_2011_2015_2022(self):
        gaps = COVERAGE_GAPS["folha_pagamento"]
        text = " ".join(gaps)
        assert "2011" in text
        assert "2015" in text
        assert "2022" in text

    def test_domain_spec_coverage_gaps_default_vazio(self):
        spec = spec_for(DomainType.DESPESAS)
        assert spec is not None
        assert spec.coverage_gaps == ()

    def test_domain_spec_aceita_coverage_gaps(self):
        spec = DomainSpec(
            domain=DomainType.DESPESAS,
            watermark_column=None,
            earliest_iso="2009-01-01",
            depends_on=frozenset(),
            coverage_gaps=("teste",),
        )
        assert spec.coverage_gaps == ("teste",)
