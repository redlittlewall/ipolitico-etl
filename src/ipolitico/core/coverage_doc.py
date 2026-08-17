"""Geração do documento público de cobertura de dados a partir do registry.

Fonte única: o registry de cobertura — ``EARLIEST_DATE_MAP`` (data de início real),
``COVERAGE_GAPS`` (lacunas no meio da série) e ``DOMAIN_SOURCE_SYSTEM``
(sistema/API de origem). A renderização é pura: um registry conhecido sempre
produz o mesmo Markdown. O entrypoint ``generate_coverage_doc`` grava o documento
em Markdown no caminho pedido; o CLI aponta o padrão para ``docs/cobertura-dados.md``
(issue 03).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ipolitico.core.constants import (
    COVERAGE_GAPS,
    DOMAIN_LABELS,
    DOMAIN_SOURCE_SYSTEM,
    EARLIEST_DATE_MAP,
    DomainType,
    EarliestDates,
    SourceSystem,
)
from ipolitico.core.domain_spec import spec_for
from ipolitico.pipeline.domain_order import FULL_PIPELINE

# ── Metadados de exibição por sistema de origem ───────────────────────────────
SOURCE_SYSTEM_LABELS: Mapping[SourceSystem, str] = {
    SourceSystem.CAMARA: "Câmara dos Deputados",
    SourceSystem.SENADO: "Senado Federal",
}

SOURCE_API_URLS: Mapping[SourceSystem, str] = {
    SourceSystem.CAMARA: "https://dadosabertos.camara.leg.br",
    SourceSystem.SENADO: "https://legis.senado.leg.br",
}

# Ordem canônica das seções no documento.
_SYSTEMS_IN_ORDER: tuple[SourceSystem, ...] = (SourceSystem.CAMARA, SourceSystem.SENADO)

# Marca de ausência de lacunas nas tabelas.
_NO_GAPS = "—"

# Domínios documentados no registry (EarliestDates/DOMAIN_SOURCE_SYSTEM) mas
# ainda sem DomainType — chegam em issues próprias (folha → issue 04;
# remunerações/CEAPs → issues 08/09). Guarda apenas o rótulo: sistema de origem
# e data de início são lidos das fontes únicas (DOMAIN_SOURCE_SYSTEM e
# EarliestDates) em build_coverage_entries, nunca copiados.
_DOCUMENTED_ONLY: tuple[tuple[str, str], ...] = (
    ("folha_pagamento", "Folha de pagamento consolidada (Câmara)"),
    ("remuneracoes", "Remunerações do Senado (administrativo)"),
    ("despesas_ceaps", "Despesas de CEAPs do Senado"),
)


@dataclass(frozen=True)
class CoverageEntry:
    """Uma linha do documento de cobertura de dados.

    Args:
        domain: Nome do domínio (``domain.value``, ex: ``"despesas"``).
        label: Descrição curta exibida ao leitor.
        source_system: Sistema de origem (Câmara ou Senado).
        earliest_iso: Data de início real de disponibilidade de dados (ISO).
        gaps: Notas de lacunas no meio da série; vazio quando não há.
        implemented: True para domínios já ingeridos; False para domínios apenas
            documentados (data confirmada no registry, extração ainda não existe).
    """

    domain: str
    label: str
    source_system: SourceSystem
    earliest_iso: str
    gaps: tuple[str, ...] = ()
    implemented: bool = True


def _format_gaps(gaps: Sequence[str]) -> str:
    """Une as notas de lacunas para exibição em tabela.

    Args:
        gaps: Notas de lacunas do domínio (pode ser vazio).

    Returns:
        Notas separadas por "; " ou a marca ``—`` quando não há lacunas.
    """
    return "; ".join(gaps) if gaps else _NO_GAPS


def build_coverage_entries() -> list[CoverageEntry]:
    """Monta as entradas de cobertura a partir do registry de cobertura.

    Percorre os ``DomainType`` na ordem canônica da pipeline (``FULL_PIPELINE``,
    com fallback alfabético para domínios fora da tupla) e acrescenta ao final os
    domínios documentados no registry que ainda não têm ``DomainType`` — lendo
    sistema de origem e data de início das fontes únicas.

    Returns:
        Lista de ``CoverageEntry`` — uma por domínio, na ordem de exibição
        (implementados primeiro, depois os documentados). Nunca vazia.
    """
    order = {d: i for i, d in enumerate(FULL_PIPELINE)}
    entries: list[CoverageEntry] = []

    for domain in sorted(DomainType, key=lambda d: (order.get(d, 999), d.value)):
        spec = spec_for(domain)
        gaps = spec.coverage_gaps if spec is not None else COVERAGE_GAPS.get(domain.value, ())
        entries.append(
            CoverageEntry(
                domain=domain.value,
                label=DOMAIN_LABELS.get(domain, domain.value),
                source_system=DOMAIN_SOURCE_SYSTEM[domain.value],
                earliest_iso=EARLIEST_DATE_MAP[domain],
                gaps=gaps,
                implemented=True,
            )
        )

    for name, label in _DOCUMENTED_ONLY:
        entries.append(
            CoverageEntry(
                domain=name,
                label=label,
                source_system=DOMAIN_SOURCE_SYSTEM[name],
                earliest_iso=getattr(EarliestDates, name.upper()),
                gaps=COVERAGE_GAPS.get(name, ()),
                implemented=False,
            )
        )
    return entries


def render_coverage_doc(
    entries: Sequence[CoverageEntry],
    *,
    source_system_labels: Mapping[SourceSystem, str] = SOURCE_SYSTEM_LABELS,
    source_api_urls: Mapping[SourceSystem, str] = SOURCE_API_URLS,
) -> str:
    """Renderiza o documento de cobertura de dados em Markdown.

    Função pura: dados as mesmas entradas e os mesmos metadados de sistema, o
    retorno é sempre idêntico. Agrupa as entradas implementadas por sistema de
    origem (Câmara primeiro, depois Senado) e abre uma seção separada para os
    domínios documentados (``implemented=False``).

    Args:
        entries: Entradas de cobertura na ordem de exibição desejada.
        source_system_labels: Rótulo de exibição por sistema de origem.
        source_api_urls: URL base da API por sistema de origem.

    Returns:
        Documento Markdown completo (str) terminado em quebra de linha. Se não
        houver entradas implementadas de um sistema, a seção é omitida; idem
        para a seção de planejados quando vazia.
    """
    implemented = [e for e in entries if e.implemented]
    planned = [e for e in entries if not e.implemented]

    lines: list[str] = [
        "# Cobertura de Dados — iPolitico ETL",
        "",
        "> Documento gerado automaticamente a partir do registry de cobertura do código",
        "> (`EARLIEST_DATE_MAP`, `COVERAGE_GAPS`, `DOMAIN_SOURCE_SYSTEM`). Não edite à mão.",
        "> Para regenerar: `ipolitico --generate-coverage-doc`.",
        "",
        "A **data de início** indica quando o órgão passou a disponibilizar dados para o",
        "domínio — não há registros anteriores por ausência na fonte, e o full load não",
        "faz requisições em períodos sem dados. As **lacunas** são ausências permanentes",
        "conhecidas no meio da série (a fonte responde vazio/404 para o período).",
        "",
        "## Sistemas de origem",
        "",
        "| Sistema | API |",
        "|---|---|",
    ]
    # Lista apenas os sistemas presentes nas entradas implementadas (na ordem
    # canônica) — os domínios planejados declaram o próprio sistema na seção deles.
    present_systems = [
        s for s in _SYSTEMS_IN_ORDER if any(e.source_system == s for e in implemented)
    ]
    for system in present_systems:
        lines.append(f"| {source_system_labels[system]} | {source_api_urls[system]} |")
    lines.append("")

    for system in present_systems:
        system_entries = [e for e in implemented if e.source_system == system]
        lines.append(f"## {source_system_labels[system]}")
        lines.append("")
        lines.append(f"API: {source_api_urls[system]}")
        lines.append("")
        lines.append("| Domínio | Início dos dados | Lacunas no meio da série |")
        lines.append("|---|---|---|")
        for entry in system_entries:
            lines.append(f"| `{entry.domain}` | {entry.earliest_iso} | {_format_gaps(entry.gaps)} |")
        lines.append("")

    if planned:
        lines.append("## Domínios planejados (datas documentadas)")
        lines.append("")
        lines.append(
            "Domínios com data de disponibilidade já confirmada no registry, ainda não ingeridos."
        )
        lines.append("")
        lines.append("| Domínio | Sistema | Início documentado | Lacunas |")
        lines.append("|---|---|---|---|")
        for entry in planned:
            system_label = source_system_labels[entry.source_system]
            lines.append(
                f"| `{entry.domain}` | {system_label} | {entry.earliest_iso} | "
                f"{_format_gaps(entry.gaps)} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_coverage_doc(output_path: Path) -> None:
    """Gera o documento de cobertura de dados e grava em ``output_path``.

    Comando (não retorna valor): monta as entradas a partir do registry
    (``build_coverage_entries``), renderiza (``render_coverage_doc``) e escreve o
    Markdown no disco. Quem decide o caminho padrão é o CLI.

    Args:
        output_path: Caminho de destino do Markdown gerado. O diretório pai é
            criado se necessário.

    Raises:
        OSError: se o diretório pai não puder ser criado ou a escrita falhar.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_coverage_doc(build_coverage_entries())
    output_path.write_text(markdown, encoding="utf-8")
