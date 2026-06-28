#!/usr/bin/env python3
"""Estima requisições HTTP e tempo de parede para ingestão na API da Câmara."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipolitico.core.constants import DomainType, LoadStrategy  # noqa: E402
from ipolitico.tools.ingestion_estimate import (  # noqa: E402
    estimate_camara_ingestion,
    estimate_full_history_api_only,
    estimate_full_history_hybrid,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimativa de carga HTTP — API Câmara")
    parser.add_argument(
        "--scenario",
        choices=("custom", "full-api", "full-hybrid"),
        default="full-hybrid",
    )
    parser.add_argument("--start-date", default="2009-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument(
        "--domains",
        nargs="+",
        type=DomainType,
        default=list(DomainType),
        choices=list(DomainType),
    )
    parser.add_argument("--strategy", type=LoadStrategy, default=LoadStrategy.FULL_LOAD)
    parser.add_argument("--deputados", type=int, default=513, help="Universo de deputados (API)")
    args = parser.parse_args()

    if args.scenario == "full-api":
        est = estimate_full_history_api_only()
    elif args.scenario == "full-hybrid":
        est = estimate_full_history_hybrid()
    else:
        est = estimate_camara_ingestion(
            args.domains,
            args.start_date,
            args.end_date,
            args.strategy,
            deputy_count=args.deputados,
        )

    print("=== iPolitico — estimativa de ingestão (Câmara) ===\n")
    for line in est.summary_lines():
        print(line)
    print(
        "\nNotas: votos depende do volume real de votações; use telemetria local "
        "(data/dbs/api_telemetry.db) para calibrar latência. Prefira BULK em despesas/"
        "proposições/votações para histórico multi-ano."
    )


if __name__ == "__main__":
    main()
