"""
Ferramenta Swagger Codegen para iPolitico ETL.

Lê o arquivo Swagger da API de um provider (Câmara, Senado) e gera blocos de
configuração e stubs de código para rotas ainda não implementadas.
"""

import argparse
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class ProviderTemplate:
    """Templates de geração de código por provider (Câmara, Senado, etc.).

    Attributes:
        name: Nome do provider.
        extractor_tpl: Template do módulo extrator.
        transformer_tpl: Template do módulo transformer.
        domain_type_class: Nome da classe Enum de DomainType.
        domain_type_module: Módulo Python do DomainType.
        sink_tpl: Template do módulo sink.
        swagger_doc_ref: Caminho do arquivo Swagger para TODOs.
    """

    name: str
    extractor_tpl: str
    transformer_tpl: str
    domain_type_class: str = "DomainType"
    domain_type_module: str = "ipolitico.core.constants"
    sink_tpl: str = "ipolitico.sinks.datalake_sink.DataLakeSink"
    swagger_doc_ref: str = "docs/camara_swagger.json"


PROVIDER_TEMPLATES: dict[str, ProviderTemplate] = {
    "camara": ProviderTemplate(
        name="camara",
        extractor_tpl="ipolitico.extractors.camara.api.{domain}.{class_name}Extractor",
        transformer_tpl=(
            "ipolitico.transformers.camara.{domain}_transformer." "Camara{class_name}Transformer"
        ),
    ),
    "senado": ProviderTemplate(
        name="senado",
        extractor_tpl="ipolitico.extractors.senado.{domain}.{class_name}Extractor",
        transformer_tpl=(
            "ipolitico.transformers.senado.{domain}_transformer." "Senado{class_name}Transformer"
        ),
        domain_type_class="SenadoDomainType",
        swagger_doc_ref="docs/senado_swagger.json",
    ),
}


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
        'mandatosExternos' -> 'mandatos_externos'
        'Deputados' -> 'deputados'
        'codSituacao' -> 'cod_situacao'

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
    Classifica uma rota pelo padrao de segments e extrai candidatos.

    Args:
        segments: Lista de segmentos do path (split por '/').

    Returns:
        Tupla (PathType, lista de nomes de dominio candidatos).
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
    """Aplica prefixo de indentacao em cada linha de um bloco."""
    return "\n".join(f"{prefix}{line}" for line in block.split("\n"))


def format_report(
    routes: list[RouteInfo],
    provider: str = "camara",
) -> str:
    """
    Gera relatorio formatado com stubs para todas as rotas nao mapeadas.

    Args:
        routes: Lista de RouteInfo nao mapeadas.
        provider: Nome do provider ('camara', 'senado').

    Returns:
        Relatorio formatado em texto simples.
    """
    if not routes:
        return "Nenhuma rota nao mapeada encontrada.\n"

    indent = "      "
    lines = [f"=== ROTAS NAO MAPEADAS: {len(routes)} encontrada(s) ===\n"]
    for i, route in enumerate(routes, 1):
        lines.append(
            f"[{i}] {route.path} ({route.http_method}) - {route.summary or 'sem descricao'}"
        )
        lines.append(
            f"    Tipo: {route.path_type.value} -> candidatos: {', '.join(route.candidate_domains)}"
        )
        lines.append("")
        lines.append("    YAML:")
        lines.append(_indent_block(generate_yaml_block(route, provider=provider), indent))
        lines.append("")
        lines.append("    DomainSpec:")
        lines.append(_indent_block(generate_domain_spec_stub(route, provider=provider), indent))
        lines.append("")
        lines.append("    SILVER_SCHEMA:")
        lines.append(_indent_block(generate_silver_schema_stub(route, provider=provider), indent))
        lines.append("")
    return "\n".join(lines)


def _to_enum_name(domain: str) -> str:
    """Converte nome de dominio para nome de enum (ex: 'recurso_novo' -> 'RECURSO_NOVO')."""
    return domain.upper()


def _to_class_name(domain: str) -> str:
    """
    Converte nome de dominio snake_case para PascalCase.

    Args:
        domain: Nome do dominio em snake_case.

    Returns:
        Nome da classe em PascalCase.
    """
    return domain.title().replace("_", "")


