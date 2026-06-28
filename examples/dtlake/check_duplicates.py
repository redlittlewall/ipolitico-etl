from pathlib import Path

import duckdb
from ipolitico.core.constants import ApiParams, DomainType, MedallionLayer

# Apontando para a base correta da Arquitetura Medallion
GOLD_PATH = Path("data/datalake") / MedallionLayer.GOLD.value


def check_table(conn: duckdb.DuckDBPyConnection, table_name: str, keys: list[str]):
    path = GOLD_PATH / table_name / f"{table_name}.parquet"

    if not path.exists():
        print(f"[{table_name.upper()}] ⚠️ Ignorado: Arquivo Gold não encontrado em {path}")
        return

    # Formata as chaves para o SQL
    key_str = ", ".join(keys)

    # Query de detecção de duplicidade (Conta agrupamentos com mais de 1 linha)
    query = f"""
        SELECT COUNT(*) as grupos_duplicados
        FROM (
            SELECT {key_str}, COUNT(*)
            FROM read_parquet('{path}')
            GROUP BY {key_str}
            HAVING COUNT(*) > 1
        )
    """

    try:
        count = conn.execute(query).fetchone()[0]
        if count == 0:
            print(f"[{table_name.upper().ljust(15)}] ✅ STATUS: LIMPO (Unicidade Garantida)")
        else:
            print(
                f"[{table_name.upper().ljust(15)}] ❌ STATUS:{count} CHAVES DUPLICADAS ENCONTRADAS!"
            )

            # Exibe uma amostra do lixo para depuração se falhar
            amostra_query = f"""
                SELECT {key_str}, COUNT(*) as repeticoes
                FROM read_parquet('{path}')
                GROUP BY {key_str}
                HAVING COUNT(*) > 1
                LIMIT 3
            """
            amostra = conn.execute(amostra_query).df()
            print(f"Exemplo do problema:\n{amostra}")

    except duckdb.Error as e:
        print(f"[{table_name.upper()}] 🚨 Erro SQL ao validar schema: {e}")


def main():
    print("=" * 60)
    print(" 🛡️  AUDITORIA DE DATA QUALITY: UNICIDADE DA CAMADA GOLD")
    print("=" * 60)

    conn = duckdb.connect()

    # Mapeamento do Contrato de Dados: Entidade -> Array de Primary Keys
    col_dep_id = ApiParams.DEPUTADO_ID.value

    validacoes = [
        (DomainType.DEPUTADOS.value, [ApiParams.ID.value]),
        (DomainType.PROPOSICOES.value, [ApiParams.ID.value]),
        (DomainType.VOTACOES.value, [ApiParams.ID.value]),
        ("votos", ["votacao_id", col_dep_id]),
        (
            DomainType.DESPESAS.value,
            [col_dep_id, "numDocumento", "codDocumento", "parcela", "valorLiquido"],
        ),
    ]

    for tabela, chaves in validacoes:
        check_table(conn, tabela, chaves)

    conn.close()


if __name__ == "__main__":
    main()
