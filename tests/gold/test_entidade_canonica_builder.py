"""Testes do builder da entidade canônica (issue 01) — leitura/escrita Gold."""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.gold.entidade_canonica import CoberturaEntidadeCanonica, EntidadeCanonicaBuilder


def _salvar(tmp_path, domain: DomainType, df: pl.DataFrame) -> None:
    """Escreve um parquet Silver de teste para o domínio."""
    d = tmp_path / "silver" / domain.value
    d.mkdir(parents=True, exist_ok=True)
    df.write_parquet(d / "lote_test.parquet")


def _deputados():
    return pl.DataFrame(
        {
            "id": [5],
            "nome": ["MARIA SILVA"],
            "uf": ["CE"],
            "idLegislatura": [57],
            "_source_url": ["http://camara/d5"],
        }
    )


def _detalhe():
    return pl.DataFrame(
        {
            "id": [5],
            "cpf": ["111.222.333-44"],
            "dataNascimento": [None],
            "nomeCivil": ["MARIA SILVA"],
            "ufNascimento": ["CE"],
            "municipioNascimento": [None],
            "_source_url": ["http://camara/det5"],
        }
    )


def _senadores():
    return pl.DataFrame(
        {
            "codigo": [77],
            "nome": ["MARIA SILVA"],
            "nome_completo": ["MARIA SILVA"],
            "sexo": ["F"],
            "uf": ["CE"],
            "codigo_mandato": [None],
            "descricao_participacao": [None],
            "primeira_legislatura": [None],
            "segunda_legislatura": [56],
            "_source_url": ["http://senado/s77"],
        }
    )


def test_builder_gera_tabelas_gold_append_only(tmp_path):
    _salvar(tmp_path, DomainType.DEPUTADOS, _deputados())
    _salvar(tmp_path, DomainType.DEPUTADOS_DETALHE, _detalhe())
    _salvar(tmp_path, DomainType.SENADORES, _senadores())

    builder = EntidadeCanonicaBuilder(base_dir=str(tmp_path))
    builder.build()
    cov = builder.cobertura()

    # Append-only: 1 lote por tabela na primeira execução.
    assert len(list((tmp_path / "gold" / "politicos").glob("*.parquet"))) == 1
    assert len(list((tmp_path / "gold" / "politicos_aliases").glob("*.parquet"))) == 1
    assert len(list((tmp_path / "gold" / "resolucoes").glob("*.parquet"))) == 1

    # Segunda execução: novo lote, nada sobrescrito.
    builder.build()
    assert len(list((tmp_path / "gold" / "politicos").glob("*.parquet"))) == 2

    # Deputado e senador são a mesma pessoa → 1 político, âncora Câmara.
    assert cov.total_politicos == 1
    assert cov.ancoras_camara == 1
    assert cov.ancoras_senado == 0
    primeiro_lote = sorted((tmp_path / "gold" / "politicos").glob("*.parquet"))[0]
    politicos = pl.read_parquet(primeiro_lote)
    assert politicos["politico_id"].to_list() == ["pol_camara_5"]
    assert politicos["cpf"].to_list() == ["111.222.333-44"]
    assert "captured_at" in politicos.columns


def test_builder_sem_domains_nao_crasha_e_relatorio_vazio(tmp_path):
    builder = EntidadeCanonicaBuilder(base_dir=str(tmp_path))
    builder.build()
    cov = builder.cobertura()
    assert isinstance(cov, CoberturaEntidadeCanonica)
    assert cov.total_politicos == 0
    assert cov.total_aliases == 0
    assert cov.resolucoes_candidatas_revisao == 0
    # Nenhuma tabela Gold criada sem dados.
    assert not (tmp_path / "gold" / "politicos").exists()


def test_builder_senador_sem_deputado_ganha_ancora_senado(tmp_path):
    _salvar(tmp_path, DomainType.SENADORES, _senadores())

    builder = EntidadeCanonicaBuilder(base_dir=str(tmp_path))
    builder.build()
    cov = builder.cobertura()

    assert cov.total_politicos == 1
    assert cov.ancoras_senado == 1
    assert cov.aliases_por_fonte.get("senado") == 1
    politicos = pl.read_parquet(tmp_path / "gold" / "politicos" / "*.parquet")
    assert politicos["politico_id"].to_list() == ["pol_senado_77"]
