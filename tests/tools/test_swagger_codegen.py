"""
Tests for tools/swagger_codegen.py — Swagger-to-stub code generator.

Each test follows the RED → GREEN cycle: write one assertion, then implement
just enough code to make it pass.
"""

import json
from pathlib import Path

import pytest

from ipolitico.tools.swagger_codegen import (
    AuditEntry,
    PathType,
    RouteInfo,
    audit_coverage,
    build_parser,
    find_unmapped_routes,
    format_audit_report,
    format_report,
    generate_domain_spec_stub,
    generate_silver_schema_stub,
    generate_yaml_block,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def minimal_swagger() -> dict:
    """Small Swagger with 7 paths, 4 already mapped + 3 unmapped."""
    with open(FIXTURES / "minimal_swagger.json") as f:
        return json.load(f)


# ── Cycle 1: all paths already mapped → 0 unmapped ────────────────────


class TestFindUnmappedRoutes:
    """find_unmapped_routes() scanning logic."""

    def test_all_paths_mapped_returns_empty(self, minimal_swagger):
        """Given paths that all resolve to existing domains, return empty list."""
        existing = {
            "deputados",
            "blocos",
            "deputados_detalhe",
            "deputados_eventos",
            "recurso_novo",
            "recurso_novo_detalhe_filho",
            "referencias",
        }
        result = find_unmapped_routes(minimal_swagger, existing)
        assert result == []

    def test_detail_path_suggests_parent_detalhe(self):
        """Path like /recurso/{id} suggests recurso_detalhe."""
        swagger = {
            "paths": {
                "/deputados/{id}": {
                    "get": {"summary": "Detalhe do deputado", "tags": ["Deputados"]}
                },
            }
        }
        existing = {"deputados"}  # only LIST exists, DETAIL is new
        result = find_unmapped_routes(swagger, existing)
        assert len(result) == 1
        r = result[0]
        assert r.path == "/deputados/{id}"
        assert r.path_type == PathType.DETAIL
        assert r.candidate_domains == ["deputados_detalhe"]

    def test_build_parser_has_required_args(self):
        """CLI parser has --swagger-path and description."""
        parser = build_parser()
        assert parser.description is not None
        assert "swagger" in parser.description.lower() or "codegen" in parser.description.lower()
        actions = {a.dest for a in parser._actions}
        assert "swagger_path" in actions

    def test_format_report_contains_all_sections(self):
        """Formatted report includes header, route info, and all stub sections."""
        routes = [
            RouteInfo(
                path="/recurso_novo",
                http_method="GET",
                summary="Novo recurso",
                path_type=PathType.LIST,
                candidate_domains=["recurso_novo"],
                already_mapped=False,
            ),
            RouteInfo(
                path="/recurso_novo/{id}/detalhe_filho",
                http_method="GET",
                summary="Detalhe filho do recurso novo",
                path_type=PathType.CHILD,
                candidate_domains=["recurso_novo_detalhe_filho", "detalhe_filho"],
                already_mapped=False,
            ),
        ]
        report = format_report(routes)
        assert "ROTAS NÃO MAPEADAS" in report or "ROTAS NAO MAPEADAS" in report
        assert "/recurso_novo" in report
        assert "/recurso_novo/{id}/detalhe_filho" in report
        assert "YAML" in report
        assert "DomainSpec" in report
        assert "SILVER_SCHEMA" in report

    def test_generate_silver_schema_stub_for_new_domain(self):
        """SILVER_SCHEMA stub includes target domain key and placeholder columns."""
        route = RouteInfo(
            path="/recurso_novo",
            http_method="GET",
            summary="Novo recurso",
            path_type=PathType.LIST,
            candidate_domains=["recurso_novo"],
            already_mapped=False,
        )
        stub = generate_silver_schema_stub(route)
        assert "recurso_novo" in stub
        assert "pl.Int64" in stub
        assert "SILVER_SCHEMAS" in stub or "silver" in stub.lower()
        assert "TODO" in stub

    def test_generate_silver_schema_stub_senado(self):
        """SILVER_SCHEMA stub com provider='senado' usa SenadoDomainType."""
        route = RouteInfo(
            path="/recurso_novo",
            http_method="GET",
            summary="Novo recurso",
            path_type=PathType.LIST,
            candidate_domains=["recurso_novo"],
            already_mapped=False,
        )
        stub = generate_silver_schema_stub(route, provider="senado")
        assert "SenadoDomainType" in stub
        assert "docs/senado_swagger.json" in stub

    def test_generate_domain_spec_stub_senado(self):
        """DomainSpec stub com provider='senado' usa SenadoDomainType."""
        route = RouteInfo(
            path="/recurso_novo",
            http_method="GET",
            summary="Novo recurso",
            path_type=PathType.LIST,
            candidate_domains=["recurso_novo"],
            already_mapped=False,
        )
        stub = generate_domain_spec_stub(route, provider="senado")
        assert "SenadoDomainType" in stub
        assert "recurso_novo" in stub
        assert "DomainSpec" in stub

    def test_generate_yaml_block_default_camara(self):
        """YAML block default provider='camara' mantém módulos Câmara."""
        route = RouteInfo(
            path="/recurso_novo",
            http_method="GET",
            summary="Novo recurso",
            path_type=PathType.LIST,
            candidate_domains=["recurso_novo"],
            already_mapped=False,
        )
        yaml = generate_yaml_block(route)
        assert "ipolitico.extractors.camara" in yaml
        assert "Camara" in yaml

    def test_generate_yaml_block_senado(self):
        """YAML block com provider='senado' gera módulos Senado."""
        route = RouteInfo(
            path="/recurso_novo",
            http_method="GET",
            summary="Novo recurso",
            path_type=PathType.LIST,
            candidate_domains=["recurso_novo"],
            already_mapped=False,
        )
        yaml = generate_yaml_block(route, provider="senado")
        assert "ipolitico.extractors.senado" in yaml
        assert "Senado" in yaml
        assert "ipolitico.transformers.senado" in yaml

    def test_build_parser_has_provider_arg(self):
        """CLI parser tem --provider com choices camara e senado."""
        parser = build_parser()
        actions = {a.dest: a for a in parser._actions}
        assert "provider" in actions
        assert set(actions["provider"].choices) == {"camara", "senado"}
        assert actions["provider"].default == "camara"

    def test_format_report_senado_includes_senado_paths(self):
        """Formatted report com provider='senado' tem stubs com módulos senado."""
        routes = [
            RouteInfo(
                path="/recurso_novo",
                http_method="GET",
                summary="Novo recurso",
                path_type=PathType.LIST,
                candidate_domains=["recurso_novo"],
                already_mapped=False,
            ),
        ]
        report = format_report(routes, provider="senado")
        assert "/recurso_novo" in report
        assert "ipolitico.extractors.senado" in report
        assert "SenadoDomainType" in report
        assert "docs/senado_swagger.json" in report

    def test_generate_domain_spec_stub_for_new_domain(self):
        """DomainSpec stub includes DomainType constant and spec entry."""
        route = RouteInfo(
            path="/recurso_novo",
            http_method="GET",
            summary="Novo recurso",
            path_type=PathType.LIST,
            candidate_domains=["recurso_novo"],
            already_mapped=False,
        )
        stub = generate_domain_spec_stub(route)
        assert "RECURSO_NOVO" in stub
        assert "recurso_novo" in stub
        assert "DomainType" in stub
        assert "DomainSpec" in stub

    def test_generate_yaml_block_for_new_domain(self):
        """YAML block with correct structure for a new domain."""
        route = RouteInfo(
            path="/recurso_novo",
            http_method="GET",
            summary="Novo recurso",
            path_type=PathType.LIST,
            candidate_domains=["recurso_novo"],
            already_mapped=False,
        )
        yaml = generate_yaml_block(route)
        assert "recurso_novo:" in yaml
        assert "extractor:" in yaml
        assert "transformer:" in yaml
        assert "datalake" in yaml
        assert "sinks:" in yaml

    def test_reference_path_maps_to_referencias(self):
        """Path like /referencias/uf should match existing 'referencias' domain."""
        swagger = {
            "paths": {
                "/referencias/uf": {"get": {"summary": "Lista de UF", "tags": ["Referências"]}},
            }
        }
        existing = {"referencias"}
        result = find_unmapped_routes(swagger, existing)
        assert result == []  # already mapped

    def test_child_path_suggests_both_patterns(self):
        """Path like /deputados/{id}/frentes suggests both deputados_frentes and frentes."""
        swagger = {
            "paths": {
                "/deputados/{id}/frentes": {
                    "get": {"summary": "Frentes do deputado", "tags": ["Deputados"]}
                },
            }
        }
        existing = {"deputados"}
        result = find_unmapped_routes(swagger, existing)
        assert len(result) == 1
        r = result[0]
        assert r.path_type == PathType.CHILD
        assert set(r.candidate_domains) == {"deputados_frentes", "frentes"}

    def test_one_new_path_returns_unmapped(self):
        """One path not in existing domains returns RouteInfo with correct candidate."""
        swagger = {
            "paths": {
                "/deputados": {"get": {"summary": "Lista de deputados", "tags": ["Deputados"]}},
                "/recurso_novo": {"get": {"summary": "Novo recurso", "tags": ["Novos"]}},
            }
        }
        existing = {"deputados"}
        result = find_unmapped_routes(swagger, existing)
        assert len(result) == 1
        r = result[0]
        assert r.path == "/recurso_novo"
        assert r.http_method == "GET"
        assert r.path_type == PathType.LIST
        assert "recurso_novo" in r.candidate_domains
        assert r.already_mapped is False


# ── Cycle NEW: --audit coverage report ──────────────────────────────────


class TestAuditCoverage:
    """audit_coverage() scanning and reporting."""

    def test_build_parser_has_audit_flag(self):
        """CLI parser tem --audit flag (store_true)."""
        parser = build_parser()
        actions = {a.dest: a for a in parser._actions}
        assert "audit" in actions
        assert actions["audit"].default is False
        assert actions["audit"].const is True

    def test_audit_coverage_empty_swagger_returns_empty(self):
        """Swagger sem paths retorna lista vazia."""
        entries = audit_coverage({"paths": {}}, set())
        assert entries == []

    def test_audit_coverage_mapped_route(self, minimal_swagger):
        """Rota mapeada tem covered=True e domain preenchido."""
        existing = {"deputados", "deputados_detalhe", "deputados_eventos", "blocos", "referencias"}
        entries = audit_coverage(minimal_swagger, existing)
        deputados = [e for e in entries if e.path == "/deputados"]
        assert len(deputados) == 1
        assert deputados[0].covered is True
        assert deputados[0].domain == "deputados"

    def test_audit_coverage_unmapped_route(self, minimal_swagger):
        """Rota nao mapeada tem covered=False."""
        existing = {"deputados", "deputados_detalhe", "blocos", "referencias"}
        entries = audit_coverage(minimal_swagger, existing)
        unmapped = [e for e in entries if not e.covered]
        assert any(e.path == "/recurso_novo" for e in unmapped)
        rec = [e for e in unmapped if e.path == "/recurso_novo"][0]
        assert rec.domain == "recurso_novo"

    def test_audit_coverage_includes_all_routes(self, minimal_swagger):
        """Todos os 7 paths do fixture aparecem no audit."""
        existing = {"deputados", "deputados_detalhe", "deputados_eventos", "blocos", "referencias"}
        entries = audit_coverage(minimal_swagger, existing)
        assert len(entries) == 7

    def test_format_audit_report_has_table_structure(self):
        """Relatorio tabular tem cabecalho, separador, e linhas."""
        entries = [
            AuditEntry(
                path="/deputados",
                http_method="GET",
                summary="Lista de deputados",
                path_type="list",
                domain="deputados",
                covered=True,
                extractor="ipolitico.extractors.camara.api.deputados.DeputadosExtractor",
                transformer="ipolitico.transformers.camara.deputados_transformer.CamaraDeputadosTransformer",
                swagger_fields=["id", "nome", "siglaPartido"],
            ),
            AuditEntry(
                path="/recurso_novo",
                http_method="GET",
                summary="Novo recurso",
                path_type="list",
                domain="recurso_novo",
                covered=False,
                extractor=None,
                transformer=None,
                swagger_fields=[],
            ),
        ]
        report = format_audit_report(entries)
        assert "Rota" in report
        assert "Dominio" in report or "Dominio" in report
        assert "Coberto" in report or "Status" in report
        assert "/deputados" in report
        assert "/recurso_novo" in report

    def test_audit_coverage_extracts_swagger_fields(self, minimal_swagger):
        """Rota com response schema no Swagger tem swagger_fields populado."""
        existing = {"deputados", "deputados_detalhe", "deputados_eventos", "blocos", "referencias"}
        entries = audit_coverage(minimal_swagger, existing)
        blocos = [e for e in entries if e.path == "/blocos"]
        assert len(blocos) == 1
        assert "id" in blocos[0].swagger_fields
        assert "nome" in blocos[0].swagger_fields
