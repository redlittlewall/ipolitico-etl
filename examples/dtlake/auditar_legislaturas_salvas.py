import duckdb


def auditar_legislaturas_salvas():
    # Caminho do seu Data Lake
    caminho_parquet = "data/datalake/gold/deputados/deputados.parquet"

    conn = duckdb.connect()

    try:
        # Agrupa os deputados pela legislatura para vermos quais faltam
        query = f"""
            SELECT idLegislatura, COUNT(*) as qtd_deputados
            FROM '{caminho_parquet}'
            GROUP BY idLegislatura
            ORDER BY idLegislatura ASC
        """
        df = conn.execute(query).df()

        # Cria uma lista de 1 a 57 (todas as legislaturas esperadas)
        legislaturas_esperadas = set(range(1, 58))
        legislaturas_salvas = set(df["idLegislatura"].dropna().astype(int).tolist())

        faltantes = legislaturas_esperadas - legislaturas_salvas

        print("=== RELATÓRIO DE AUDITORIA ===")
        if faltantes:
            print(f"❌ ATENÇÃO! Faltam as legislaturas: {sorted(list(faltantes))}")
        else:
            print("✅ Todas as 57 legislaturas estão no arquivo!")

        print("\nDistribuição das Legislaturas Salvas:")
        print(df.to_string(index=False))

    except Exception as e:
        print(f"Erro ao ler o arquivo: {e}")


if __name__ == "__main__":
    auditar_legislaturas_salvas()
