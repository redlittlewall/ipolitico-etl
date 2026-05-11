from pathlib import Path

import duckdb

DATALAKE_PATH = Path("datalake")


def check_table(conn, table_name, keys):
    path = DATALAKE_PATH / f"{table_name}.parquet"
    if not path.exists():
        return

    # Esta query identifica se existem combinações de chaves que aparecem mais de uma vez
    key_str = ", ".join(keys)
    query = f"""
        SELECT COUNT(*) as duplicados
        FROM (
            SELECT {key_str}, COUNT(*)
            FROM '{path}'
            GROUP BY {key_str}
            HAVING COUNT(*) > 1
        )
    """
    count = conn.execute(query).fetchone()[0]
    status = "✅ LIMPO" if count == 0 else f"❌ {count} GRUPOS DUPLICADOS"
    print(f"{table_name.ljust(30)}: {status}")


def main():
    conn = duckdb.connect()
    print("=== AUDITORIA DE INTEGRIDADE (DUPLICIDADE) ===\n")

    # Mapeamento de Tabela -> Chaves que deveriam ser únicas
    validacoes = [
        ("deputados", ["id"]),
        ("deputados_discursos", ["id_deputado", "dataHoraInicio"]),
        ("deputados_frentes", ["id_deputado", "id"]),
        ("votacoes", ["id"]),
        ("votos", ["idVotacao", "deputado_id"]),
        (
            "despesas_old",
            ["codDocumento", "numParcela", "id_deputado", "dataDocumento", "valorLiquido"],
        ),
    ]

    for tabela, chaves in validacoes:
        check_table(conn, tabela, chaves)


if __name__ == "__main__":
    main()
