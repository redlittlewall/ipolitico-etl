"""Inventário e documentação do Datalake iPolitico — Camada Gold.

Domínios utilizados: todos os disponíveis na camada Gold
"""

from pathlib import Path

import duckdb

DATALAKE_PATH = Path("data/datalake/gold")


def gerar_inventario_datalake():
    print("=" * 80)
    print(" 📑 INVENTÁRIO E DOCUMENTAÇÃO DO DATALAKE iPOLITICO")
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

        print(f"\n📂 ENTIDADE: {tabela.upper()}")
        print(f"   ∟ Arquivo: {path}")

        stats = conn.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT captured_at) as cargas"
            f" FROM read_parquet('{path}')"
        ).fetchone()
        print(f"   ∟ Total de Registros: {stats[0]}")
        print(f"   ∟ Histórico de Sincronizações: {stats[1]}")

        print("   ∟ Dicionário de Dados (Atributos encontrados):")
        cols = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").df()

        for _, row in cols.iterrows():
            tag = "[ID/CHAVE]" if "id" in row["column_name"].lower() else ""
            tag = "[MOEDA]" if "valor" in row["column_name"].lower() else tag
            tag = (
                "[URL/LINK]"
                if "url" in row["column_name"].lower() or "uri" in row["column_name"].lower()
                else tag
            )

            print(f"      - {row['column_name']:20} | {row['column_type']:10} {tag}")

    print("\n" + "=" * 80)
    print(" Dica: Use estes IDs e URLs para cruzar com a documentação oficial do Swagger.")


if __name__ == "__main__":
    gerar_inventario_datalake()
