"""
Exemplos analíticos multi-domínio para validação dos dados no Data Lake iPolitico.

Cada função consulta os dados Parquet (Silver ou Gold) usando DuckDB e responde
uma pergunta relevante para jornalismo de dados. Servem como:

1. Validação de que os dados estão íntegros e consistentes
2. Exemplo de como consumir os dados para análise
3. Verificação de que as relações entre domínios funcionam

Uso:
    python scripts/analytical_examples.py [--gold]
    python scripts/analytical_examples.py --domain q1

Requer: duckdb instalado
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DATALAKE = Path("data/datalake").resolve()


def _silver(domain: str) -> str:
    return str(DATALAKE / "silver" / domain / "*.parquet")


def _gold(domain: str) -> str:
    p = DATALAKE / "gold" / domain / f"{domain}.parquet"
    return str(p) if p.exists() else _silver(domain)


def _table(domain: str, use_gold: bool) -> str:
    """Retorna o caminho de tabela apropriado (Silver glob ou Gold file)."""
    return _gold(domain) if use_gold else _silver(domain)


def _try_execute(conn: duckdb.DuckDBPyConnection, sql: str, fallback_sql: str | None = None):
    """Tenta executar SQL, com fallback para SQL alternativo."""
    try:
        return conn.execute(sql).fetchdf()
    except Exception as e1:
        if fallback_sql:
            try:
                return conn.execute(fallback_sql).fetchdf()
            except Exception as e2:
                print(f"  ❌ Erro: {e1}")
                print(f"  ❌ Fallback: {e2}")
                return None
        print(f"  ❌ Erro: {e1}")
        return None


def q1_deputados_mais_gastos(conn, use_gold: bool) -> None:
    """Quais deputados mais gastaram a cota parlamentar (CEAP) em 2024?"""
    d = _table("deputados", use_gold)
    ds = _table("despesas", use_gold)

    sql = f"""
    SELECT
        nome AS deputado,
        COALESCE(siglaPartido, partido, '?') AS partido,
        COALESCE(siglaUf, uf, '?') AS uf,
        ROUND(SUM(valorLiquido), 2) AS total_gasto
    FROM read_parquet('{ds}') ds
    JOIN read_parquet('{d}') dep ON ds.id_deputado = dep.id
    WHERE ds.ano = 2024
    GROUP BY nome, COALESCE(siglaPartido, partido, '?'), COALESCE(siglaUf, uf, '?')
    ORDER BY total_gasto DESC LIMIT 15
    """
    df = _try_execute(conn, sql)
    if df is not None:
        print("\n📊 Top 15 deputados com maiores gastos (CEAP 2024)")
        print(df.to_string(index=False))


def q2_proposicoes_mais_votadas(conn, use_gold: bool) -> None:
    """Quais proposições tiveram mais votações nominais em plenário?"""
    p = _table("proposicoes", use_gold)
    v = _table("votacoes", use_gold)

    sql = f"""
    SELECT p.id AS id_proposicao,
           COALESCE(p.siglaTipo, p.tipo) || ' ' || p.numero || '/' || p.ano AS proposicao,
           p.ementa,
           COUNT(v.id) AS num_votacoes
    FROM read_parquet('{v}') v
    JOIN read_parquet('{p}') p ON v.id_proposicao = p.id
    GROUP BY p.id, COALESCE(p.siglaTipo, p.tipo), p.numero, p.ano, p.ementa
    ORDER BY num_votacoes DESC LIMIT 15
    """
    df = _try_execute(conn, sql)
    if df is not None:
        print("\n📊 Top 15 proposições com mais votações nominais")
        print(df.to_string(index=False))


def q3_partidos_mais_presentes(conn, use_gold: bool) -> None:
    """Qual a presença média dos partidos nas votações?"""
    v = _table("votos", use_gold)

    sql = f"""
    SELECT partido_no_voto AS partido,
           COUNT(*) AS total_votos,
           ROUND(AVG(CASE WHEN tipoVoto = 'Sim' THEN 1.0 ELSE 0.0 END) * 100, 1) AS pct_sim,
           ROUND(AVG(CASE WHEN tipoVoto = 'Nao' THEN 1.0 ELSE 0.0 END) * 100, 1) AS pct_nao,
           ROUND(
               AVG(CASE WHEN tipoVoto IN ('Abstencao', 'Art. 17') THEN 1.0 ELSE 0.0 END) * 100,
               1
           ) AS pct_abstencao
    FROM read_parquet('{v}')
    GROUP BY partido_no_voto
    HAVING total_votos > 1000
    ORDER BY total_votos DESC LIMIT 15
    """
    df = _try_execute(conn, sql)
    if df is not None:
        print("\n📊 Presença dos partidos nas votações (comportamento de voto)")
        print(df.to_string(index=False))


def q4_eventos_com_pauta(conn, use_gold: bool) -> None:
    """Quantos eventos têm pauta registrada? Quais órgãos têm mais eventos?"""
    ev = _table("eventos", use_gold)
    pa = _table("eventos_pauta", use_gold)
    orgaos = _table("orgaos", use_gold)

    sql = f"""
    SELECT COALESCE(o.sigla, '?') AS orgao_sigla,
           COALESCE(o.nome, '?') AS orgao_nome,
           COUNT(DISTINCT e.id) AS total_eventos,
           COUNT(DISTINCT p.id_proposicao) AS proposicoes_na_pauta
    FROM read_parquet('{ev}') e
    JOIN read_parquet('{orgaos}') o ON e.idOrgao = o.id
    LEFT JOIN read_parquet('{pa}') p ON p.id_evento = e.id
    GROUP BY o.sigla, o.nome
    ORDER BY total_eventos DESC LIMIT 15
    """
    df = _try_execute(conn, sql)
    if df is not None:
        print("\n📊 Órgãos com mais eventos e proposições em pauta")
        print(df.to_string(index=False))


def q5_frentes_com_mais_membros(conn, use_gold: bool) -> None:
    """Quais frentes parlamentares têm mais membros?"""
    f = _table("frentes", use_gold)
    m = _table("frentes_membros", use_gold)

    sql = f"""
    SELECT f.nome AS frente,
           COALESCE(f.siglaFrente, f.sigla) AS sigla,
           COUNT(fm.id_deputado) AS total_membros
    FROM read_parquet('{f}') f
    JOIN read_parquet('{m}') fm ON fm.id_frente = f.id
    GROUP BY f.nome, COALESCE(f.siglaFrente, f.sigla)
    ORDER BY total_membros DESC LIMIT 15
    """
    df = _try_execute(conn, sql)
    if df is not None:
        print("\n📊 Frentes parlamentares com mais membros")
        print(df.to_string(index=False))


def q6_orientacao_partidos(conn, use_gold: bool) -> None:
    """Como os partidos orientaram suas bancadas nas votações mais recentes?"""
    o = _table("orientacoes", use_gold)
    v = _table("votacoes", use_gold)

    sql = f"""
    SELECT v.dataRegistro::DATE AS data_votacao,
           LEFT(o.nomePartido, 20) AS partido,
           o.orientacaoVoto AS orientacao
    FROM read_parquet('{o}') o
    JOIN read_parquet('{v}') v ON o.id_votacao = v.id
    WHERE v.dataRegistro >= '2025-01-01'
    ORDER BY v.dataRegistro DESC LIMIT 20
    """
    df = _try_execute(conn, sql)
    if df is not None and df.empty:
        sql_fb = f"""
        SELECT v.dataRegistro::DATE AS data_votacao,
               LEFT(o.nomePartido, 20) AS partido,
               o.orientacaoVoto AS orientacao
        FROM read_parquet('{o}') o
        JOIN read_parquet('{v}') v ON o.id_votacao = v.id
        ORDER BY v.dataRegistro DESC LIMIT 20
        """
        df = conn.execute(sql_fb).fetchdf()
        print("\n📊 Orientações de partidos (últimas 20, sem filtro de data)")
        print(df.to_string(index=False))
    elif df is not None:
        print("\n📊 Orientações de partidos em votações recentes (2025+)")
        print(df.to_string(index=False))


def q7_validacao_consistencia(conn, _use_gold: bool) -> None:
    """Verifica consistência entre domínios relacionados: votos × deputados."""
    v = _table("votos", False)
    d = _table("deputados", False)

    sql = f"""
    SELECT COUNT(DISTINCT v.id_deputado) AS deputados_que_votaram,
           COUNT(DISTINCT d.id) AS deputados_no_cadastro,
           ROUND(
               COUNT(DISTINCT v.id_deputado) * 100.0 / NULLIF(COUNT(DISTINCT d.id), 0),
               1
           ) AS pct_cobertura
    FROM read_parquet('{v}') v
    FULL JOIN read_parquet('{d}') d ON v.id_deputado = d.id
    """
    df = _try_execute(conn, sql)
    if df is not None:
        print("\n🔍 Validação de consistência: votos × deputados")
        print(df.to_string(index=False))


def q8_proposicoes_por_ano(conn, use_gold: bool) -> None:
    """Distribuição de proposições ao longo dos anos."""
    p = _table("proposicoes", use_gold)

    sql = f"""
    SELECT ano, siglaTipo, COUNT(*) AS total
    FROM read_parquet('{p}')
    WHERE ano >= 2000
    GROUP BY ano, siglaTipo
    ORDER BY ano DESC, total DESC LIMIT 25
    """
    df = _try_execute(conn, sql)
    if df is not None:
        print("\n📊 Proposições por ano e tipo (2000+)")
        print(df.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Exemplos analíticos — Data Lake iPolitico")
    parser.add_argument("--gold", action="store_true", help="Usa camada Gold")
    parser.add_argument("--domain", type=str, default=None, help="q1-q8")
    args = parser.parse_args()

    queries = {
        "q1": q1_deputados_mais_gastos,
        "q2": q2_proposicoes_mais_votadas,
        "q3": q3_partidos_mais_presentes,
        "q4": q4_eventos_com_pauta,
        "q5": q5_frentes_com_mais_membros,
        "q6": q6_orientacao_partidos,
        "q7": q7_validacao_consistencia,
        "q8": q8_proposicoes_por_ano,
    }

    conn = duckdb.connect()
    print("=" * 80)
    print("  iPolitico — Exemplos Analíticos")
    print(f"  Camada: {'GOLD' if args.gold else 'SILVER'}")
    print(f"  Data: {DATALAKE}")
    print("=" * 80)

    if args.domain:
        q = args.domain.lower()
        (queries.get(q, lambda c, g: print(f"  ❌ Query '{q}' não encontrada")))(conn, args.gold)
    else:
        for name, fn in queries.items():
            fn(conn, args.gold)
            print()

    conn.close()


if __name__ == "__main__":
    main()
