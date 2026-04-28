import os

import duckdb


def gerar_inventario_datalake():
    print("=" * 80)
    print(" 📑 INVENTÁRIO E DOCUMENTAÇÃO DO DATALAKE iPOLITICO")
    print("=" * 80)

    conn = duckdb.connect()
    caminho_lake = "datalake/"

    if not os.path.exists(caminho_lake):
        print(f"Erro: Pasta {caminho_lake} não encontrada.")
        return

    arquivos = [f for f in os.listdir(caminho_lake) if f.endswith(".parquet")]

    for arquivo in arquivos:
        tabela = arquivo.replace(".parquet", "")
        path = os.path.join(caminho_lake, arquivo)

        print(f"\n📂 ENTIDADE: {tabela.upper()}")
        print(f"   ∟ Arquivo: {path}")

        # Estatísticas básicas
        stats = conn.execute(
            f"SELECT COUNT(*) as total, COUNT(DISTINCT captured_at) as cargas FROM '{path}'"
        ).fetchone()
        print(f"   ∟ Total de Registros: {stats[0]}")
        print(f"   ∟ Histórico de Sincronizações: {stats[1]}")

        # Descoberta de Schema
        print("   ∟ Dicionário de Dados (Atributos encontrados):")
        cols = conn.execute(f"DESCRIBE SELECT * FROM '{path}'").df()

        for _, row in cols.iterrows():
            # Identifica se é uma URL, ID ou Valor
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
