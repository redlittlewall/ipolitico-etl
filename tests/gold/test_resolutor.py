"""Testes das funções puras de resolução de entidade (issue 01)."""

import polars as pl

from ipolitico.gold.resolutor import (
    FONTE_CAMARA,
    FONTE_SENADO,
    FONTE_SERVIDOR,
    montar_ancoras,
    normalizar_nome,
    resolve_fuzzy_camara_senado,
    resolve_por_chaves_naturais,
    resolve_por_cpf,
    resolve_roster_servidor,
)


# ─────────────────────────────────────────────────────────────────────────────
# normalizar_nome
# ─────────────────────────────────────────────────────────────────────────────
def test_normalizar_nome_remove_acentos_maiusculas_e_espacos():
    df = pl.DataFrame({"nome": ["  João da Silva  ", "MARIA CLÁUDIA  ", None]})
    result = df.select(normalizar_nome(pl.col("nome")).alias("norm"))
    assert result["norm"].to_list() == ["JOAO DA SILVA", "MARIA CLAUDIA", None]


# ─────────────────────────────────────────────────────────────────────────────
# resolve_por_cpf
# ─────────────────────────────────────────────────────────────────────────────
def _deputado_detalhe(**kwargs):
    dados = {
        "id": [1, 2, 3],
        "cpf": ["123.456.789-00", None, "987.654.321-00"],
        "dataNascimento": ["1980-01-01", None, "1970-05-05"],
        "nomeCivil": ["ANA", "BIA", "CARLA"],
        "ufNascimento": ["SP", "RJ", "MG"],
        "municipioNascimento": ["SAO PAULO", None, "BH"],
        "_source_url": ["http://camara/x1", "http://camara/x2", "http://camara/x3"],
    }
    dados.update(kwargs)
    return pl.DataFrame(dados)


def test_resolve_por_cpf_cria_aliases_camara_so_com_cpf_nao_nulo():
    aliases = resolve_por_cpf(_deputado_detalhe())
    assert aliases.height == 2
    assert set(aliases["fonte"].unique()) == {FONTE_CAMARA}
    assert set(aliases["metodo"].unique()) == {"cpf_exato"}
    assert set(aliases["confianca"].unique()) == {"alta"}
    assert set(aliases["id_natural"].to_list()) == {1, 3}
    assert set(aliases["politico_id"].to_list()) == {"pol_camara_1", "pol_camara_3"}


def test_resolve_por_cpf_vazio_retorna_schema():
    aliases = resolve_por_cpf(pl.DataFrame(schema=_deputado_detalhe().schema))
    assert aliases.is_empty()
    assert "politico_id" in aliases.columns


# ─────────────────────────────────────────────────────────────────────────────
# resolve_por_chaves_naturais
# ─────────────────────────────────────────────────────────────────────────────
def _deputados():
    return pl.DataFrame(
        {
            "id": [1, 1, 2],
            "nome": ["ANA", "ANA", "BIA"],
            "uf": ["SP", "SP", "RJ"],
            "idLegislatura": [56, 57, 57],
            "_source_url": ["http://camara/d1", "http://camara/d1", "http://camara/d2"],
        }
    )


def _senadores():
    return pl.DataFrame(
        {
            "codigo": [10, 10, 11],
            "nome": ["PEDRO", "PEDRO", "PAULO"],
            "nome_completo": ["PEDRO DE SOUZA", "PEDRO DE SOUZA", "PAULO DA SILVA"],
            "uf": ["MG", "MG", "BA"],
            "segunda_legislatura": [55, 56, 56],
            "_source_url": ["http://senado/s10", "http://senado/s10", "http://senado/s11"],
        }
    )


def test_resolve_por_chaves_naturais_dedup_por_id():
    aliases = resolve_por_chaves_naturais(_deputados(), _senadores())
    camara = aliases.filter(pl.col("fonte") == FONTE_CAMARA)
    senado = aliases.filter(pl.col("fonte") == FONTE_SENADO)
    # deputado 1 aparece 2x na Silver; alias único
    assert camara.height == 2
    assert set(camara["politico_id"].to_list()) == {"pol_camara_1", "pol_camara_2"}
    assert set(senado["politico_id"].to_list()) == {"pol_senado_10", "pol_senado_11"}


