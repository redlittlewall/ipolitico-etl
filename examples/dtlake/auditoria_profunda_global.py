from pathlib import Path

import duckdb

# Configuração de caminhos
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATALAKE_PATH = BASE_DIR / "datalake"


def auditoria_global():
    print("=" * 80)
    print(" 🔎 AUDITORIA PROFUNDA DE SCHEMA E VOLUMETRIA - iPolitico")
    print("=" * 80)

    conn = duckdb.connect()
    arquivos = list(DATALAKE_PATH.glob("*.parquet"))

    if not arquivos:
        print(f"Erro: Nenhum arquivo encontrado em {DATALAKE_PATH}")
        return

    for path in sorted(arquivos):
        tabela = path.stem
        print(f"\n📊 TABELA: {tabela.upper()}")
        print("-" * 40)

        try:
            # 1. DESCRIBE: Tipagem de dados
            schema_info = conn.execute(f"DESCRIBE SELECT * FROM '{path}'").df()
            print("--- Estrutura (Top 5 colunas):")
            print(schema_info[["column_name", "column_type"]].head(5).to_markdown(index=False))

            # 2. AMOSTRA: Primeiras 3 linhas formatadas
            # Nota: Usamos strings para evitar o problema do 'e+08' na visualização
            amostra = conn.execute(f"SELECT * FROM '{path}' LIMIT 3").df()
            print("\n--- Amostra de Dados:")
            # Truque: converte tudo para string no print para garantir visibilidade
            print(amostra.astype(str).to_markdown(index=False))

            # 3. CONTAGEM
            total = conn.execute(f"SELECT COUNT(*) FROM '{path}'").fetchone()[0]
            print(f"\n✅ Total de Registros: {total:,}".replace(",", "."))
            print("." * 80)

        except Exception as e:
            print(f"❌ Erro ao analisar {tabela}: {e}")


if __name__ == "__main__":
    auditoria_global()
