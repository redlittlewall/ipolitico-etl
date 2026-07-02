from pathlib import Path

import duckdb

from ipolitico.core.constants import ApiParams


def executar_auditoria_gold():
    print("=" * 70)
    print(" 🔎 AUDITORIA DE INTEGRIDADE REFERENCIAL (CAMADA GOLD)")
    print("=" * 70)

    # Conecta ao DuckDB em memória
    conn = duckdb.connect()

    # Paths da camada Gold
    base_path = "data/datalake/gold"
    p_deputados = f"{base_path}/deputados/deputados.parquet"
    p_despesas = f"{base_path}/despesas/despesas.parquet"
    p_votacoes = f"{base_path}/votacoes/votacoes.parquet"
    p_votos = f"{base_path}/votos/votos.parquet"
    p_proposicoes = f"{base_path}/proposicoes/proposicoes.parquet"

    # 1. CONTAGEM MACRO
    print("\n[1] Volume de Dados Consolidados:")
    try:
        for entity, path in [
            ("Deputados", p_deputados),
            ("Despesas", p_despesas),
            ("Votações", p_votacoes),
            ("Votos", p_votos),
            ("Proposições", p_proposicoes),
        ]:
            if Path(path).exists():
                count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
                print(f"  ✅ {entity.ljust(15)}: {count:,} registros")
            else:
                print(f"  ❌ {entity.ljust(15)}: Arquivo não encontrado!")
    except Exception as e:
        print(f"Erro na leitura base: {e}")

    # 2. TESTE DE INTEGRIDADE: VOTOS ÓRFÃOS (Problema N+1)
    print("\n[2] Teste de Integridade: Votos sem Votação Matriz")
    try:
        query_orfãos = f"""
            SELECT COUNT(*)
            FROM read_parquet('{p_votos}') v
            LEFT JOIN read_parquet('{p_votacoes}') vt ON v.votacao_id = vt.id
            WHERE vt.id IS NULL
        """
        orfaos_count = conn.execute(query_orfãos).fetchone()[0]
        if orfaos_count == 0:
            print("  ✅ Sucesso: 100% dos votos estão vinculados a uma votação válida.")
        else:
            print(f"  🚨 ALERTA CRÍTICO: {orfaos_count} votos estão órfãos")
    except Exception as e:
        print(f"  ⚠️ Não foi possível testar votos: {e}")

    # 3. TESTE DE INTEGRIDADE: DESPESAS FANTASMAS
    print("\n[3] Teste de Integridade: Despesas de Deputados Inexistentes")
    try:
        col_dep_id = ApiParams.DEPUTADO_ID.value
        query_fantasmas = f"""
            SELECT COUNT(*)
            FROM read_parquet('{p_despesas}') d
            LEFT JOIN read_parquet('{p_deputados}') dep ON d.{col_dep_id} = dep.id
            WHERE dep.id IS NULL
        """
        fantasmas_count = conn.execute(query_fantasmas).fetchone()[0]
        if fantasmas_count == 0:
            print("  ✅ Sucesso: 100% das despesas pertencem a deputados cadastrados.")
        else:
            print(
                f"  🚨 ALERTA CRÍTICO: {fantasmas_count} despesas pertencem a IDs de deputados que não estão no banco."  # noqa: E501
            )
            print(
                "  💡 Dica: Isso acontece se você não extraiu as legislaturas antigas no Manager."
            )
    except Exception as e:
        print(f"  ⚠️ Não foi possível testar despesas: {e}")


if __name__ == "__main__":
    executar_auditoria_gold()
