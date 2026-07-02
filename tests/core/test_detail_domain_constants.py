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


class TestDomainSpecSourceUrlFormat:
    def test_default_source_url_format_is_none(self):
        """DomainSpec padrao deve ter source_url_format=None."""
        spec = spec_for(DomainType.DEPUTADOS)
        assert spec is not None
        assert spec.source_url_format is None

    def test_domain_spec_can_set_source_url_format(self):
        """DomainSpec deve aceitar source_url_format via parametro."""
        from ipolitico.core.domain_spec import DomainSpec

        spec = DomainSpec(
            domain=DomainType.DEPUTADOS,
            watermark_column=None,
            earliest_iso="1826-04-29",
            depends_on=frozenset(),
            source_url_format="https://dadosabertos.camara.leg.br/api/v2/deputados/{resource_id}",
        )
        assert (
            spec.source_url_format
            == "https://dadosabertos.camara.leg.br/api/v2/deputados/{resource_id}"
        )


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


class TestSourceUrlInSchemas:
    """Contract test: _source_url deve existir em todos os SILVER_SCHEMAS."""

    def test_all_silver_schemas_have_source_url(self):
        """Todo schema em SILVER_SCHEMAS deve conter o campo _source_url."""
        missing = []
        for domain_key, schema in SILVER_SCHEMAS.items():
            if "_source_url" not in schema:
                missing.append(domain_key)
        assert not missing, f"Schemas sem _source_url: {missing}"

    def test_source_url_is_first_field_in_all_schemas(self):
        """_source_url deve ser o primeiro campo em todos os schemas."""
        violations = []
        for domain_key, schema in SILVER_SCHEMAS.items():
            fields = list(schema.keys())
            if not fields or fields[0] != "_source_url":
                violations.append(domain_key)
        assert not violations, f"Schemas onde _source_url nao e o primeiro campo: {violations}"
