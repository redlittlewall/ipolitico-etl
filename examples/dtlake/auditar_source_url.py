#!/usr/bin/env python3
"""
Script de Auditoria de Cobertura _source_url na Camada Gold.

Varre todos os parquets Gold, conta registros com _source_url nulo por
domínio e gera relatório de cobertura (% com URL vs sem). Amostra URLs
inválidas ou mal formatadas quando encontradas.

Uso:
    python examples/dtlake/auditar_source_url.py
    python examples/dtlake/auditar_source_url.py --min-coverage 95
    python examples/dtlake/auditar_source_url.py --sample-size 5
"""

import argparse
import sys
from pathlib import Path

import duckdb

GOLD_DIR = Path("data/datalake/gold")


def auditar_cobertura_source_url(min_coverage: float = 100.0, sample_size: int = 3) -> int:
    """
    Audita a cobertura de _source_url em todos os domínios da camada Gold.

    Para cada domínio, conta registros totais, registros com _source_url
    não-nulo e calcula o percentual de cobertura. Quando cobertura é
    inferior a ``min_coverage``%, exibe amostras de registros com URL nula
    ou mal formatada.

    Args:
        min_coverage: Percentual mínimo aceitável (padrão 100.0). Domínios
            abaixo deste valor disparam aviso e fazem o script retornar
            código 1.
        sample_size: Número de amostras de URLs inválidas/nulas a exibir
            por domínio com problema (padrão 3).

    Returns:
        0 se todos os domínios estão >= min_coverage, 1 caso contrário.
    """
    conn = duckdb.connect()

    dominios = sorted(
        d.name for d in GOLD_DIR.iterdir() if d.is_dir() and (d / f"{d.name}.parquet").exists()
    )

    if not dominios:
        print("❌ Nenhum domínio Gold encontrado para auditoria.")
        conn.close()
        return 1

    print("=" * 80)
    print(" 🧾 AUDITORIA DE COBERTURA _source_url — CAMADA GOLD")
    print(f"    Data: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Cabeçalho da tabela
    header = f"{'DOMÍNIO':<32} {'TOTAL':>10} {'COM URL':>10} {'SEM URL':>10} {'% COBERTURA':>12}"
    print(f"\n{header}")
    print("-" * len(header))

    resultados: list[dict] = []
    exit_code = 0
    dominios_baixa_cobertura: list[tuple[str, float]] = []

    for dominio in dominios:
        parquet_path = GOLD_DIR / dominio / f"{dominio}.parquet"

        try:
            # Total de registros
            total = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')").fetchone()[
                0
            ]

            # Registros com _source_url não-nulo
            com_url = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{parquet_path}') "
                f"WHERE _source_url IS NOT NULL AND _source_url != ''"
            ).fetchone()[0]

            sem_url = total - com_url
            pct = (com_url / total * 100) if total > 0 else 0.0

            resultados.append(
                {
                    "dominio": dominio,
                    "total": total,
                    "com_url": com_url,
                    "sem_url": sem_url,
                    "pct": pct,
                }
            )

            # Formatação para exibição
            pct_str = f"{pct:5.1f}%"
            if pct >= 99.99:
                pct_str = " 100.0%"
            elif pct < min_coverage:
                dominios_baixa_cobertura.append((dominio, pct))

            print(f"{dominio:<32} {total:>10,} {com_url:>10,} {sem_url:>10,} {pct_str:>12}")

        except Exception as e:
            print(f"{dominio:<32} {'ERRO':>10} {'':>10} {'':>10} {str(e):>12}")
            continue

    # ── Totais agregados ──────────────────────────────────────────
    total_geral = sum(r["total"] for r in resultados)
    com_url_geral = sum(r["com_url"] for r in resultados)
    sem_url_geral = total_geral - com_url_geral
    pct_geral = (com_url_geral / total_geral * 100) if total_geral > 0 else 0.0

    print("-" * len(header))
    print(
        f"{'TOTAL GERAL':<32} {total_geral:>10,} {com_url_geral:>10,} "
        f"{sem_url_geral:>10,} {pct_geral:5.1f}%".rjust(len(header))
    )
    print()

    # ── Amostras de problemas ────────────────────────────────────
    if dominios_baixa_cobertura:
        print(f"\n⚠️  DOMÍNIOS COM COBERTURA ABAIXO DE {min_coverage:.0f}%:\n")
        for dominio, pct in sorted(dominios_baixa_cobertura, key=lambda x: x[1]):
            print(f"  {dominio:<30} {pct:5.1f}%")
            if sem_url > 0:
                _mostrar_amostras(conn, GOLD_DIR / dominio / f"{dominio}.parquet", sample_size)
            print()
        exit_code = 1

    # ── Resumo executivo ──────────────────────────────────────────
    if dominios_baixa_cobertura:
        print(
            f"\n❌ {len(dominios_baixa_cobertura)} domínio(s) abaixo de "
            f"{min_coverage:.0f}% de cobertura."
        )
    else:
        print(f"✅ Todos os {len(dominios)} domínios com cobertura >= {min_coverage:.0f}%.")

    conn.close()
    return exit_code


def _mostrar_amostras(
    conn: duckdb.DuckDBPyConnection, parquet_path: Path, sample_size: int
) -> None:
    """
    Exibe amostras de registros com _source_url nulo/inválido.

    Args:
        conn: Conexão DuckDB.
        parquet_path: Caminho do arquivo parquet.
        sample_size: Número de amostras a exibir.
    """
    try:
        amostras = conn.execute(
            f"SELECT _source_url, * EXCLUDE (_source_url) "
            f"FROM read_parquet('{parquet_path}') "
            f"WHERE _source_url IS NULL OR _source_url = '' "
            f"LIMIT {sample_size}"
        ).fetchdf()

        if not amostras.empty:
            # Mostra apenas as colunas mais relevantes (primeiras 3)
            cols = amostras.columns.tolist()
            display_cols = ["_source_url"] + [c for c in cols if c != "_source_url"][:3]
            print(f"    Amostras (até {sample_size} registros sem URL):")
            for _, row in amostras[display_cols].head(sample_size).iterrows():
                vals = " | ".join(str(row[c])[:60] for c in display_cols[1:3])
                print(f"      _source_url={row['_source_url']!r} | {vals}")
    except Exception as e:
        print(f"    (erro ao obter amostras: {e})")


def main() -> int:
    """Entry point com parsing de argumentos CLI."""
    parser = argparse.ArgumentParser(description="Audita cobertura de _source_url na camada Gold.")
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=100.0,
        help="Percentual mínimo aceitável (padrão: 100.0).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=3,
        help="Amostras por domínio com problema (padrão: 3).",
    )
    args = parser.parse_args()
    return auditar_cobertura_source_url(args.min_coverage, args.sample_size)


if __name__ == "__main__":
    sys.exit(main())
