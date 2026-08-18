"""Issue 03 — Documento público de cobertura de dados gerado a partir do registry.

A função pura ``render_coverage_doc`` recebe um registry conhecido e devolve o
Markdown esperado; ``build_coverage_entries`` monta as entradas a partir das
fontes únicas (``EARLIEST_DATE_MAP``, ``COVERAGE_GAPS``, ``DOMAIN_SOURCE_SYSTEM``).
"""

from pathlib import Path

from ipolitico.core.constants import (
    DOMAIN_SOURCE_SYSTEM,
    EARLIEST_DATE_MAP,
    DomainType,
    SourceSystem,
)
from ipolitico.core.coverage_doc import (
    CoverageEntry,
    build_coverage_entries,
    generate_coverage_doc,
    render_coverage_doc,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _entry(
    domain: str,
    system: SourceSystem,
    earliest: str,
    gaps: tuple[str, ...] = (),
    label: str | None = None,
    implemented: bool = True,
) -> CoverageEntry:
    """Factory de ``CoverageEntry`` para testes.

    Args:
        domain: Nome do domínio.
        system: Sistema de origem.
        earliest: Data de início real (ISO).
        gaps: Lacunas no meio da série.
        label: Rótulo amigável (default: próprio nome do domínio).
        implemented: Se o domínio é considerado implementado.

    Returns:
        ``CoverageEntry`` preenchido com os valores fornecidos.
    """
    return CoverageEntry(
        domain=domain,
        label=label or domain,
        source_system=system,
        earliest_iso=earliest,
        gaps=gaps,
        implemented=implemented,
    )


SAMPLE_ENTRIES = [
    _entry("despesas", SourceSystem.CAMARA, "2009-01-01", label="Cota para Exercício (CEAP)"),
    _entry("proposicoes", SourceSystem.CAMARA, "1988-01-01"),
    _entry("senadores", SourceSystem.SENADO, "1949-01-01", label="Senadores"),
    _entry(
        "folha_pagamento",
        SourceSystem.CAMARA,
        "2012-01-01",
        gaps=("2011, 2015 e 2022 não publicados (HTTP 404) — ausência, não erro",),
        label="Folha de pagamento",
        implemented=False,
    ),
]


class TestRenderCoberturaDoc:
    """Função pura: registry conhecido → Markdown esperado."""

    def test_render_full_documento_esperado(self):
        markdown = render_coverage_doc(SAMPLE_ENTRIES)
        assert markdown == (
            "# Cobertura de Dados — iPolitico ETL\n"
            "\n"
            "> Documento gerado automaticamente a partir do registry de cobertura do código\n"
            "> (`EARLIEST_DATE_MAP`, `COVERAGE_GAPS`, `DOMAIN_SOURCE_SYSTEM`). Não edite à mão.\n"
            "> Para regenerar: `ipolitico --generate-coverage-doc`.\n"
            "\n"
            "A **data de início** indica quando o órgão passou a disponibilizar dados para o\n"
            "domínio — não há registros anteriores por ausência na fonte, e o full load não\n"
            "faz requisições em períodos sem dados. As **lacunas** são ausências permanentes\n"
            "conhecidas no meio da série (a fonte responde vazio/404 para o período).\n"
            "\n"
            "## Sistemas de origem\n"
            "\n"
            "| Sistema | API |\n"
            "|---|---|\n"
            "| Câmara dos Deputados | https://dadosabertos.camara.leg.br |\n"
            "| Senado Federal | https://legis.senado.leg.br |\n"
            "\n"
            "## Câmara dos Deputados\n"
            "\n"
            "API: https://dadosabertos.camara.leg.br\n"
            "\n"
            "| Domínio | Início dos dados | Lacunas no meio da série |\n"
            "|---|---|---|\n"
            "| `despesas` | 2009-01-01 | — |\n"
            "| `proposicoes` | 1988-01-01 | — |\n"
            "\n"
            "## Senado Federal\n"
            "\n"
            "API: https://legis.senado.leg.br\n"
            "\n"
            "| Domínio | Início dos dados | Lacunas no meio da série |\n"
            "|---|---|---|\n"
            "| `senadores` | 1949-01-01 | — |\n"
            "\n"
            "## Domínios planejados (datas documentadas)\n"
            "\n"
            "Domínios com data de disponibilidade já confirmada no registry, ainda não ingeridos.\n"
            "\n"
            "| Domínio | Sistema | Início documentado | Lacunas |\n"
            "|---|---|---|---|\n"
            "| `folha_pagamento` | Câmara dos Deputados | 2012-01-01 | "
            "2011, 2015 e 2022 não publicados (HTTP 404) — ausência, não erro |\n"
        )

    def test_render_sem_lacunas_usa_emdash(self):
        markdown = render_coverage_doc([_entry("votacoes", SourceSystem.CAMARA, "1991-01-01")])
        assert "| `votacoes` | 1991-01-01 | — |" in markdown

    def test_render_omite_secao_planejados_quando_vazia(self):
        markdown = render_coverage_doc([_entry("despesas", SourceSystem.CAMARA, "2009-01-01")])
        assert "Domínios planejados" not in markdown

    def test_render_grupos_por_sistema_na_ordem_camara_depois_senado(self):
        markdown = render_coverage_doc(
            [
                _entry("senadores", SourceSystem.SENADO, "1949-01-01"),
                _entry("despesas", SourceSystem.CAMARA, "2009-01-01"),
            ]
        )
        camara_idx = markdown.index("## Câmara dos Deputados")
        senado_idx = markdown.index("## Senado Federal")
        assert camara_idx < senado_idx

    def test_render_usa_labels_e_urls_configuraveis(self):
        markdown = render_coverage_doc(
            [_entry("despesas", SourceSystem.CAMARA, "2009-01-01")],
            source_system_labels={SourceSystem.CAMARA: "Casa A"},
            source_api_urls={SourceSystem.CAMARA: "https://api.example"},
        )
        assert "| Casa A | https://api.example |" in markdown
        assert "## Casa A" in markdown
        assert "API: https://api.example" in markdown


class TestRegistrySistemaOrigem:
    """Todo domínio tem sistema de origem explícito (sem default silencioso)."""

    def test_todo_domaintype_tem_sistema_de_origem(self):
        missing = [d.value for d in DomainType if d.value not in DOMAIN_SOURCE_SYSTEM]
        assert missing == []

    def test_despesas_origem_camara(self):
        assert DOMAIN_SOURCE_SYSTEM["despesas"] == SourceSystem.CAMARA

    def test_senadores_origem_senado(self):
        assert DOMAIN_SOURCE_SYSTEM["senadores"] == SourceSystem.SENADO

    def test_dominios_documentados_origem_correta(self):
        assert DOMAIN_SOURCE_SYSTEM["folha_pagamento"] == SourceSystem.CAMARA
        assert DOMAIN_SOURCE_SYSTEM["remuneracoes"] == SourceSystem.SENADO
        assert DOMAIN_SOURCE_SYSTEM["despesas_ceaps"] == SourceSystem.SENADO


class TestBuildCoverageEntries:
    """Entradas montadas a partir do registry real."""

    def test_cobre_todos_os_domaintype_mais_planejados(self):
        entries = build_coverage_entries()
        implemented_names = {e.domain for e in entries if e.implemented}
        assert set(DomainType) == {DomainType(n) for n in implemented_names}
        planned_names = {e.domain for e in entries if not e.implemented}
        # despesas_ceaps virou DomainType implementado (issue 09) — nada planeja.
        assert planned_names == set()

    def test_usa_data_real_de_inicio(self):
        by_name = {e.domain: e for e in build_coverage_entries()}
        assert by_name["despesas"].earliest_iso == EARLIEST_DATE_MAP[DomainType.DESPESAS]
        assert by_name["despesas"].earliest_iso == "2009-01-01"

    def test_lacunas_do_spec_aparecem_nas_entradas(self):
        by_name = {e.domain: e for e in build_coverage_entries()}
        folha = by_name["folha_pagamento"]
        assert folha.gaps
        assert "2011" in " ".join(folha.gaps)
        assert by_name["despesas"].gaps == ()

    def test_planejados_implemented_false(self):
        by_name = {e.domain: e for e in build_coverage_entries()}
        assert by_name["despesas"].implemented is True
        assert by_name["folha_pagamento"].implemented is True

    def test_entradas_em_ordem_canonica_da_pipeline(self):
        from ipolitico.pipeline.domain_order import FULL_PIPELINE

        entries = [e for e in build_coverage_entries() if e.implemented]
        order = {d.value: i for i, d in enumerate(FULL_PIPELINE)}
        # Domínios fora da tupla canônica (blocos_detalhe, proposicoes_detalhe)
        # caem no fallback 999, ao final — mesma regra do builder.
        keys = [order.get(e.domain, 999) for e in entries]
        assert keys == sorted(keys)


class TestGeracaoArquivo:
    """Entrypoint de geração grava o documento no disco."""

    def test_generate_escreve_arquivo(self, tmp_path):
        out = tmp_path / "cobertura.md"
        generate_coverage_doc(out)
        assert out.is_file()
        assert out.read_text(encoding="utf-8") == render_coverage_doc(build_coverage_entries())

    def test_doc_committed_sincronizado_com_registry(self):
        """O docs/cobertura-dados.md versionado nunca deve dessincronizar do código."""
        committed = Path(REPO_ROOT) / "docs" / "cobertura-dados.md"
        assert committed.is_file(), "docs/cobertura-dados.md não existe — rode o gerador"
        assert committed.read_text(encoding="utf-8") == render_coverage_doc(
            build_coverage_entries()
        )

    def test_generate_cria_diretorio_pai(self, tmp_path):
        out = tmp_path / "sub" / "dir" / "cobertura.md"
        generate_coverage_doc(out)
        assert out.is_file()


class TestGeracaoViaCLI:
    """O entrypoint argparse (--generate-coverage-doc) grava o documento."""

    def test_cli_gera_documento_no_caminho_pedido(self, tmp_path, monkeypatch, capsys):
        from ipolitico.main import main_cli

        out = tmp_path / "cli" / "cobertura.md"
        monkeypatch.setattr(
            "sys.argv",
            ["ipolitico", "--generate-coverage-doc", "--coverage-doc-output", str(out)],
        )
        main_cli()
        assert out.is_file()
        assert "Documento de cobertura gerado em" in capsys.readouterr().out
        assert out.read_text(encoding="utf-8") == render_coverage_doc(build_coverage_entries())

    def test_cli_padrao_aponta_para_docs(self, monkeypatch, tmp_path):
        from ipolitico.main import main_cli

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["ipolitico", "--generate-coverage-doc"])
        main_cli()
        assert (tmp_path / "docs" / "cobertura-dados.md").is_file()
