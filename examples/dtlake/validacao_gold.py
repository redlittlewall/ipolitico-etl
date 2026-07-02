from pathlib import Path

import duckdb
import pandas as pd

from ipolitico.core.schemas import DESPESAS_PARTITION_KEYS

# Aponta para o diretório Gold que o Optimizer gerou
GOLD_DIR = Path("data/datalake/gold")


def validar_camada_gold():
    print("=" * 70)
    print(" 🏛️ AUDITORIA DA CAMADA GOLD (CIVIC TECH) ")
    print("=" * 70)

    # Inicia o DuckDB em memória (Custo Zero)
    conn = duckdb.connect()

    # Mapeamento dos arquivos
    despesas_path = GOLD_DIR / "despesas" / "despesas.parquet"
    deputados_path = GOLD_DIR / "deputados" / "deputados.parquet"

    if not despesas_path.exists():
        print(f"❌ Erro: Arquivo de despesas não encontrado em {despesas_path}")
        return

    # ---------------------------------------------------------
    # 1. VALIDAÇÃO DE TIPAGEM (SCHEMA)
    # ---------------------------------------------------------
    print("\n[1] 📊 Validação de Tipagem (Despesas):")
    schema = conn.execute(f"DESCRIBE SELECT * FROM '{despesas_path}'").df()
    # Verifica como o motor entende o valor financeiro
    tipo_valor = schema[schema["column_name"] == "valorLiquido"]["column_type"].values[0]
    print(f"Tipo da coluna 'valorLiquido': {tipo_valor} ", end="")
    if "DOUBLE" in str(tipo_valor).upper() or "FLOAT" in str(tipo_valor).upper():
        print("✅ (Pronto para cálculos matemáticos!)")
    else:
        print("❌ (PERIGO: Tipagem incorreta para moeda!)")

    # ---------------------------------------------------------
    # 2. TESTE DE DEDUPLICAÇÃO (INTEGRIDADE)
    # ---------------------------------------------------------
    print("\n[2] 🔍 Teste de Integridade (Duplicatas — PK Gold):")
    pk_cols = ", ".join(DESPESAS_PARTITION_KEYS)
    query_duplicatas = f"""
        SELECT {pk_cols}, COUNT(*) as qtd
        FROM '{despesas_path}'
        WHERE codDocumento IS NOT NULL
        GROUP BY {pk_cols}
        HAVING COUNT(*) > 1
    """
    duplicatas = conn.execute(query_duplicatas).df()
    if duplicatas.empty:
        print("✅ Camada Gold blindada! O otimizador removeu todas as duplicatas.")
    else:
        print(f"❌ ATENÇÃO: Encontrados {len(duplicatas)} grupos de chaves duplicadas.")
        print("\n🧐 MODO ADVOGADO DO DIABO: Inspecionando as linhas reais de 2 casos suspeitos...")

        # Puxamos as colunas críticas (Datas e Valores) das 2 primeiras chaves duplicadas
        query_exemplos = f"""
            WITH amostra_chaves AS (
                SELECT codDocumento, numDocumento, id_deputado
                FROM '{despesas_path}'
                WHERE codDocumento IS NOT NULL
                GROUP BY 1, 2, 3
                HAVING COUNT(*) > 1
                LIMIT 2
            )
            SELECT
                d.id_deputado,
                d.codDocumento,
                d.numDocumento,
                d.dataDocumento,
                d.valorDocumento,
                d.valorLiquido,
                d.valorGlosa
            FROM '{despesas_path}' d
            JOIN amostra_chaves a
              ON d.codDocumento = a.codDocumento
             AND d.numDocumento = a.numDocumento
             AND d.id_deputado = a.id_deputado
            ORDER BY d.codDocumento, d.valorLiquido
        """
        exemplos_df = conn.execute(query_exemplos).df()
        print(exemplos_df.to_string(index=False))
        print(
            "\n💡 Dica Cívica: Compare os valores de 'valorLiquido' e 'valorGlosa'"
            " entre as linhas com mesmo código."
        )
    # ---------------------------------------------------------
    # 3. ANÁLISE CÍVICA (CRUZAMENTO RELACIONAL)
    # ---------------------------------------------------------
    print("\n[3] 💰 Top 5 Gastos em Janeiro de 2024 (Cruzamento Deputados x Despesas):")
    if deputados_path.exists():
        # Vamos usar SQL padrão para fazer o Join entre os Parquets diretamente
        query_top_gastos = f"""
            SELECT
                dep.nome AS Parlamentar,
                desp.nomeFornecedor AS Fornecedor,
                desp.tipoDespesa AS Categoria,
                SUM(desp.valorLiquido) AS TotalGasto
            FROM '{despesas_path}' desp
            JOIN '{deputados_path}' dep ON desp.id_deputado = dep.id
            WHERE desp.dataDocumento >= '2024-01-01'
              AND desp.dataDocumento <= '2024-01-31'
            GROUP BY 1, 2, 3
            ORDER BY TotalGasto DESC
            LIMIT 5
        """
        df_top = conn.execute(query_top_gastos).df()

        # Formatação Cívica (Moeda BR)
        df_top["TotalGasto"] = df_top["TotalGasto"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        # Melhorando o visual no terminal
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 1000)
        print(df_top.to_string(index=False))
    else:
        print("⚠️ Arquivo de deputados não encontrado no Gold para cruzar os dados.")


if __name__ == "__main__":
    validar_camada_gold()
