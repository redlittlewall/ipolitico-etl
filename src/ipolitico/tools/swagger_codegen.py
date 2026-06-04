"""
Ferramenta Swagger Codegen para iPolitico ETL.

Lê o arquivo Swagger da API da Câmara dos Deputados e gera blocos de
configuração e stubs de código para rotas ainda não implementadas.
"""

import argparse
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PathType(str, Enum):
    """Classifica o tipo de uma rota Swagger."""

    LIST = "list"
    DETAIL = "detail"
    CHILD = "child"
    REFERENCE = "reference"


@dataclass
class RouteInfo:
    """Informações sobre uma rota Swagger analisada."""

    path: str
    http_method: str
    summary: Optional[str]
    path_type: PathType
    candidate_domains: list[str] = field(default_factory=list)
    already_mapped: bool = False


def _to_snake_case(name: str) -> str:
    """
    Converte camelCase ou CamelCase para snake_case.

    Exemplos:
        'mandatosExternos' → 'mandatos_externos'
        'Deputados' → 'deputados'
        'codSituacao' → 'cod_situacao'

    Args:
        name: String em camelCase.

    Returns:
        String em snake_case.
    """
    result = ""
    for char in name:
        if char.isupper() and result:
            result += "_" + char.lower()
        else:
            result += char.lower()
    return result


def _is_param(segment: str) -> bool:
    """True if the segment is a Swagger path parameter like {id}."""
    return segment.startswith("{") and segment.endswith("}")


def _classify_segments(segments: list[str]) -> tuple[PathType, list[str]]:
    """
    Classifica uma rota pelo padrão de segments e extrai candidatos.

    Args:
        segments: Lista de segmentos do path (split por '/').

    Returns:
        Tupla (PathType, lista de nomes de domínio candidatos).
    """
    segments = [_to_snake_case(s) for s in segments]

    if segments and segments[0] == "referencias":
        return PathType.REFERENCE, ["referencias"]

    if len(segments) == 1:
        return PathType.LIST, [segments[0]]

    if len(segments) == 2 and _is_param(segments[1]):
        return PathType.DETAIL, [f"{segments[0]}_detalhe"]

    if len(segments) >= 3 and _is_param(segments[1]):
        child = segments[2]
        parent = segments[0]
        candidates = [f"{parent}_{child}", child]
        return PathType.CHILD, candidates

    # Fallback: just use the last segment
    return PathType.LIST, [segments[-1]]


def _indent_block(block: str, prefix: str) -> str:
    """Aplica prefixo de indentação em cada linha de um bloco."""
    return "\n".join(f"{prefix}{line}" for line in block.split("\n"))


def format_report(routes: list[RouteInfo]) -> str:
    """
    Gera relatório formatado com stubs para todas as rotas não mapeadas.

    Args:
        routes: Lista de RouteInfo não mapeadas.

    Returns:
        Relatório formatado em texto simples.
    """
    if not routes:
        return "Nenhuma rota não mapeada encontrada.\n"

    indent = "      "
    lines = [f"=== ROTAS NÃO MAPEADAS: {len(routes)} encontrada(s) ===\n"]
    for i, route in enumerate(routes, 1):
        lines.append(
            f"[{i}] {route.path} ({route.http_method}) — {route.summary or 'sem descrição'}"
        )
        lines.append(
            f"    Tipo: {route.path_type.value} → candidatos: {', '.join(route.candidate_domains)}"
        )
        lines.append("")
        lines.append("    YAML:")
        lines.append(_indent_block(generate_yaml_block(route), indent))
        lines.append("")
        lines.append("    DomainSpec:")
        lines.append(_indent_block(generate_domain_spec_stub(route), indent))
        lines.append("")
        lines.append("    SILVER_SCHEMA:")
        lines.append(_indent_block(generate_silver_schema_stub(route), indent))
        lines.append("")
    return "\n".join(lines)


def _to_enum_name(domain: str) -> str:
    """Converte nome de domínio para nome de enum (ex: 'recurso_novo' → 'RECURSO_NOVO')."""
    return domain.upper()


def _to_class_name(domain: str) -> str:
    """
    Converte nome de domínio snake_case para PascalCase (ex: 'recurso_novo' → 'RecursoNovo').

    Args:
        domain: Nome do domínio em snake_case.

    Returns:
        Nome da classe em PascalCase.
    """
    return domain.title().replace("_", "")


