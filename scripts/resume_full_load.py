#!/usr/bin/env python3
"""
Retomada de Execução ETL Interrompida.

1. Otimiza Gold para 6 domínios que já têm Silver completo
2. Executa extração de 9 domínios nunca extraídos
3. Otimiza Gold para os novos domínios
4. Audit final de cobertura
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Garante que o src está no path (partindo de scripts/ → raiz do projeto)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ipolitico.core.client import CamaraClient  # noqa: E402

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType  # noqa: E402
from ipolitico.pipeline.builder import PipelineBuilder  # noqa: E402
from ipolitico.pipeline.federation import FederationOrchestrator  # noqa: E402
from ipolitico.pipeline.manager import PipelineManager  # noqa: E402
from ipolitico.pipeline.optimizer import DataLakeOptimizer  # noqa: E402
from ipolitico.pipeline.runner import PipelineRunner  # noqa: E402
from ipolitico.sinks.datalake_sink import DataLakeSink  # noqa: E402
from ipolitico.sources.camara_provider import CamaraSourceProvider  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("resume")


# Domínios que já têm Silver completo — só otimizar Gold
SILVER_ONLY = [
    DomainType.PROPOSICOES,
    DomainType.TRAMITACOES,
    DomainType.AUTORES,
    DomainType.RELACIONADAS,
    DomainType.TEMAS,
    DomainType.VOTACOES,
]

# Domínios nunca extraídos — executar FULL_LOAD
UNEXTRACTED = [
    DomainType.PROPOSICOES_VOTACOES,
    DomainType.DISCURSOS,
    DomainType.ORGAOS_VOTACOES,
    DomainType.PARTIDOS_LIDERES,
    DomainType.VOTACOES_DETALHE,
    DomainType.VOTOS,
    DomainType.ORIENTACOES,
    DomainType.REFERENCIAS,
    DomainType.PROPOSICOES_DETALHE,
]


def optimize_gold(domains: list[DomainType], label: str) -> float:
    """Otimiza Silver → Gold para lista de domínios."""
    optimizer = DataLakeOptimizer()
    start = time.perf_counter()
    for domain in domains:
        ts = time.perf_counter()
        print(f"  → [{label}] Otimizando {domain.value}...", end=" ", flush=True)
        try:
            optimizer.compact_and_deduplicate(domain.value)
            print(f"OK ({time.perf_counter() - ts:.1f}s)")
        except Exception as e:
            print(f"ERRO: {e}")
    elapsed = time.perf_counter() - start
    print(f"  ✔ [{label}] Concluído em {elapsed:.1f}s\n")
    return elapsed


async def extract_domains(domains: list[DomainType]) -> float:
    """Executa o pipeline ETL para os domínios especificados."""
    config_path = PROJECT_ROOT / "configs" / "camara_pipeline.yaml"
    import yaml

    with open(config_path) as f:
        pipeline_config = yaml.safe_load(f)

    client = CamaraClient()
    builder = PipelineBuilder(client)
    runner = PipelineRunner()
    state_store = DataLakeSink()
    manager = PipelineManager(builder, runner, pipeline_config, state_store)
    federation = FederationOrchestrator([CamaraSourceProvider(manager)])

    start = time.perf_counter()
    try:
        await federation.run_all(
            domains=domains,
            strategy=LoadStrategy.FULL_LOAD,
            sink_type=SinkType.DATALAKE,
            start_date=None,
            end_date=None,
        )
    except Exception as e:
        logger.error(f"Falha na extração: {e}")
    finally:
        await client.close()
    elapsed = time.perf_counter() - start
    print(f"  ✔ Extração concluída em {elapsed:.1f}s\n")
    return elapsed


async def main():
    print("=" * 70)
    print("  iPolitico ETL — Retomada de Execução Interrompida")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    all_start = time.perf_counter()

    # ─────────────────────────────────────────────
    # Passo 1: Otimizar Gold (Silver-only domains)
    # ─────────────────────────────────────────────
    print("\n▸ Passo 1/3: Otimizando Gold para 6 domínios com Silver completo\n")
    t1 = optimize_gold(SILVER_ONLY, "Silver-only")

    # ─────────────────────────────────────────────
    # Passo 2: Extrair domínios nunca extraídos
    # ─────────────────────────────────────────────
    print("▸ Passo 2/3: Extraindo 9 domínios nunca extraídos\n")
    t2 = await extract_domains(UNEXTRACTED)

    # ─────────────────────────────────────────────
    # Passo 3: Otimizar Gold (novos domínios)
    # ─────────────────────────────────────────────
    print("▸ Passo 3/3: Otimizando Gold para novos domínios\n")
    t3 = optimize_gold(UNEXTRACTED, "Novos")

    # ─────────────────────────────────────────────
    # Resumo
    # ─────────────────────────────────────────────
    total = time.perf_counter() - all_start
    print("=" * 70)
    print("  RESUMO DA RETOMADA")
    print(f"  Otimizar Gold (pré-existente):  {t1:.1f}s")
    print(f"  Extrair domínios faltantes:     {t2:.1f}s")
    print(f"  Otimizar Gold (novos):          {t3:.1f}s")
    print("  ─────────────────────────────────────")
    print(f"  TOTAL:                           {total:.1f}s ({total / 60:.1f}min)")
    print(f"  Hora de término:                {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Audit final
    print("\n▸ Auditoria de cobertura final:\n")
    import subprocess

    subprocess.run([sys.executable, "-m", "ipolitico.main", "--audit-coverage"])

    print("\n✔ Retomada concluída com sucesso!")


if __name__ == "__main__":
    asyncio.run(main())