def generate_silver_schema_stub(
    route: RouteInfo,
    provider: str = "camara",
) -> str:
    """
    Gera stub de SILVER_SCHEMA para uma rota nao mapeada.

    Args:
        route: Informacoes da rota.
        provider: Nome do provider.

    Returns:
        Bloco de schema para colar em core/schemas.py.
    """
    tpl = PROVIDER_TEMPLATES[provider]
    domain = route.candidate_domains[0]
    lines = [
        f"# -- {domain} --",
        "# Em core/schemas.py (SILVER_SCHEMAS):",
        f"{tpl.domain_type_class}.{_to_enum_name(domain)}.value: {{",
        '    "id": pl.Int64,',
        "    # TODO: mapear colunas do Swagger - consultar schema em",
        f"    #       {tpl.swagger_doc_ref} -> paths -> {route.path}",
        "},",
    ]
    return "\n".join(lines)


def generate_domain_spec_stub(
    route: RouteInfo,
    provider: str = "camara",
) -> str:
    """
    Gera stub de DomainSpec para uma rota nao mapeada.

    Args:
        route: Informacoes da rota.
        provider: Nome do provider.

    Returns:
        Bloco de codigo Python com enum + DomainSpec.
    """
    tpl = PROVIDER_TEMPLATES[provider]
    domain = route.candidate_domains[0]
    enum_name = _to_enum_name(domain)
    lines = [
        f"# -- {domain} --",
        f"# Em {tpl.domain_type_module} ({tpl.domain_type_class}):",
        f'# {enum_name} = "{domain}"',
        "",
        "# Em core/domain_spec.py:",
        "DomainSpec(",
        f"    domain={tpl.domain_type_class}.{enum_name},",
        "    watermark_column=None,         # TODO: verificar se ha coluna de data",
        "    earliest_iso=EarliestDates.DEPUTADOS,  # TODO: ajustar data mais antiga",
        "    depends_on=frozenset(),        # TODO: adicionar dependencias",
        '    unique_keys=("id",),',
        "),",
    ]
    return "\n".join(lines)


def generate_yaml_block(route: RouteInfo, provider: str = "camara") -> str:
    """
    Gera um bloco de configuracao YAML para uma rota nao mapeada.

    Args:
        route: Informacoes da rota a ser gerada.
        provider: Nome do provider.

    Returns:
        Bloco YAML formatado com extractor, transformer e sinks.
    """
    tpl = PROVIDER_TEMPLATES[provider]
    domain = route.candidate_domains[0]
    class_name = _to_class_name(domain)
    extractor = tpl.extractor_tpl.format(domain=domain, class_name=class_name)
    transformer = tpl.transformer_tpl.format(domain=domain, class_name=class_name)
    return "\n".join(
        [
            f"  {domain}:",
            f'    extractor: "{extractor}"',
            f"    transformer: " f'"{transformer}"',
            "    sinks:",
            f'      datalake: "{tpl.sink_tpl}"',
        ]
    )


def find_unmapped_routes(
    swagger: dict,
    existing_domains: set[str],
) -> list[RouteInfo]:
    """
    Percorre as paths do Swagger e retorna as que NAO estao mapeadas.

    Args:
        swagger: Dict do Swagger (parsed JSON).
        existing_domains: Conjunto de nomes de dominio ja implementados
                          (valores de DomainType).

    Returns:
        Lista de RouteInfo para rotas ainda nao implementadas.
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
    Analisa um path individual e adiciona a lista se nao estiver mapeado.

    Args:
        path: Path da rota (ex: '/deputados').
        http_method: Metodo HTTP (ex: 'GET').
        details: Dict com summary, tags etc.
        existing_domains: Dominios ja implementados.
        result: Lista de saida (append se unmapped).
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
    Constroi o parser de argumentos da CLI.

    Returns:
        ArgumentParser configurado.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Gera stubs de codigo para rotas Swagger nao implementadas "
            "de um provider (Camara, Senado, etc.)."
        ),
    )
    parser.add_argument(
        "--swagger-path",
        default="docs/camara_swagger.json",
        help="Caminho para o arquivo Swagger JSON (default: docs/camara_swagger.json)",
    )
    parser.add_argument(
        "--provider",
        default="camara",
        choices=list(PROVIDER_TEMPLATES.keys()),
        help="Provider da API (default: camara)",
    )
    return parser


def main() -> None:
    """
    Entry point da CLI. Le o Swagger, encontra rotas nao mapeadas e gera relatorio.
    """
    parser = build_parser()
    args = parser.parse_args()

    with open(args.swagger_path) as f:
        swagger = json.load(f)

    from ipolitico.core.constants import DomainType

    existing = {v.value for v in DomainType}

    routes = find_unmapped_routes(swagger, existing)
    print(format_report(routes, provider=args.provider), end="")


if __name__ == "__main__":
    main()
