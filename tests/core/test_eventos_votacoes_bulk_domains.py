"""Testes para os novos domínios bulk-only:
eventosPresencaDeputados, eventosRequerimentos,
votacoesObjetos, votacoesProposicoes."""

import polars as pl

from ipolitico.core.constants import DomainType, LoadStrategy
from ipolitico.core.domain_spec import DOMAIN_SPECS
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY
from ipolitico.pipeline.source_router import SourceRouter


class TestDomainType:
    def test_eventos_presenca_deputados_exists(self):
        assert DomainType.EVENTOS_PRESENCA_DEPUTADOS.value == "eventos_presenca_deputados"

    def test_eventos_requerimentos_exists(self):
        assert DomainType.EVENTOS_REQUERIMENTOS.value == "eventos_requerimentos"

    def test_votacoes_objetos_exists(self):
        assert DomainType.VOTACOES_OBJETOS.value == "votacoes_objetos"

    def test_votacoes_proposicoes_exists(self):
        assert DomainType.VOTACOES_PROPOSICOES.value == "votacoes_proposicoes"


class TestSchemas:
    """SILVER_SCHEMAS para os 4 novos domínios."""

    def test_eventos_presenca_deputados_schema(self):
        schema = SILVER_SCHEMAS.get(DomainType.EVENTOS_PRESENCA_DEPUTADOS.value)
        assert schema is not None
        assert "idEvento" in schema and "idDeputado" in schema
        assert schema["idEvento"] == pl.Int64
        assert schema["idDeputado"] == pl.Int64
        assert schema["dataHoraInicio"] == pl.String

    def test_eventos_requerimentos_schema(self):
        schema = SILVER_SCHEMAS.get(DomainType.EVENTOS_REQUERIMENTOS.value)
        assert schema is not None
        assert "idEvento" in schema
        assert schema["idEvento"] == pl.Int64

    def test_votacoes_objetos_schema(self):
        schema = SILVER_SCHEMAS.get(DomainType.VOTACOES_OBJETOS.value)
        assert schema is not None
        assert "idVotacao" in schema and "proposicao_id" in schema
        assert schema["idVotacao"] == pl.String
        assert schema["proposicao_id"] == pl.Int64

    def test_votacoes_proposicoes_schema(self):
        schema = SILVER_SCHEMAS.get(DomainType.VOTACOES_PROPOSICOES.value)
        assert schema is not None
        assert "idVotacao" in schema and "proposicao_id" in schema
        assert schema["idVotacao"] == pl.String
        assert schema["proposicao_id"] == pl.Int64


class TestBulkRegistry:
    """BULK_REGISTRY entries para os 4 novos domínios."""

    def test_eventos_presenca_deputados_registry(self):
        entry = BULK_REGISTRY.get("eventos_presenca_deputados")
        assert entry is not None
        assert entry["bulk_granularity"] == "year"
        assert entry["requires_year"] is True
        assert "eventosPresencaDeputados" in entry["url_template"]
        assert entry["bulk_only"] is True

    def test_eventos_requerimentos_registry(self):
        entry = BULK_REGISTRY.get("eventos_requerimentos")
        assert entry is not None
        assert entry["bulk_granularity"] == "year"
        assert entry["requires_year"] is True
        assert "eventosRequerimentos" in entry["url_template"]
        assert entry["bulk_only"] is True

    def test_votacoes_objetos_registry(self):
        entry = BULK_REGISTRY.get("votacoes_objetos")
        assert entry is not None
        assert entry["bulk_granularity"] == "year"
        assert entry["requires_year"] is True
        assert "votacoesObjetos" in entry["url_template"]
        assert entry["bulk_only"] is True

    def test_votacoes_proposicoes_registry(self):
        entry = BULK_REGISTRY.get("votacoes_proposicoes")
        assert entry is not None
        assert entry["bulk_granularity"] == "year"
        assert entry["requires_year"] is True
        assert "votacoesProposicoes" in entry["url_template"]
        assert entry["bulk_only"] is True


DOMAIN_KEYS = {
    DomainType.EVENTOS_PRESENCA_DEPUTADOS: ("idEvento", "idDeputado"),
    DomainType.EVENTOS_REQUERIMENTOS: ("idEvento", "tituloRequerimento", "uriRequerimento"),
    DomainType.VOTACOES_OBJETOS: ("idVotacao", "proposicao_id"),
    DomainType.VOTACOES_PROPOSICOES: ("idVotacao", "proposicao_id"),
}


class TestDomainSpecs:
    """DomainSpec entries para os 4 novos domínios."""

    def test_eventos_presenca_deputados_spec(self):
        spec = DOMAIN_SPECS.get(DomainType.EVENTOS_PRESENCA_DEPUTADOS)
        assert spec is not None
        assert spec.unique_keys == DOMAIN_KEYS[DomainType.EVENTOS_PRESENCA_DEPUTADOS]

    def test_eventos_requerimentos_spec(self):
        spec = DOMAIN_SPECS.get(DomainType.EVENTOS_REQUERIMENTOS)
        assert spec is not None
        assert spec.unique_keys == DOMAIN_KEYS[DomainType.EVENTOS_REQUERIMENTOS]

    def test_votacoes_objetos_spec(self):
        spec = DOMAIN_SPECS.get(DomainType.VOTACOES_OBJETOS)
        assert spec is not None
        assert spec.unique_keys == DOMAIN_KEYS[DomainType.VOTACOES_OBJETOS]

    def test_votacoes_proposicoes_spec(self):
        spec = DOMAIN_SPECS.get(DomainType.VOTACOES_PROPOSICOES)
        assert spec is not None
        assert spec.unique_keys == DOMAIN_KEYS[DomainType.VOTACOES_PROPOSICOES]


class TestSourceRouter:
    """SourceRouter sempre retorna BULK para domínios bulk_only."""

    def test_eventos_presenca_deputados_always_bulk(self):
        plan = SourceRouter.plan(
            DomainType.EVENTOS_PRESENCA_DEPUTADOS,
            LoadStrategy.INCREMENTAL,
            "2025-01-01",
            "2025-12-31",
        )
        assert plan.source_type.value == "bulk"

    def test_eventos_requerimentos_always_bulk(self):
        plan = SourceRouter.plan(
            DomainType.EVENTOS_REQUERIMENTOS, LoadStrategy.INCREMENTAL, "2025-01-01", "2025-12-31"
        )
        assert plan.source_type.value == "bulk"

    def test_votacoes_objetos_always_bulk(self):
        plan = SourceRouter.plan(
            DomainType.VOTACOES_OBJETOS, LoadStrategy.INCREMENTAL, "2025-01-01", "2025-12-31"
        )
        assert plan.source_type.value == "bulk"

    def test_votacoes_proposicoes_always_bulk(self):
        plan = SourceRouter.plan(
            DomainType.VOTACOES_PROPOSICOES, LoadStrategy.INCREMENTAL, "2025-01-01", "2025-12-31"
        )
        assert plan.source_type.value == "bulk"
