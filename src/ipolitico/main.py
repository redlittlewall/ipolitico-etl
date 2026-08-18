import argparse
import asyncio
import logging
import time
from pathlib import Path

import yaml

from ipolitico.core.camara_client import CamaraClient
from ipolitico.core.constants import (
    DOMAIN_LABELS,
    DomainType,
    LoadStrategy,
    MedallionLayer,
    SinkType,
)
from ipolitico.gold.custo_erario import (
    CUSTO_PK,
    OBS_PK,
    CoberturaCustoErario,
    CustoErarioBuilder,
)
from ipolitico.gold.entidade_canonica import (
    ALIASES_PK,
    POLITICOS_PK,
    RESOLUCOES_PK,
    CoberturaEntidadeCanonica,
    EntidadeCanonicaBuilder,
)
from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.domain_order import (
    FULL_PIPELINE,
    expand_domains_with_dependencies,
)
from ipolitico.pipeline.federation import FederationOrchestrator
from ipolitico.pipeline.manager import PipelineManager
from ipolitico.pipeline.optimizer import DataLakeOptimizer
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.sinks.datalake_sink import DataLakeSink
from ipolitico.storage.gold_exporter import ExportFormat, GoldExporter

logger = logging.getLogger(__name__)


def load_config(file_path: Path) -> dict:
    """Carrega as definições dinâmicas de pipeline em formato YAML."""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _print_domain_tree() -> None:
    """
    Exibe a árvore hierárquica de domínios com labels descritivos.

    Agrupa domínios em seções: Entidades Principais (pais), Referências
    e Carga Massiva (bulk-only). Filhos são indentados sob seus pais
    com caracteres de árvore (├── / └──).
    """
    from ipolitico.core.domain_spec import DOMAIN_SPECS
    from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

    # ── Catalogar domínios ────────────────────────────────────────────────────
    bulk_only: set[DomainType] = {
        DomainType(k) for k, v in BULK_REGISTRY.items() if v.get("bulk_only")
    }

    # Pais → filhos via DOMAIN_SPECS (depends_on)
    parent_children: dict[DomainType, list[DomainType]] = {}
    all_with_deps: set[DomainType] = set()
    for domain, spec in DOMAIN_SPECS.items():
        for parent in spec.depends_on:
            parent_children.setdefault(parent, []).append(domain)
            all_with_deps.add(domain)

    # Ordem canônica como chave de ordenação
    pipeline_order = {d: i for i, d in enumerate(FULL_PIPELINE)}

    # Entidades raiz: não são bulk-only e não dependem de ninguém (via DOMAIN_SPECS)
    EXCLUDED_ROOTS: set[DomainType] = {DomainType.REFERENCIAS}
    roots: list[DomainType] = [
        d
        for d in DOMAIN_SPECS
        if d not in bulk_only and d not in EXCLUDED_ROOTS and not DOMAIN_SPECS[d].depends_on
    ]
    roots.sort(key=lambda d: pipeline_order.get(d, 999))

    # ── Helper de formatação ──────────────────────────────────────────────────
    def _fmt(domain: DomainType, prefix: str = "") -> str:
        name = domain.value
        label = DOMAIN_LABELS.get(domain, name)
        label_width = 50
        return f"{prefix}{name:<20} {label:<{label_width}}"

    def _section(title: str) -> None:
        sep = "─" * (60 - len(title) - 4)
        print(f"\n{sep} {title} {sep}")

    # ── Seção 1: Entidades Principais ─────────────────────────────────────────
    _section("Entidades Principais")
    for root in roots:
        children = parent_children.get(root, [])
        children.sort(key=lambda d: pipeline_order.get(d, 999))

        print(_fmt(root))
        if children:
            for i, child in enumerate(children):
                branch = "  └─ " if i == len(children) - 1 else "  ├─ "
                print(_fmt(child, branch))
            print()
        else:
            print()

    # ── Seção 2: Referências ──────────────────────────────────────────────────
    if DomainType.REFERENCIAS not in bulk_only:
        _section("Referencias")
        print(_fmt(DomainType.REFERENCIAS))
        print()

    # ── Seção 3: Carga Massiva ────────────────────────────────────────────────
    _section("Carga Massiva (Bulk)")
    bulk_sorted = sorted(
        (d for d in bulk_only if d in DOMAIN_LABELS),
        key=lambda d: pipeline_order.get(d, 999),
    )
    for domain in bulk_sorted:
        print(_fmt(domain))

    print()


