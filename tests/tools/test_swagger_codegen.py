"""
Tests for tools/swagger_codegen.py — Swagger-to-stub code generator.

Each test follows the RED → GREEN cycle: write one assertion, then implement
just enough code to make it pass.
"""

import json
from pathlib import Path

import pytest
from ipolitico.tools.swagger_codegen import (
    PathType,
    RouteInfo,
    build_parser,
    find_unmapped_routes,
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
        assert "ROTAS NÃO MAPEADAS" in report
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
