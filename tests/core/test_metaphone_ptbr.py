"""Testes unitários para o algoritmo fonético Metaphone PT-BR (Issue 06)."""

import polars as pl

from ipolitico.core.metaphone_ptbr import (
    limpar_e_remover_agnomes,
    metaphone_ptbr_expr,
    metaphone_ptbr_str,
)


def test_limpar_e_remover_agnomes_remove_titulos_e_conectores():
    """Garante remoção de partículas 'de/da/do' e agnomes 'junior/filho/neto'."""
    nomes = [
        "LUIZ INACIO LULA DA SILVA",
        "ARTHUR CESAR PEREIRA DE LIRA FILHO",
        "RODRIGO FELINTO IBARRA EPITACIO MAIA NETO",
        "JOSE SARNEY DE ARAUJO COSTA JUNIOR",
        "MARIA DO ROSARIO NUNES",
    ]
    df = pl.DataFrame({"nome": nomes})
    res = df.select(limpar_e_remover_agnomes(pl.col("nome")).alias("limpo"))
    esperados = [
        "LUIZ INACIO LULA SILVA",
        "ARTHUR CESAR PEREIRA LIRA",
        "RODRIGO FELINTO IBARRA EPITACIO MAIA",
        "JOSE SARNEY ARAUJO COSTA",
        "MARIA ROSARIO NUNES",
    ]
    assert res["limpo"].to_list() == esperados


def test_metaphone_ptbr_str_homofonos_brasileiros():
    """Garante que grafias foneticamente idênticas geram o mesmo código."""
    # S vs Z intervocálico
    assert metaphone_ptbr_str("LUIZ") == metaphone_ptbr_str("LUIS")
    assert metaphone_ptbr_str("SOUSA") == metaphone_ptbr_str("SOUZA")
    assert metaphone_ptbr_str("TERESA") == metaphone_ptbr_str("TEREZA")

    # C vs S vs Ç
    assert metaphone_ptbr_str("CEZAR") == metaphone_ptbr_str("CESAR")
    assert metaphone_ptbr_str("CELIA") == metaphone_ptbr_str("SELIA")

    # F vs PH
    assert metaphone_ptbr_str("FELIPE") == metaphone_ptbr_str("PHELIPPE")

    # K vs C
    assert metaphone_ptbr_str("KATIA") == metaphone_ptbr_str("CATIA")
    assert metaphone_ptbr_str("CASSIANO") == metaphone_ptbr_str("KASSIANO")

    # H mudo
    assert metaphone_ptbr_str("HELENA") == metaphone_ptbr_str("ELENA")
    assert metaphone_ptbr_str("HUGO") == metaphone_ptbr_str("UGO")


def test_metaphone_ptbr_expr_vetorizado():
    """Valida execução da expressão vetorizada Polars sobre DataFrame."""
    df = pl.DataFrame(
        {
            "nome": [
                "LUIZ INACIO LULA DA SILVA",
                "LUIS INACIO LULA DA SILVA",
                "ARTHUR DE LIRA",
                "ARTUR DE LIRA",
                None,
                "",
            ]
        }
    )
    res = df.with_columns(metaphone_ptbr_expr(pl.col("nome")).alias("meta"))

    # Nomes homófonos devem ter exatamente o mesmo metaphone
    assert res["meta"][0] == res["meta"][1]
    assert res["meta"][2] == res["meta"][3]
    # Nulo e vazio preservam segurança
    assert res["meta"][4] is None
    assert res["meta"][5] == ""


def test_metaphone_ptbr_str_casos_borda():
    """Trata strings nulas, vazias ou com pontuação estranha."""
    assert metaphone_ptbr_str("") == ""
    assert metaphone_ptbr_str("   ") == ""
    assert metaphone_ptbr_str("123 !@#") == ""
    assert metaphone_ptbr_str("O'NEILL") == metaphone_ptbr_str("ONEILL")
