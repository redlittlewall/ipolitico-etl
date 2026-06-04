"""Tests for DomainType, EARLIEST_DATE_MAP, DomainSpec, and SILVER_SCHEMA entries."""

import polars as pl
from ipolitico.core.constants import EARLIEST_DATE_MAP, DomainType, EarliestDates
from ipolitico.core.domain_spec import spec_for
from ipolitico.core.schemas import SILVER_SCHEMAS


class TestDomainTypeConstants:
    def test_blocos_detalhe_exists(self):
        """DomainType deve ter BLOCOS_DETALHE."""
        assert hasattr(DomainType, "BLOCOS_DETALHE")
        assert DomainType.BLOCOS_DETALHE.value == "blocos_detalhe"

    def test_proposicoes_detalhe_exists(self):
        """DomainType deve ter PROPOSICOES_DETALHE."""
        assert hasattr(DomainType, "PROPOSICOES_DETALHE")
        assert DomainType.PROPOSICOES_DETALHE.value == "proposicoes_detalhe"


class TestEarliestDateMap:
    def test_blocos_detalhe_mapeado(self):
        """EARLIEST_DATE_MAP deve ter entrada para BLOCOS_DETALHE."""
        assert DomainType.BLOCOS_DETALHE in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.BLOCOS_DETALHE] == EarliestDates.DEPUTADOS

    def test_proposicoes_detalhe_mapeado(self):
        """EARLIEST_DATE_MAP deve ter entrada para PROPOSICOES_DETALHE."""
        assert DomainType.PROPOSICOES_DETALHE in EARLIEST_DATE_MAP
        assert EARLIEST_DATE_MAP[DomainType.PROPOSICOES_DETALHE] == EarliestDates.PROPOSICOES


class TestDomainSpecEntries:
    def test_blocos_detalhe_spec(self):
        """spec_for(BLOCOS_DETALHE) deve retornar DomainSpec com sub_domain e depends_on."""
        spec = spec_for(DomainType.BLOCOS_DETALHE)
        assert spec is not None
        assert spec.domain == DomainType.BLOCOS_DETALHE
        assert spec.sub_domain == "blocos_detalhe"
        assert spec.watermark_column is None
        assert DomainType.BLOCOS in spec.depends_on

    def test_proposicoes_detalhe_spec(self):
        """spec_for(PROPOSICOES_DETALHE) deve retornar DomainSpec com sub_domain e depends_on."""
        spec = spec_for(DomainType.PROPOSICOES_DETALHE)
        assert spec is not None
        assert spec.domain == DomainType.PROPOSICOES_DETALHE
        assert spec.sub_domain == "proposicoes_detalhe"
        assert spec.watermark_column is None
        assert DomainType.PROPOSICOES in spec.depends_on


class TestSilverSchemaEntries:
    def test_blocos_detalhe_schema(self):
        """SILVER_SCHEMAS deve ter entry para blocos_detalhe com campos corretos."""
        schema = SILVER_SCHEMAS.get(DomainType.BLOCOS_DETALHE.value)
        assert schema is not None
        # Schema idêntico ao blocos raiz
        assert schema["id"] == pl.Int64
        assert schema["idLegislatura"] == pl.Int64
        assert schema["nome"] == pl.String
        assert schema["uri"] == pl.String
        assert schema["federacao"] == pl.Boolean

    def test_proposicoes_detalhe_schema(self):
        """SILVER_SCHEMAS deve ter entry para proposicoes_detalhe com campos enriquecidos."""
        schema = SILVER_SCHEMAS.get(DomainType.PROPOSICOES_DETALHE.value)
        assert schema is not None
        # Campos base (listagem)
        assert schema["id"] == pl.Int64
        assert schema["uri"] == pl.String
        assert schema["siglaTipo"] == pl.String
        assert schema["numero"] == pl.Int64
        assert schema["ano"] == pl.Int64
        assert schema["ementa"] == pl.String
        assert schema["dataApresentacao"] == pl.Datetime
        assert schema["uriOrgaoNumerador"] == pl.String
        # Campos extras de detalhe
        assert schema["codTipo"] == pl.Int64
        assert schema["ementaDetalhada"] == pl.String
        assert schema["statusProposicao"] == pl.String
        assert schema["uriAutores"] == pl.String
        assert schema["descricaoTipo"] == pl.String
        assert schema["keywords"] == pl.String
        assert schema["urlInteiroTeor"] == pl.String
