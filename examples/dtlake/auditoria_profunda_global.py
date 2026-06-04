"""Auditoria Profunda de Schema e Volumetria — Camada Gold.

Varre todos os domínios gold e exibe schema, amostra e contagem.
Domínios utilizados: todos os disponíveis na camada Gold
"""

from pathlib import Path

import duckdb

DATALAKE_PATH = Path("data/datalake/gold")


def auditoria_global():
    print("=" * 80)
    print(" 🔎 AUDITORIA PROFUNDA DE SCHEMA E VOLUMETRIA - iPolitico")
    print("=" * 80)

    conn = duckdb.connect()
    gold_dirs = sorted(DATALAKE_PATH.glob("*/"))
    parquet_files = []
    for d in gold_dirs:
        parq = list(d.glob("*.parquet"))
        parquet_files.extend(parq)

    if not parquet_files:
        print(f"Erro: Nenhum arquivo encontrado em {DATALAKE_PATH}")
        return

    for path in sorted(parquet_files):
        tabela = path.parent.name
        print(f"\n📊 TABELA: {tabela.upper()}")
        print("-" * 40)

        try:
            schema_info = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").df()
            print("--- Estrutura (Top 5 colunas):")
            print(schema_info[["column_name", "column_type"]].head(5).to_markdown(index=False))

            amostra = conn.execute(f"SELECT * FROM read_parquet('{path}') LIMIT 3").df()
            print("\n--- Amostra de Dados:")
            print(amostra.astype(str).to_markdown(index=False))

            total = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
            print(f"\n✅ Total de Registros: {total:,}".replace(",", "."))
            print("." * 80)

        except Exception as e:
            print(f"❌ Erro ao analisar {tabela}: {e}")


if __name__ == "__main__":
    auditoria_global()
