#!/usr/bin/env python3
"""
Auditoria completa do Data Lake iPolitico.

Varre os 60 domínios, conta registros em Silver e Gold, identifica gaps,
anomalias de schema, e gera um relatório consolidado.
"""

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ipolitico.core.constants import DomainType

DATALAKE = Path("data/datalake").resolve()


def count_parquet(conn: duckdb.DuckDBPyConnection, path: Path) -> int:
    """Conta registros em um diretório/arquivo parquet."""
    if not path.exists():
        return 0
    try:
        pattern = str(path / "*.parquet") if path.is_dir() else str(path)
        return conn.execute(f"SELECT COUNT(*) FROM read_parquet('{pattern}')").fetchone()[0]
    except Exception:
        return -1


def count_gold_parquet(conn: duckdb.DuckDBPyConnection, domain: str) -> int:
    """Conta registros no Gold consolidado."""
    gold_file = DATALAKE / "gold" / domain / f"{domain}.parquet"
    return count_parquet(conn, gold_file)


def count_silver_parquet(conn: duckdb.DuckDBPyConnection, domain: str) -> int:
    """Conta registros no Silver (multi-file)."""
    silver_dir = DATALAKE / "silver" / domain
    return count_parquet(conn, silver_dir)


def main():
    conn = duckdb.connect()

    domains = sorted(set(d.value for d in DomainType))

    # ── Descobrir o que existe de fato em disco ────────────────────────────
    silver_on_disk = {d.name for d in (DATALAKE / "silver").iterdir() if d.is_dir()}
    gold_on_disk = {d.name for d in (DATALAKE / "gold").iterdir() if d.is_dir()}
    both = silver_on_disk & gold_on_disk
    only_silver = silver_on_disk - gold_on_disk
    only_gold = gold_on_disk - silver_on_disk

    # ── Domínios do enum que nunca foram extraídos ─────────────────────────
    all_covered = silver_on_disk | gold_on_disk
    never_extracted = sorted(set(domains) - all_covered)

    print("=" * 110)
    print("AUDITORIA COMPLETA DO DATA LAKE — iPolitico ETL")
    print("=" * 110)
    print(f"\nDomínios definidos no DomainType: {len(domains)}")
    print(f"Domínios em disco (Silver+Gold): {len(all_covered)}/{len(domains)}")

    if never_extracted:
        print(f"\n❌ NUNCA EXTRAÍDOS ({len(never_extracted)}):")
        for d in never_extracted:
            print(f"   - {d}")

    if only_silver:
        print(f"\n🔷 APENAS SILVER ({len(only_silver)}):")
        for d in sorted(only_silver):
            print(f"   - {d}")

    if only_gold:
        print(f"\n🔶 APENAS GOLD ({len(only_gold)}):")
        for d in sorted(only_gold):
            print(f"   - {d}")

    if not never_extracted and not only_silver and not only_gold:
        print("\n✅ TODOS OS 60 DOMÍNIOS COBERTOS em Silver E Gold!")

    # ── Contagem de registros ──────────────────────────────────────────────
    print()
    print("-" * 110)
    print(f"{'DOMÍNIO':<32} {'SILVER':>14} {'GOLD':>14} {'DIF':>10}  {'STATUS'}")
    print("-" * 110)

    total_s = 0
    total_g = 0
    high_diff_domains = []

    for domain in sorted(both):
        s = count_silver_parquet(conn, domain)
        g = count_gold_parquet(conn, domain)
        total_s += max(s, 0)
        total_g += max(g, 0)

        if s >= 0 and g >= 0:
            diff = s - g
            if abs(diff) > 500:
                status = "⚠️  DIF ALTA"
                high_diff_domains.append((domain, diff))
            elif diff == 0:
                status = "✅"
            else:
                status = "~"
            s_str = f"{s:,}"
            g_str = f"{g:,}"
            d_str = f"{diff:,}"
        else:
            status = "❌ ERRO"
            s_str = str(s)
            g_str = str(g)
            d_str = "N/A"

        print(f"{domain:<32} {s_str:>14} {g_str:>14} {d_str:>10}  {status}")

    # Domínios só Silver
    for domain in sorted(only_silver):
        s = count_silver_parquet(conn, domain)
        total_s += max(s, 0)
        s_str = f"{s:,}" if s >= 0 else str(s)
        print(f"{domain:<32} {s_str:>14} {'N/A':>14} {'N/A':>10}  🔷 S/Silver")

    # Domínios só Gold
    for domain in sorted(only_gold):
        g = count_gold_parquet(conn, domain)
        total_g += max(g, 0)
        g_str = f"{g:,}" if g >= 0 else str(g)
        print(f"{domain:<32} {'N/A':>14} {g_str:>14} {'N/A':>10}  🔶 S/Gold")

    print("-" * 110)
    print(f"{'TOTAL GERAL':<32} {total_s:>14,} {total_g:>14,}")
    print()

    if high_diff_domains:
        print("⚠️  DOMÍNIOS COM DIFERENÇA SILVER-GOLD > 500:")
        for d, diff in high_diff_domains:
            print(
                f"   - {d}: diff={diff:,} (Silver tem mais que Gold — normal se "
                f"Gold não foi otimizado recentemente)"
            )

    # ── Amostragem de schemas ──────────────────────────────────────────────
    print()
    print("=" * 110)
    print("AMOSTRA DE SCHEMAS (primeiros 5 domínios)")
    print("=" * 110)
    for domain in sorted(both)[:5]:
        silver_dir = DATALAKE / "silver" / domain
        if silver_dir.is_dir() and list(silver_dir.glob("*.parquet")):
            try:
                schema = conn.execute(
                    f"DESCRIBE SELECT * FROM read_parquet('{silver_dir}/*.parquet') LIMIT 0"
                ).fetchdf()
                print(f"\n--- {domain} (Silver) ---")
                print(f"Colunas: {len(schema)}")
            except Exception as e:
                print(f"\n--- {domain} (Silver) — ERRO: {e}")

    conn.close()


if __name__ == "__main__":
    main()
