"""Testes unitários para o motor de Record Linkage e Resolução de Entidades (Issue 06)."""

import polars as pl

from ipolitico.gold.record_linkage import (
    CONF_ALTA,
    CONF_BAIXA,
    METODO_CPF_EXATO,
    METODO_CPF_MASCARADO,
    METODO_METAPHONE_DN_UF,
    normalizar_cpf,
    vincular_por_cpf,
    vincular_por_cpf_mascarado,
    vincular_por_metaphone_dn_uf,
)


def test_normalizar_cpf_remove_pontuacao_e_garante_11_digitos():
    """Garante formatação e padding de CPF."""
    df = pl.DataFrame(
        {
            "cpf": [
                "123.456.789-00",
                "12345678900",
                "12345678",  # incompleto
                "-4",  # sentinela TSE 2024
                None,
                "***.456.789-**",
            ]
        }
    )
    res = df.select(normalizar_cpf(pl.col("cpf")).alias("cpf_norm"))
    assert res["cpf_norm"].to_list() == [
        "12345678900",
        "12345678900",
        None,
        None,
        None,
        None,
    ]


def test_vincular_por_cpf_exato_match_auditavel():
    """Valida linkage determinístico 1-para-1 com CPF íntegro."""
    df_fonte = pl.DataFrame(
        {
            "id_natural": [101, 102],
            "cpf": ["111.222.333-44", "999.888.777-66"],
            "nome": ["DEPUTADO UM", "DEPUTADO DOIS"],
            "_source_url": ["http://camara/101", "http://camara/102"],
        }
    )
    df_tse = pl.DataFrame(
        {
            "sq_candidato": [90001, 90002],
            "cpf": ["11122233344", "00011122233"],
            "nome": ["DEPUTADO UM CIVIL", "OUTRO CANDIDATO"],
            "_source_url": ["http://tse/90001", "http://tse/90002"],
        }
    )

    aliases, resolucoes = vincular_por_cpf(
        df_fonte=df_fonte,
        df_tse=df_tse,
        fonte="camara",
        col_id_fonte="id_natural",
    )

    assert aliases.height == 1
    assert aliases["id_natural"][0] == 101
    assert aliases["politico_id"][0] == "pol_cpf_11122233344"
    assert aliases["metodo"][0] == METODO_CPF_EXATO
    assert aliases["confianca"][0] == CONF_ALTA
    assert aliases["score"][0] == 1.0

    assert resolucoes.height == 1
    assert resolucoes["id_origem"][0] == "101"
    assert resolucoes["id_destino"][0] == "90001"


def test_vincular_por_cpf_mascarado_bloco():
    """Valida linkage quando a fonte possui CPF com 6 dígitos centrais expostos."""
    df_cgu = pl.DataFrame(
        {
            "id_servidor": [501],
            "cpf_mascarado": ["***.555.666-**"],
            "data_nascimento": ["1975-08-20"],
            "uf": ["SP"],
            "_source_url": ["http://cgu/501"],
        }
    )
    df_tse = pl.DataFrame(
        {
            "sq_candidato": [80001],
            "cpf": ["12355566699"],  # central = 555666
            "data_nascimento": ["1975-08-20"],
            "uf": ["SP"],
            "_source_url": ["http://tse/80001"],
        }
    )

    aliases, resolucoes = vincular_por_cpf_mascarado(
        df_fonte=df_cgu,
        df_tse=df_tse,
        fonte="cgu_pep",
        col_id_fonte="id_servidor",
        col_cpf_mascarado="cpf_mascarado",
    )

    assert aliases.height == 1
    assert aliases["id_natural"][0] == 501
    assert aliases["politico_id"][0] == "pol_cpf_12355566699"
    assert aliases["metodo"][0] == METODO_CPF_MASCARADO
    assert aliases["confianca"][0] == CONF_ALTA


def test_vincular_por_metaphone_dn_uf_sem_cpf():
    """Valida linkage fonético quando CPF está ausente (ex: TSE 2024)."""
    df_camara = pl.DataFrame(
        {
            "id_deputado": [201],
            "nome": ["ARTHUR CESAR PEREIRA DE LIRA"],
            "data_nascimento": ["1969-06-25"],
            "uf": ["AL"],
            "_source_url": ["http://camara/201"],
        }
    )
    df_tse = pl.DataFrame(
        {
            "sq_candidato": [70001],
            "nome": ["ARTUR CESAR PEREIRA LIRA"],  # grafia alternativa
            "data_nascimento": ["1969-06-25"],
            "uf": ["AL"],
            "_source_url": ["http://tse/70001"],
        }
    )

    aliases, resolucoes = vincular_por_metaphone_dn_uf(
        df_fonte=df_camara,
        df_tse=df_tse,
        fonte="camara",
        col_id_fonte="id_deputado",
    )

    assert aliases.height == 1
    assert aliases["id_natural"][0] == 201
    assert aliases["metodo"][0] == METODO_METAPHONE_DN_UF
    assert aliases["confianca"][0] == CONF_ALTA
    assert aliases["score"][0] == 0.90


def test_vincular_homonimos_gera_baixa_confianca_para_revisao():
    """Garante que homônimos não sofrem merge silencioso indevido."""
    df_fonte = pl.DataFrame(
        {
            "id_natural": [301],
            "nome": ["JOSE SILVA"],
            "data_nascimento": [None],
            "uf": ["SP"],
            "_source_url": ["http://fonte/301"],
        }
    )
    df_tse = pl.DataFrame(
        {
            "sq_candidato": [60001, 60002],
            "nome": ["JOSE SILVA", "JOSE DA SILVA"],  # dois candidatos distintos
            "data_nascimento": ["1960-01-01", "1970-02-02"],
            "uf": ["SP", "SP"],
            "_source_url": ["http://tse/60001", "http://tse/60002"],
        }
    )

    aliases, resolucoes = vincular_por_metaphone_dn_uf(
        df_fonte=df_fonte,
        df_tse=df_tse,
        fonte="fonte_teste",
        col_id_fonte="id_natural",
    )

    # Não deve haver merge nos aliases para homônimo ambíguo!
    assert aliases.is_empty()
    # Deve ser registrado na trilha de auditoria para revisão humana
    assert resolucoes.height == 2
    assert all(c == CONF_BAIXA for c in resolucoes["confianca"])
    assert all("ambíguo" in j.lower() for j in resolucoes["justificativa"])
