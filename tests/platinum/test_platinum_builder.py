"""Testes unitários da Camada Platinum (Issue 07).

Valida os Data Marts OBT (One Big Table) desnormalizados:
- ``obt_politico_custo_mensal``
- ``obt_politico_resumo_carreira``
- Métricas analíticas de custo e atividade legislativa
- Idempotência, schemas estritos e exportação SQLite / DuckDB.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

from ipolitico.platinum.builder import PlatinumBuilder
from ipolitico.platinum.models import (
    OBT_POLITICO_CUSTO_MENSAL_SCHEMA,
    OBT_POLITICO_RESUMO_CARREIRA_SCHEMA,
    TABLE_OBT_POLITICO_CUSTO_MENSAL,
    TABLE_OBT_POLITICO_RESUMO_CARREIRA,
    mascarar_cpf,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Fixtures de DataFrames sintéticos
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def synthetic_gold_data():
    """Gera dados Gold sintéticos com deputados e senadores."""
    politicos = pl.DataFrame(
        {
            "politico_id": ["pol_camara_10", "pol_senado_20"],
            "nome_civil": ["Maria Parlamentar", "João Senador"],
            "cpf": ["12345678901", "98765432100"],
            "data_nascimento": ["1975-03-10", "1960-11-25"],
            "uf": ["SP", "MG"],
            "_source_url": ["http://camara.gov.br", "http://senado.gov.br"],
        }
    )

    aliases = pl.DataFrame(
        {
            "fonte": ["camara", "senado"],
            "id_natural": [10, 20],
            "politico_id": ["pol_camara_10", "pol_senado_20"],
            "metodo": ["cpf_exato", "chave_natural"],
            "confianca": ["alta", "alta"],
            "_source_url": ["http://camara.gov.br", "http://senado.gov.br"],
        }
    )

    custo = pl.DataFrame(
        {
            "politico_id": [
                "pol_camara_10",
                "pol_camara_10",
                "pol_camara_10",
                "pol_camara_10",
                "pol_senado_20",
                "pol_senado_20",
            ],
            "casa": ["camara", "camara", "camara", "camara", "senado", "senado"],
            "mandato": [57, 57, 57, 57, 57, 57],
            "componente": [
                "salario",
                "ceap",
                "assessores",
                "viagens",
                "salario",
                "ceap",  # no senado vira total_ceaps
            ],
            "mes": [
                "2024-01",
                "2024-01",
                "2024-01",
                "2024-02",
                "2024-01",
                "2024-01",
            ],
            "valor_total": [
                30000.0,
                15000.0,
                10000.0,
                5000.0,
                35000.0,
                20000.0,
            ],
            "metodo": ["exato"] * 6,
            "_source_url": ["http://custo.gov.br"] * 6,
        }
    )

    deputados = pl.DataFrame(
        {
            "id": [10],
            "nome": ["Maria Parlamentar"],
            "partido": ["PARTIDO_A"],
            "uf": ["SP"],
            "idLegislatura": [57],
        }
    )

    senadores = pl.DataFrame(
        {
            "codigo": [20],
            "nome": ["João Senador"],
            "uf": ["MG"],
            "segunda_legislatura": [57],
        }
    )

    return {
        "politicos": politicos,
        "aliases": aliases,
        "custo": custo,
        "deputados": deputados,
        "senadores": senadores,
    }


@pytest.fixture
def synthetic_silver_activity():
    """Gera fatos Silver sintéticos de proposições, votações e presença."""
    proposicoes = pl.DataFrame(
        {
            "id": [101, 102, 103],
            "siglaTipo": ["PL", "PEC", "PL"],
            "numero": [1, 2, 3],
            "ano": [2023, 2023, 2024],
            "ementa": ["Projeto 1", "Projeto 2", "Projeto 3"],
        }
    )

    autores = pl.DataFrame(
        {
            "id_proposicao": [101, 102, 103],
            "nome": ["Maria Parlamentar", "Maria Parlamentar", "João Senador"],
            "uri": [
                "https://dadosabertos.camara.leg.br/api/v2/deputados/10",
                "https://dadosabertos.camara.leg.br/api/v2/deputados/10",
                "https://dadosabertos.senado.leg.br/api/v2/senadores/20",
            ],
        }
    )

    votacoes = pl.DataFrame(
        {
            "id": ["vot_101", "vot_102"],
            "aprovacao": [1, 0],
            "proposicaoObjeto": ["PL 1/2023", "PEC 2/2023"],
        }
    )

    votacoes_prop = pl.DataFrame(
        {
            "idVotacao": ["vot_101", "vot_102"],
            "proposicao_id": [101, 102],
        }
    )

    votos = pl.DataFrame(
        {
            "id_deputado": [10, 10],
            "votacao_id": ["vot_101", "vot_102"],
            "tipoVoto": ["Sim", "Não"],
        }
    )

    votos_senado = pl.DataFrame(
        {
            "codigo_parlamentar": [20],
            "votacao_id": [888],
            "voto": ["Sim"],
        }
    )

    presenca = pl.DataFrame(
        {
            "idEvento": [9001, 9002],
            "idDeputado": [10, 10],
        }
    )

    return {
        "proposicoes": proposicoes,
        "autores": autores,
        "votacoes": votacoes,
        "votacoes_proposicoes": votacoes_prop,
        "votos": votos,
        "votos_senado": votos_senado,
        "presenca": presenca,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Testes unitários
# ─────────────────────────────────────────────────────────────────────────────


def test_mascarar_cpf():
    """Valida o mascaramento contratual de CPF (***.XXX.XXX-**)."""
    # 11 dígitos sem pontuação
    assert mascarar_cpf("12345678901") == "***.456.789-**"
    # Formatado com pontuação
    assert mascarar_cpf("123.456.789-01") == "***.456.789-**"
    # Já mascarado
    assert mascarar_cpf("***.456.789-**") == "***.456.789-**"
    # Nulo ou vazio
    assert mascarar_cpf(None) is None
    assert mascarar_cpf("") is None
    assert mascarar_cpf("   ") is None
    # Menos de 6 dígitos
    assert mascarar_cpf("123") == "123"


def test_platinum_builder_empty_upstream():
    """Garante resiliência e schemas estritos quando o upstream está vazio."""
    builder = PlatinumBuilder(base_dir="non_existent_dir")
    empty_politicos = pl.DataFrame(schema=OBT_POLITICO_RESUMO_CARREIRA_SCHEMA)

    df_mensal, df_resumo = builder.transform(
        politicos=empty_politicos,
        politicos_aliases=pl.DataFrame(),
        custo_erario=pl.DataFrame(),
    )

    assert df_mensal.is_empty()
    assert df_resumo.is_empty()
    assert set(df_mensal.columns) == set(OBT_POLITICO_CUSTO_MENSAL_SCHEMA.keys())
    assert set(df_resumo.columns) == set(OBT_POLITICO_RESUMO_CARREIRA_SCHEMA.keys())


def test_obt_politico_custo_mensal_rubricas_and_keys(
    synthetic_gold_data,
    synthetic_silver_activity,
):
    """Valida chaves, período e rubricas de custo discriminadas no grão mensal."""
    builder = PlatinumBuilder()
    df_mensal, _ = builder.transform(
        politicos=synthetic_gold_data["politicos"],
        politicos_aliases=synthetic_gold_data["aliases"],
        custo_erario=synthetic_gold_data["custo"],
        deputados=synthetic_gold_data["deputados"],
        senadores=synthetic_gold_data["senadores"],
        **synthetic_silver_activity,
    )

    # Verifica colunas contratuais
    assert set(df_mensal.columns) == set(OBT_POLITICO_CUSTO_MENSAL_SCHEMA.keys())

    # Maria Parlamentar 2024-01:
    # salario: 30000, ceap: 15000, assessores: 10000 -> total: 55000
    maria_jan = df_mensal.filter(
        (pl.col("id_politico_canônico") == "pol_camara_10") & (pl.col("ano_mes") == "2024-01")
    )
    assert maria_jan.height == 1
    row_maria = maria_jan.to_dicts()[0]
    assert row_maria["nome"] == "Maria Parlamentar"
    assert row_maria["cpf_mascarado"] == "***.456.789-**"
    assert row_maria["partido_atual"] == "PARTIDO_A"
    assert row_maria["cargo_atual"] == "Deputado Federal"
    assert row_maria["ano"] == 2024
    assert row_maria["mes"] == 1
    assert row_maria["total_salario"] == 30000.0
    assert row_maria["total_ceap"] == 15000.0
    assert row_maria["total_ceaps"] == 0.0
    assert row_maria["total_verba_gabinete"] == 10000.0
    assert row_maria["custo_total_mes"] == 55000.0

    # Maria Parlamentar 2024-02:
    # viagens: 5000 -> total: 5000
    maria_fev = df_mensal.filter(
        (pl.col("id_politico_canônico") == "pol_camara_10") & (pl.col("ano_mes") == "2024-02")
    )
    assert maria_fev.height == 1
    assert maria_fev["total_viagens"][0] == 5000.0
    assert maria_fev["custo_total_mes"][0] == 5000.0

    # João Senador 2024-01:
    # salario: 35000, ceap (senado -> ceaps): 20000 -> total: 55000
    joao_jan = df_mensal.filter(
        (pl.col("id_politico_canônico") == "pol_senado_20") & (pl.col("ano_mes") == "2024-01")
    )
    assert joao_jan.height == 1
    row_joao = joao_jan.to_dicts()[0]
    assert row_joao["nome"] == "João Senador"
    assert row_joao["cpf_mascarado"] == "***.654.321-**"
    assert row_joao["cargo_atual"] == "Senador"
    assert row_joao["total_salario"] == 35000.0
    assert row_joao["total_ceap"] == 0.0
    assert row_joao["total_ceaps"] == 20000.0
    assert row_joao["custo_total_mes"] == 55000.0


def test_obt_politico_resumo_carreira_metrics(
    synthetic_gold_data,
    synthetic_silver_activity,
):
    """Valida agregações de vida pública: custo total, mandatos, proposições, votos e presença."""
    builder = PlatinumBuilder()
    _, df_resumo = builder.transform(
        politicos=synthetic_gold_data["politicos"],
        politicos_aliases=synthetic_gold_data["aliases"],
        custo_erario=synthetic_gold_data["custo"],
        deputados=synthetic_gold_data["deputados"],
        senadores=synthetic_gold_data["senadores"],
        **synthetic_silver_activity,
    )

    assert set(df_resumo.columns) == set(OBT_POLITICO_RESUMO_CARREIRA_SCHEMA.keys())
    assert df_resumo.height == 2

    maria = df_resumo.filter(pl.col("id_politico_canônico") == "pol_camara_10").to_dicts()[0]
    assert maria["custo_total_acumulado_historico"] == 60000.0  # 30k + 15k + 10k + 5k
    assert maria["proposicoes_apresentadas"] == 2
    assert maria["proposicoes_aprovadas"] == 1
    assert maria["taxa_sucesso_legislativo"] == 0.5
    assert maria["votos_registrados"] == 2
    assert maria["presenca_plenario_pct"] == 100.0  # 2 de 2 eventos presentes
    assert maria["quantidade_mandatos"] >= 1

    joao = df_resumo.filter(pl.col("id_politico_canônico") == "pol_senado_20").to_dicts()[0]
    assert joao["custo_total_acumulado_historico"] == 55000.0  # 35k + 20k
    assert joao["proposicoes_apresentadas"] == 1
    assert joao["proposicoes_aprovadas"] == 0
    assert joao["taxa_sucesso_legislativo"] == 0.0
    assert joao["votos_registrados"] == 1
    assert joao["quantidade_mandatos"] >= 1


def test_platinum_builder_build_and_idempotency(tmp_path: Path, synthetic_gold_data):
    """Valida idempotência da materialização de arquivos Parquet ZSTD."""
    # Prepara diretório com dados Gold
    base_dir = tmp_path / "datalake"
    gold_dir = base_dir / "gold"
    gold_dir.mkdir(parents=True)

    synthetic_gold_data["politicos"].write_parquet(gold_dir / "politicos.parquet")
    synthetic_gold_data["aliases"].write_parquet(gold_dir / "politicos_aliases.parquet")
    synthetic_gold_data["custo"].write_parquet(gold_dir / "custo_erario.parquet")

    builder = PlatinumBuilder(base_dir=str(base_dir))

    # Primeira execução
    cov1 = builder.build()
    assert cov1.total_politicos == 2
    assert cov1.total_linhas_custo_mensal == 3

    file_mensal = base_dir / "platinum" / f"{TABLE_OBT_POLITICO_CUSTO_MENSAL}.parquet"
    file_resumo = base_dir / "platinum" / f"{TABLE_OBT_POLITICO_RESUMO_CARREIRA}.parquet"
    assert file_mensal.exists()
    assert file_resumo.exists()

    df1_mensal = pl.read_parquet(file_mensal)
    df1_resumo = pl.read_parquet(file_resumo)

    # Segunda execução (idempotência total, sem duplicar linhas)
    cov2 = builder.build()
    assert cov2.total_politicos == cov1.total_politicos
    assert cov2.total_linhas_custo_mensal == cov1.total_linhas_custo_mensal

    df2_mensal = pl.read_parquet(file_mensal)
    df2_resumo = pl.read_parquet(file_resumo)

    assert df1_mensal.height == df2_mensal.height
    assert df1_resumo.height == df2_resumo.height


def test_platinum_builder_export_sqlite_and_duckdb(tmp_path: Path, synthetic_gold_data):
    """Valida exportação das tabelas Platinum para SQLite e DuckDB."""
    base_dir = tmp_path / "datalake"
    gold_dir = base_dir / "gold"
    gold_dir.mkdir(parents=True)

    synthetic_gold_data["politicos"].write_parquet(gold_dir / "politicos.parquet")
    synthetic_gold_data["aliases"].write_parquet(gold_dir / "politicos_aliases.parquet")
    synthetic_gold_data["custo"].write_parquet(gold_dir / "custo_erario.parquet")

    builder = PlatinumBuilder(base_dir=str(base_dir))
    builder.build()

    # 1. Export SQLite
    sqlite_output = tmp_path / "platinum.db"
    exported_sqlite = builder.export_all(str(sqlite_output), format="sqlite")
    assert TABLE_OBT_POLITICO_CUSTO_MENSAL in exported_sqlite
    assert TABLE_OBT_POLITICO_RESUMO_CARREIRA in exported_sqlite
    assert sqlite_output.exists()

    # Verifica integridade no SQLite nativo
    conn = sqlite3.connect(sqlite_output)
    cursor = conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{TABLE_OBT_POLITICO_CUSTO_MENSAL}"')
    assert cursor.fetchone()[0] == 3
    cursor.execute(f'SELECT COUNT(*) FROM "{TABLE_OBT_POLITICO_RESUMO_CARREIRA}"')
    assert cursor.fetchone()[0] == 2
    conn.close()

    # 2. Export DuckDB
    duckdb_output = tmp_path / "platinum.duckdb"
    exported_duckdb = builder.export_all(str(duckdb_output), format="duckdb")
    assert TABLE_OBT_POLITICO_CUSTO_MENSAL in exported_duckdb
    assert TABLE_OBT_POLITICO_RESUMO_CARREIRA in exported_duckdb
    # Verifica integridade no DuckDB
    dcon = duckdb.connect(str(duckdb_output))
    r_mensal = dcon.execute(f'SELECT COUNT(*) FROM "{TABLE_OBT_POLITICO_CUSTO_MENSAL}"').fetchone()[
        0
    ]
    assert r_mensal == 3
    r_resumo = dcon.execute(
        f'SELECT COUNT(*) FROM "{TABLE_OBT_POLITICO_RESUMO_CARREIRA}"'
    ).fetchone()[0]
    assert r_resumo == 2
    dcon.close()


def test_cobertura_platinum(tmp_path: Path, synthetic_gold_data):
    """Valida o método cobertura() como query idempotente sem mutações."""
    base_dir = tmp_path / "datalake"
    gold_dir = base_dir / "gold"
    gold_dir.mkdir(parents=True)

    synthetic_gold_data["politicos"].write_parquet(gold_dir / "politicos.parquet")
    synthetic_gold_data["aliases"].write_parquet(gold_dir / "politicos_aliases.parquet")
    synthetic_gold_data["custo"].write_parquet(gold_dir / "custo_erario.parquet")

    builder = PlatinumBuilder(base_dir=str(base_dir))

    # Antes do build: sem arquivos, retorna zeros
    cov_vazia = builder.cobertura()
    assert cov_vazia.total_politicos == 0
    assert cov_vazia.total_linhas_custo_mensal == 0

    # Após o build
    builder.build()
    cov = builder.cobertura()
    assert cov.total_politicos == 2
    assert cov.total_linhas_custo_mensal == 3
    assert cov.custo_total_acumulado == 115000.0  # 60k + 55k
    assert TABLE_OBT_POLITICO_CUSTO_MENSAL in cov.tabelas_geradas
    assert TABLE_OBT_POLITICO_RESUMO_CARREIRA in cov.tabelas_geradas


@pytest.mark.asyncio
async def test_cli_platinum_integration(monkeypatch, tmp_path: Path, synthetic_gold_data, capsys):
    """Valida execução da CLI com as opções --build-platinum e --export-platinum."""
    from ipolitico.main import main

    # Prepara datalake sob cwd
    datalake_dir = Path("data/datalake")
    gold_dir = datalake_dir / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    synthetic_gold_data["politicos"].write_parquet(gold_dir / "politicos.parquet")
    synthetic_gold_data["aliases"].write_parquet(gold_dir / "politicos_aliases.parquet")
    synthetic_gold_data["custo"].write_parquet(gold_dir / "custo_erario.parquet")

    try:
        # 1. Testa CLI --build-platinum
        monkeypatch.setattr(sys, "argv", ["ipolitico", "--build-platinum"])
        await main()

        captured = capsys.readouterr()
        assert "políticos consolidados: 2" in captured.out
        assert "registros mensais (obt_politico_custo_mensal): 3" in captured.out

        # 2. Testa CLI --export-platinum sqlite
        monkeypatch.setattr(sys, "argv", ["ipolitico", "--export-platinum", "sqlite"])
        await main()

        captured_export = capsys.readouterr()
        assert "Tabelas Platinum exportadas para" in captured_export.out
        assert Path("data/platinum_export.db").exists()
    finally:
        # Cleanup dos arquivos gerados no workspace
        for p in [
            gold_dir / "politicos.parquet",
            gold_dir / "politicos_aliases.parquet",
            gold_dir / "custo_erario.parquet",
            datalake_dir / "platinum" / f"{TABLE_OBT_POLITICO_CUSTO_MENSAL}.parquet",
            datalake_dir / "platinum" / f"{TABLE_OBT_POLITICO_RESUMO_CARREIRA}.parquet",
            Path("data/platinum_export.db"),
        ]:
            if p.exists():
                p.unlink()