def generate_silver_schema_stub(route: RouteInfo) -> str:
    """
    Gera stub de SILVER_SCHEMA para uma rota não mapeada.

    Args:
        route: Informações da rota.

    Returns:
        Bloco de schema para colar em core/schemas.py.
    """
    domain = route.candidate_domains[0]
    lines = [
        f"# -- {domain} --",
        "# Em core/schemas.py (SILVER_SCHEMAS):",
        f"DomainType.{_to_enum_name(domain)}.value: {{",
        '    "id": pl.Int64,',
        "    # TODO: mapear colunas do Swagger — consultar schema em",
        f"    #       docs/camara_swagger.json → paths → {route.path}",
        "},",
    ]
    return "\n".join(lines)


def generate_domain_spec_stub(route: RouteInfo) -> str:
    """
    Gera stub de DomainSpec para uma rota não mapeada.

    Args:
        route: Informações da rota.

    Returns:
        Bloco de código Python com enum + DomainSpec para colar em constants.py
        e domain_spec.py.
    """
    domain = route.candidate_domains[0]
    enum_name = _to_enum_name(domain)
    lines = [
        f"# -- {domain} --",
        "# Em core/constants.py (DomainType):",
        f'# {enum_name} = "{domain}"',
        "",
        "# Em core/domain_spec.py:",
        "DomainSpec(",
        f"    domain=DomainType.{enum_name},",
        "    watermark_column=None,         # TODO: verificar se há coluna de data",
        "    earliest_iso=EarliestDates.DEPUTADOS,  # TODO: ajustar data mais antiga",
        "    depends_on=frozenset(),        # TODO: adicionar dependências",
        '    unique_keys=("id",),',
        "),",
    ]
    return "\n".join(lines)


def generate_yaml_block(route: RouteInfo) -> str:
    """
    Gera um bloco de configuração YAML para uma rota não mapeada.

    Args:
        route: Informações da rota a ser gerada.

    Returns:
        Bloco YAML formatado com extractor, transformer e sinks.
    """
    domain = route.candidate_domains[0]
    class_name = _to_class_name(domain)
    return "\n".join(
        [
            f"  {domain}:",
            f'    extractor: "ipolitico.extractors.camara.api.{domain}.{class_name}Extractor"',
            f"    transformer: "
            f'"ipolitico.transformers.camara.{domain}_transformer.Camara{class_name}Transformer"',
            "    sinks:",
            '      datalake: "ipolitico.sinks.datalake_sink.DataLakeSink"',
        ]
    )


def find_unmapped_routes(
    swagger: dict,
    existing_domains: set[str],
) -> list[RouteInfo]:
    """
    Percorre as paths do Swagger e retorna as que NÃO estão mapeadas.

    Args:
        swagger: Dict do Swagger (parsed JSON).
        existing_domains: Conjunto de nomes de domínio já implementados
                          (valores de DomainType).

    Returns:
        Lista de RouteInfo para rotas ainda não implementadas.
    """
    result: list[RouteInfo] = []
    paths = swagger.get("paths", {})

    for path, methods in paths.items():
        for http_method, details in methods.items():
            _try_add_route(path, http_method.upper(), details, existing_domains, result)

    return result


def _try_add_route(
    path: str,
    http_method: str,
    details: dict,
    existing_domains: set[str],
    result: list[RouteInfo],
) -> None:
    """
    Analisa um path individual e adiciona à lista se não estiver mapeado.

    Args:
        path: Path da rota (ex: '/deputados').
        http_method: Método HTTP (ex: 'GET').
        details: Dict com summary, tags etc.
        existing_domains: Domínios já implementados.
        result: Lista de saída (append se unmapped).
    """
    segments = [s for s in path.split("/") if s]
    path_type, candidates = _classify_segments(segments)

    already_mapped = any(c in existing_domains for c in candidates)

    if not already_mapped:
        result.append(
            RouteInfo(
                path=path,
                http_method=http_method,
                summary=details.get("summary"),
                path_type=path_type,
                candidate_domains=candidates,
                already_mapped=False,
            )
        )


def build_parser() -> argparse.ArgumentParser:
    """
    Constrói o parser de argumentos da CLI.

    Returns:
        ArgumentParser configurado.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Gera stubs de código para rotas Swagger não implementadas " "da Câmara dos Deputados."
        ),
    )
    parser.add_argument(
        "--swagger-path",
        default="docs/camara_swagger.json",
        help="Caminho para o arquivo Swagger JSON (default: docs/camara_swagger.json)",
    )
    return parser


def main() -> None:
    """
    Entry point da CLI. Lê o Swagger, encontra rotas não mapeadas e gera relatório.
    """
    parser = build_parser()
    args = parser.parse_args()

    with open(args.swagger_path) as f:
        swagger = json.load(f)

    from ipolitico.core.constants import DomainType

    existing = {v.value for v in DomainType}

    routes = find_unmapped_routes(swagger, existing)
    print(format_report(routes), end="")


if __name__ == "__main__":
    main()