# ─────────────────────────────────────────────────────────────────────────────
# resolve_fuzzy_camara_senado
# ─────────────────────────────────────────────────────────────────────────────
def test_fuzzy_nome_uf_merge_nao_ambiguo_confianca_media():
    dep = pl.DataFrame(
        {
            "id": [5],
            "nome": ["MARIA SILVA"],
            "uf": ["CE"],
            "idLegislatura": [57],
            "_source_url": ["u/d"],
        }
    )
    det = pl.DataFrame(
        {"id": [5], "dataNascimento": [None], "cpf": [None], "nomeCivil": ["MARIA SILVA"],
         "ufNascimento": ["CE"], "municipioNascimento": [None], "_source_url": ["u/d"]}
    )
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["MARIA SILVA"], "uf": ["CE"], "nome_completo": ["MARIA SILVA"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    aliases, resolucoes = resolve_fuzzy_camara_senado(dep, det, sen)
    assert aliases.height == 1
    row = aliases.row(0, named=True)
    assert row["fonte"] == FONTE_SENADO and row["id_natural"] == 77
    assert row["politico_id"] == "pol_camara_5"
    assert row["confianca"] == "media"
    assert resolucoes.height == 1
    assert resolucoes["confianca"].to_list() == ["media"]


def test_fuzzy_nome_dn_uf_confianca_alta_quando_senadores_detalhe():
    dep = pl.DataFrame(
        {
            "id": [5],
            "nome": ["MARIA SILVA"],
            "uf": ["CE"],
            "idLegislatura": [57],
            "_source_url": ["u/d"],
        }
    )
    det = pl.DataFrame(
        {"id": [5], "dataNascimento": ["1975-03-10"], "cpf": [None], "nomeCivil": ["MARIA SILVA"],
         "ufNascimento": ["CE"], "municipioNascimento": [None], "_source_url": ["u/d"]}
    )
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["MARIA SILVA"], "uf": ["CE"], "nome_completo": ["MARIA SILVA"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    sen_det = pl.DataFrame(
        {"codigo": [77], "data_nascimento": ["1975-03-10"], "_source_url": ["u/sd"]}
    )
    aliases, resolucoes = resolve_fuzzy_camara_senado(dep, det, sen, senadores_detalhe=sen_det)
    assert aliases.height == 1
    assert aliases["confianca"].to_list() == ["alta"]
    assert aliases["metodo"].to_list() == ["nome_normalizado_dn_uf"]


def test_fuzzy_dn_divergente_vira_candidata_revisao_sem_merge():
    """
    DN presente nos dois lados mas divergente não confirma o merge.

    Com ``senadores_detalhe`` ingerido, nome+UF casam mas a data de nascimento
    difere (1975-03-10 na Câmara vs 1982-11-02 no Senado): o par vai para
    ``resolucoes`` com confiança baixa e justificativa de DN divergente — nunca
    alias em ``media`` (era o comportamento errado corrigido no code-review).
    """
    dep = pl.DataFrame(
        {
            "id": [5],
            "nome": ["MARIA SILVA"],
            "uf": ["CE"],
            "idLegislatura": [57],
            "_source_url": ["u/d"],
        }
    )
    det = pl.DataFrame(
        {"id": [5], "dataNascimento": ["1975-03-10"], "cpf": [None], "nomeCivil": ["MARIA SILVA"],
         "ufNascimento": ["CE"], "municipioNascimento": [None], "_source_url": ["u/d"]}
    )
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["MARIA SILVA"], "uf": ["CE"], "nome_completo": ["MARIA SILVA"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    sen_det = pl.DataFrame(
        {"codigo": [77], "data_nascimento": ["1982-11-02"], "_source_url": ["u/sd"]}
    )
    aliases, resolucoes = resolve_fuzzy_camara_senado(dep, det, sen, senadores_detalhe=sen_det)
    assert aliases.is_empty()
    assert resolucoes.height == 1
    row = resolucoes.row(0, named=True)
    assert row["confianca"] == "baixa"
    assert "DN divergente" in row["justificativa"]


def test_fuzzy_uf_divergente_vira_candidata_revisao_sem_merge():
    dep = pl.DataFrame(
        {
            "id": [5],
            "nome": ["MARIA SILVA"],
            "uf": ["CE"],
            "idLegislatura": [57],
            "_source_url": ["u/d"],
        }
    )
    det = pl.DataFrame(
        {"id": [5], "dataNascimento": [None], "cpf": [None], "nomeCivil": ["MARIA SILVA"],
         "ufNascimento": ["CE"], "municipioNascimento": [None], "_source_url": ["u/d"]}
    )
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["MARIA SILVA"], "uf": ["RJ"], "nome_completo": ["MARIA SILVA"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    aliases, resolucoes = resolve_fuzzy_camara_senado(dep, det, sen)
    assert aliases.is_empty()
    assert resolucoes.height == 1
    assert resolucoes["confianca"].to_list() == ["baixa"]


def test_fuzzy_nome_ambiguo_vira_candidata_revisao_sem_merge():
    dep = pl.DataFrame(
        {"id": [5, 6], "nome": ["JOSE SILVA", "JOSE SILVA"], "uf": ["CE", "CE"],
         "idLegislatura": [57, 57], "_source_url": ["u/d5", "u/d6"]}
    )
    det = pl.DataFrame(
        {"id": [5, 6], "dataNascimento": [None, None], "cpf": [None, None],
         "nomeCivil": ["JOSE SILVA", "JOSE SILVA"], "ufNascimento": ["CE", "CE"],
         "municipioNascimento": [None, None], "_source_url": ["u/d5", "u/d6"]}
    )
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["JOSE SILVA"], "uf": ["CE"], "nome_completo": ["JOSE SILVA"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    aliases, resolucoes = resolve_fuzzy_camara_senado(dep, det, sen)
    assert aliases.is_empty()
    assert resolucoes.height == 2  # uma candidata por par (2 deputados)
    assert resolucoes["confianca"].unique().to_list() == ["baixa"]


# ─────────────────────────────────────────────────────────────────────────────
# resolve_roster_servidor
# ─────────────────────────────────────────────────────────────────────────────
def _servidores():
    return pl.DataFrame(
        {
            "sequencial": [101, 102, 103],
            "nome": ["PEDRO", "JOAO SERVIDOR", "PEDRO"],
            "lotacao_sigla": ["GAB", "GAB", "GAB"],
            "lotacao_nome": ["Gabinete do Senador PEDRO", "Gabinete do Senador PEDRO", "Outra"],
            "_source_url": ["u/s1", "u/s2", "u/s3"],
        }
    )


def test_roster_servidor_casa_com_senador_unico():
    sen = pl.DataFrame(
        {"codigo": [10], "nome": ["PEDRO"], "nome_completo": ["PEDRO DE SOUZA"], "uf": ["MG"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    aliases, resolucoes = resolve_roster_servidor(_servidores(), sen)
    # nome "PEDRO" tem 2 servidores → ambíguo → candidata_revisao, sem alias
    assert aliases.is_empty()
    assert resolucoes.height == 2
    assert resolucoes["confianca"].unique().to_list() == ["baixa"]


def test_roster_servidor_merge_unico():
    serv = pl.DataFrame(
        {"sequencial": [101], "nome": ["MARIA AUXILIADORA"], "lotacao_sigla": ["GAB"],
         "lotacao_nome": ["Gabinete do Senador X"], "_source_url": ["u/s"]}
    )
    sen = pl.DataFrame(
        {"codigo": [10], "nome": ["MARIA AUXILIADORA"], "nome_completo": ["MARIA AUXILIADORA"],
         "uf": ["MG"], "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    aliases, resolucoes = resolve_roster_servidor(serv, sen)
    assert aliases.height == 1
    row = aliases.row(0, named=True)
    assert row["fonte"] == FONTE_SERVIDOR and row["id_natural"] == 101
    assert row["politico_id"] == "pol_senado_10"
    assert row["confianca"] == "media"
    # merge confirmado é auditado em resolucoes (nunca silencioso)
    assert resolucoes.height == 1
    assert resolucoes["confianca"].to_list() == ["media"]


# ─────────────────────────────────────────────────────────────────────────────
# montar_ancoras — integração
# ─────────────────────────────────────────────────────────────────────────────
def test_montar_ancoras_deputado_e_senador_mesma_pessoa_um_politico():
    dep = pl.DataFrame({"id": [5], "nome": ["MARIA SILVA"], "uf": ["CE"], "idLegislatura": [57],
                        "_source_url": ["u/d"]})
    det = pl.DataFrame(
        {
            "id": [5],
            "dataNascimento": [None],
            "cpf": ["111.222.333-44"],
            "nomeCivil": ["MARIA SILVA"],
            "ufNascimento": ["CE"],
            "municipioNascimento": [None],
            "_source_url": ["u/d"],
        }
    )
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["MARIA SILVA"], "nome_completo": ["MARIA SILVA"], "uf": ["CE"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    politicos, aliases, resolucoes = montar_ancoras(dep, det, sen)
    # Uma única pessoa: pol_camara_5 (CPF presente), senador absorvido
    assert politicos.height == 1
    assert politicos["politico_id"].to_list() == ["pol_camara_5"]
    assert politicos["cpf"].to_list() == ["111.222.333-44"]
    # alias do senador aponta para a âncora da Câmara
    sen_alias = aliases.filter(pl.col("fonte") == FONTE_SENADO)
    assert sen_alias["politico_id"].to_list() == ["pol_camara_5"]
    assert resolucoes.height >= 1  # merge auditado


def test_montar_ancoras_senador_sem_deputado_ganha_pol_senado():
    dep = pl.DataFrame(schema={"id": pl.Int64, "nome": pl.String, "uf": pl.String,
                               "idLegislatura": pl.Int64, "_source_url": pl.String})
    det = pl.DataFrame(schema={"id": pl.Int64, "dataNascimento": pl.String, "cpf": pl.String,
                               "nomeCivil": pl.String, "ufNascimento": pl.String,
                               "municipioNascimento": pl.String, "_source_url": pl.String})
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["MARIA SILVA"], "nome_completo": ["MARIA SILVA"], "uf": ["CE"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    politicos, aliases, _ = montar_ancoras(dep, det, sen)
    assert politicos["politico_id"].to_list() == ["pol_senado_77"]
    assert politicos["nome_civil"].to_list() == ["MARIA SILVA"]
    assert aliases["politico_id"].unique().to_list() == ["pol_senado_77"]


def test_montar_ancoras_servidor_do_senador_segue_ancora_final():
    dep = pl.DataFrame({"id": [5], "nome": ["MARIA SILVA"], "uf": ["CE"], "idLegislatura": [57],
                        "_source_url": ["u/d"]})
    det = pl.DataFrame(
        {"id": [5], "dataNascimento": [None], "cpf": [None], "nomeCivil": ["MARIA SILVA"],
         "ufNascimento": ["CE"], "municipioNascimento": [None], "_source_url": ["u/d"]}
    )
    sen = pl.DataFrame(
        {"codigo": [77], "nome": ["MARIA SILVA"], "nome_completo": ["MARIA SILVA"], "uf": ["CE"],
         "segunda_legislatura": [56], "_source_url": ["u/s"]}
    )
    serv = pl.DataFrame(
        {"sequencial": [101], "nome": ["MARIA SILVA"], "lotacao_sigla": ["GAB"],
         "lotacao_nome": ["Gabinete do Senador MARIA SILVA"], "_source_url": ["u/sv"]}
    )
    politicos, aliases, _ = montar_ancoras(dep, det, sen, servidores=serv)
    # servidor → senador 77 → absorbido pela Câmara → pol_camara_5
    serv_alias = aliases.filter(pl.col("fonte") == FONTE_SERVIDOR)
    assert serv_alias["politico_id"].to_list() == ["pol_camara_5"]
    assert len(politicos["politico_id"].unique()) == 1