def _print_audit_coverage() -> None:
    """
    Audita a cobertura dos dados no datalake (Silver e Gold).

    Para cada domínio conhecido, conta registros nas camadas Silver e Gold
    e exibe um status: OK, SILVER APENAS, SEM DADOS ou NUNCA EXTRAÍDO.
    Domínios bulk-only são identificados com marcador (B).
    """
    import duckdb

    from ipolitico.extractors.camara.bulk.registry import BULK_REGISTRY

    DATALAKE = Path("data/datalake")
    conn = duckdb.connect()

    bulk_only: set[DomainType] = {
        DomainType(k) for k, v in BULK_REGISTRY.items() if v.get("bulk_only")
    }

    # Ordena pela pipeline canônica; domínios fora da lista vão ao final
    pipeline_order = {d: i for i, d in enumerate(FULL_PIPELINE)}

    sorted_domains = sorted(DomainType, key=lambda d: pipeline_order.get(d, 9999))

    header = f"{'DOMÍNIO':<36} {'SILVER':>8} {'GOLD':>8}  STATUS"
    print("=" * len(header))
    print(header)
    print("=" * len(header))

    for domain in sorted_domains:
        name = domain.value
        tag = " (B)" if domain in bulk_only else ""
        display_name = name + tag

        silver_dir = DATALAKE / "silver" / name
        gold_dir = DATALAKE / "gold" / name
        gold_file = gold_dir / f"{name}.parquet"

        silver_count = 0
        gold_count = 0

        # Conta Silver (multi-file parquet)
        if silver_dir.is_dir() and list(silver_dir.glob("*.parquet")):
            try:
                silver_count = conn.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{silver_dir}/*.parquet')"
                ).fetchone()[0]
            except Exception:
                silver_count = -1  # erro de leitura

        # Conta Gold (parquet consolidado)
        if gold_file.exists():
            try:
                gold_count = conn.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{gold_file}')"
                ).fetchone()[0]
            except Exception:
                gold_count = -1

        # Determina status
        if gold_count > 0 and silver_count > 0:
            status = "OK"
        elif gold_count > 0 and silver_count == 0:
            status = "OK (gold only)"
        elif gold_count == 0 and silver_count > 0:
            status = "SILVER APENAS"
        elif silver_count == 0 and gold_dir.is_dir():
            status = "DADOS VAZIOS"
        elif silver_dir.is_dir() and not gold_dir.is_dir():
            status = "SILVER APENAS"
        elif silver_count == -1 or gold_count == -1:
            status = "ERRO LEITURA"
        else:
            status = "NUNCA EXTRAÍDO"

        silver_str = f"{silver_count:,}".replace(",", ".") if silver_count >= 0 else "ERR"
        gold_str = f"{gold_count:,}".replace(",", ".") if gold_count >= 0 else "ERR"

        print(f"{display_name:<36} {silver_str:>8} {gold_str:>8}  {status}")

    conn.close()


async def main():
    """
    Ponto de Entrada (CLI).
    Lê os parâmetros do usuário, monta as peças e aciona o Gestor. Nenhuma
    regra de negócio ou IFs de domínio ocorrem aqui.
    """
    parser = argparse.ArgumentParser(description="Motor ETL iPolitico")
    parser.add_argument(
        "--source",
        type=str,
        choices=["camara", "senado", "senado-adm", "all"],
        default="all",
        help="Fonte de dados: camara, senado, senado-adm, ou all (todas em paralelo).",
    )
    parser.add_argument(
        "--list-domains",
        action="store_true",
        help="Lista todos os domínios disponíveis com descrição e hierarquia.",
    )
    parser.add_argument(
        "--audit-coverage",
        action="store_true",
        help="Audita cobertura dos dados: registros em Silver e Gold por domínio.",
    )
    parser.add_argument(
        "--generate-coverage-doc",
        action="store_true",
        help=(
            "Gera docs/cobertura-dados.md a partir do registry de cobertura "
            "do código (datas reais, lacunas, sistema/API de origem)."
        ),
    )
    parser.add_argument(
        "--coverage-doc-output",
        type=str,
        default="docs/cobertura-dados.md",
        help="Caminho de destino do documento de cobertura (com --generate-coverage-doc).",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Executa a consolidação (Camada Gold) via DuckDB após a ingestão.",
    )
    parser.add_argument(
        "--strategy",
        type=LoadStrategy,
        choices=list(LoadStrategy),
        default=LoadStrategy.INCREMENTAL,
    )
    parser.add_argument(
        "--domains",
        action="append",
        nargs="+",
        type=DomainType,
        choices=list(DomainType),
        default=None,
    )
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="Desativa o pré-aquecimento de cache para rotas 504-prone.",
    )
    parser.add_argument(
        "--export-gold",
        type=str,
        choices=["sqlite", "duckdb"],
        default=None,
        help="Exporta a camada Gold para banco SQL (sqlite ou duckdb) após a ingestão.",
    )
    parser.add_argument(
        "--build-entidade-canonica",
        action="store_true",
        help=(
            "Constrói as tabelas Gold de identidade (politicos, politicos_aliases, "
            "resolucoes) a partir dos Silver ingeridos e deduplica (issue 01)."
        ),
    )
    parser.add_argument(
        "--build-custo-erario",
        action="store_true",
        help=(
            "Constrói as Gold de custo ao erário (custo_erario, observacoes_metricas) "
            "a partir dos Silver + aliases e deduplica (issue 02)."
        ),
    )

    args = parser.parse_args()

    if args.list_domains:
        _print_domain_tree()
        return

    if args.audit_coverage:
        _print_audit_coverage()
        return

    if args.generate_coverage_doc:
        from ipolitico.core.coverage_doc import generate_coverage_doc

        output = Path(args.coverage_doc_output)
        generate_coverage_doc(output)
        print(f"Documento de cobertura gerado em: {output}")
        return

    # Modo somente-build: sem ingestão, só Gold (issues 01/02). Com ``--domains``
    # o build roda após a ingestão (ver fluxo principal).
    if (args.build_entidade_canonica or args.build_custo_erario) and args.domains is None:
        _run_gold_builds(args)
        return

    if args.domains is None:
        args.domains = list(DomainType)
    else:
        args.domains = [d for group in args.domains for d in group]
    args.domains = expand_domains_with_dependencies(args.domains)

    start_time = time.perf_counter()

    # Seleciona componentes com base na fonte
    source_name = args.source
    if source_name == "camara":
        providers_configs = ["camara"]
    elif source_name == "senado":
        providers_configs = ["senado"]
    elif source_name == "senado-adm":
        providers_configs = ["senado-adm"]
    else:  # all
        providers_configs = ["camara", "senado", "senado-adm"]
    logger.info("=" * 60)
    logger.info(
        f" iPolitico ETL (Ingestão) | Destino: DATALAKE  |"
        f" Estratégia: {args.strategy.value.upper()}",
    )
    logger.info("=" * 60)

    # Carregar Configurações
    base_dir = Path(__file__).resolve().parent.parent.parent / "configs"
    camara_config = load_config(base_dir / "camara_pipeline.yaml")
    senado_config = load_config(base_dir / "senado_pipeline.yaml")
    senado_adm_config = load_config(base_dir / "senado_adm_pipeline.yaml")

    runner = PipelineRunner()
    state_store = DataLakeSink()

    providers = []

    if "camara" in providers_configs:
        from ipolitico.services.metadata import CamaraMetadataService
        from ipolitico.sources.camara_provider import CamaraSourceProvider

        camara_client = CamaraClient()
        camara_builder = PipelineBuilder(camara_client)
        camara_metadata = CamaraMetadataService(camara_client)
        camara_manager = PipelineManager(
            camara_builder, runner, camara_config, state_store, camara_metadata
        )
        providers.append(CamaraSourceProvider(camara_manager))

    if "senado" in providers_configs:
        from ipolitico.core.senado_client import SenadoClient
        from ipolitico.services.senado_metadata import SenadoMetadataService
        from ipolitico.sources.senado_provider import SenadoSourceProvider

        senado_client = SenadoClient()
        senado_builder = PipelineBuilder(senado_client)
        senado_metadata = SenadoMetadataService()
        senado_manager = PipelineManager(
            senado_builder, runner, senado_config, state_store, senado_metadata
        )
        providers.append(SenadoSourceProvider(senado_manager))

    if "senado-adm" in providers_configs:
        from ipolitico.core.senado_adm_client import SenadoAdmClient
        from ipolitico.services.senado_metadata import SenadoMetadataService
        from ipolitico.sources.senado_adm_provider import SenadoAdmSourceProvider

        senado_adm_client = SenadoAdmClient()
        senado_adm_builder = PipelineBuilder(senado_adm_client)
        senado_adm_metadata = SenadoMetadataService()
        senado_adm_manager = PipelineManager(
            senado_adm_builder, runner, senado_adm_config, state_store, senado_adm_metadata
        )
        providers.append(SenadoAdmSourceProvider(senado_adm_manager))

    federation = FederationOrchestrator(providers)

    try:
        await federation.run_all(
            args.domains,
            args.strategy,
            SinkType.DATALAKE,
            args.start_date,
            args.end_date,
            warmup=not args.no_warmup,
        )

        if args.optimize:
            for domain in args.domains:
                logger.info(f"=== Otimizando Camada Gold para {domain.value.upper()} ===")
                DataLakeOptimizer().compact_and_deduplicate(domain.value)

        if args.build_entidade_canonica or args.build_custo_erario:
            _run_gold_builds(args)

        if args.export_gold:
            fmt = ExportFormat(args.export_gold)
            ext = "db" if fmt == ExportFormat.SQLITE else "duckdb"
            output = Path(f"data/gold_export.{ext}")
            logger.info("=== Exportando Gold para %s ===", output)
            GoldExporter().export_all(str(output), format=fmt)
    except Exception as e:
        logger.error(f"Falha catastrófica no ETL: {e}")
    finally:
        for p in providers:
            if (
                hasattr(p, "_manager")
                and hasattr(p._manager, "builder")
                and p._manager.builder.client
            ):
                maybe_client = p._manager.builder.client
                if hasattr(maybe_client, "close"):
                    await maybe_client.close()
        logger.info(f"Tempo total de execução: {time.perf_counter() - start_time:.2f}s")


def _run_gold_builds(args: argparse.Namespace) -> None:
    """Executa os builders Gold (issues 01/02) e a dedup das tabelas novas.

    Roda os builders contra os Silver/Gold já persistidos (não faz ingestão),
    imprime o relatório de cobertura e deduplica as tabelas Gold produzidas com
    ``pk_cols`` explícito (a dedup é responsabilidade da camada Gold).

    Args:
        args: Namespace do argparse com as flags ``--build-*``.
    """
    optimizer = DataLakeOptimizer()
    if args.build_entidade_canonica:
        logger.info("=== Construindo entidade canônica (Gold, issue 01) ===")
        builder = EntidadeCanonicaBuilder()
        builder.build()
        _imprimir_cov_entidade(builder.cobertura())
        for tabela, pk in (
            ("politicos", POLITICOS_PK),
            ("politicos_aliases", ALIASES_PK),
            ("resolucoes", RESOLUCOES_PK),
        ):
            logger.info("=== Deduplicando Gold %s ===", tabela.upper())
            optimizer.compact_and_deduplicate(
                tabela,
                source_layer=MedallionLayer.GOLD,
                target_layer=MedallionLayer.GOLD,
                pk_cols=", ".join(pk),
            )
    if args.build_custo_erario:
        logger.info("=== Construindo custo ao erário (Gold, issue 02) ===")
        builder = CustoErarioBuilder()
        builder.build()
        _imprimir_cov_custo(builder.cobertura())
        for tabela, pk in (
            ("custo_erario", CUSTO_PK),
            ("observacoes_metricas", OBS_PK),
        ):
            logger.info("=== Deduplicando Gold %s ===", tabela.upper())
            optimizer.compact_and_deduplicate(
                tabela,
                source_layer=MedallionLayer.GOLD,
                target_layer=MedallionLayer.GOLD,
                pk_cols=", ".join(pk),
            )


def _imprimir_cov_entidade(cov: CoberturaEntidadeCanonica) -> None:
    """Imprime o relatório de cobertura da entidade canônica (issue 01).

    Args:
        cov: Relatório de cobertura do ``EntidadeCanonicaBuilder``.
    """
    print(f"  políticos únicos: {cov.total_politicos}")
    print(f"  aliases: {cov.total_aliases} por fonte: {cov.aliases_por_fonte}")
    print(f"  âncoras camara: {cov.ancoras_camara} | senado: {cov.ancoras_senado}")
    print(
        f"  resoluções confirmadas: {cov.resolucoes_confirmadas} | "
        f"candidatas a revisão: {cov.resolucoes_candidatas_revisao}"
    )


def _imprimir_cov_custo(cov: CoberturaCustoErario) -> None:
    """Imprime o relatório de cobertura do custo ao erário (issue 02).

    Args:
        cov: Relatório de cobertura do ``CustoErarioBuilder``.
    """
    print(f"  linhas custo_erario: {cov.total_linhas} por componente: {cov.total_por_componente}")
    print(f"  por casa: {cov.total_por_casa}")
    print(f"  observações registradas: {cov.total_observacoes}")


def main_cli():
    """Entry point para console_scripts (``ipolitico`` no terminal)."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
