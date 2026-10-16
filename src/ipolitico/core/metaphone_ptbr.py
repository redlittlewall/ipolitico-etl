"""Algoritmo de fonética e normalização Metaphone PT-BR (Issue 06).

Fornece funções vetorizadas em Polars e auxiliares escalares para normalização
fonética de nomes próprios da língua portuguesa brasileira, mitigando variações
ortográficas (ex: Souza/Sousa, Luiz/Luís, Arthur/Artur, Célia/Sélia, Phelippe/Felipe).
Compatível com a engine de regex em Rust do Polars (sem lookahead/lookbehind).
"""

from __future__ import annotations

import polars as pl

# Expressão regex de preposições conectoras e agnomes comuns
RE_CONECTORES_AGNOMES = r"\b(DE|DA|DO|DAS|DOS|E|JUNIOR|FILHO|NETO|SOBRINHO|SEGUNDO|TERCEIRO)\b"

# Letras duplicadas comuns a serem colapsadas
DUPLICADAS = [
    (r"RR", "R"),
    (r"SS", "S"),
    (r"LL", "L"),
    (r"MM", "M"),
    (r"NN", "N"),
    (r"PP", "P"),
    (r"TT", "T"),
    (r"FF", "F"),
    (r"BB", "B"),
    (r"DD", "D"),
    (r"GG", "G"),
    (r"CC", "K"),
    (r"ZZ", "S"),
]


def limpar_e_remover_agnomes(expr: pl.Expr) -> pl.Expr:
    """Normaliza texto removendo acentos, pontuação, conectores e agnomes de parentesco.

    Args:
        expr: Expressão Polars contendo os nomes em formato texto.

    Returns:
        Expressão Polars com o nome limpo em caixa alta, sem preposições e agnomes.
    """
    return (
        expr.str.to_uppercase()
        .str.normalize("NFKD")
        .str.replace_all(r"\p{Mn}", "")
        .str.replace_all(r"['’`]", "")
        .str.replace_all(r"[^A-Z\s]", " ")
        .str.replace_all(RE_CONECTORES_AGNOMES, " ")
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
    )


def metaphone_ptbr_expr(expr: pl.Expr) -> pl.Expr:
    """Calcula o código fonético Metaphone PT-BR de forma puramente vetorizada.

    Aplica uma sequência determinística de regras fonéticas adaptadas ao português
    brasileiro para unificar grafias equivalentes sem recorrer a loops Python.
    Compatível com o motor regex do Rust (sem lookaround ou backreferences).

    Args:
        expr: Expressão Polars com o texto do nome a ser transformado.

    Returns:
        Expressão Polars com os códigos fonéticos gerados. Nulos são preservados.
    """
    # 1. Limpeza inicial
    e = limpar_e_remover_agnomes(expr)

    # 2. Substituições diretas
    e = e.str.replace_all(r"Y", "I").str.replace_all(r"W", "V")
    e = e.str.replace_all(r"PH", "F")
    e = e.str.replace_all(r"CH", "X").str.replace_all(r"SH", "X")

    # Digrafos com H que preservam fonética
    e = e.str.replace_all(r"LH", "L").str.replace_all(r"NH", "N")

    # H mudo restante é eliminado
    e = e.str.replace_all(r"H", "")

    # C / SC / XC antes de E ou I -> S
    e = e.str.replace_all(r"[SX]C([EI])", r"S$1")
    e = e.str.replace_all(r"C([EI])", r"S$1")

    # G antes de E ou I -> J
    e = e.str.replace_all(r"G([EI])", r"J$1")

    # QU antes de E ou I -> K; QU antes de A ou O -> KU
    e = e.str.replace_all(r"QU([EI])", r"K$1")
    e = e.str.replace_all(r"QU([AO])", r"KU$1")

    # C restante vira K
    e = e.str.replace_all(r"C", "K")

    # Z no fim de palavra -> S
    e = e.str.replace_all(r"Z\b", "S")

    # Z restante unificado com S
    e = e.str.replace_all(r"Z", "S")

    # Colapso de consoantes duplicadas
    for padrao, subst in DUPLICADAS:
        e = e.str.replace_all(padrao, subst)

    # Espaços colapsados e sem bordas
    e = e.str.replace_all(r"\s+", " ").str.strip_chars()

    return (
        pl.when(expr.is_null())
        .then(pl.lit(None, dtype=pl.String))
        .when(expr.str.strip_chars() == "")
        .then(pl.lit("", dtype=pl.String))
        .otherwise(e)
    )


def metaphone_ptbr_str(nome: str | None) -> str:
    """Versão escalar do Metaphone PT-BR para uso pontual e testes.

    Args:
        nome: String contendo o nome a ser processado, ou None.

    Returns:
        String contendo a chave fonética resultante, ou string vazia se nulo/vazio.
    """
    if nome is None:
        return ""
    df = pl.DataFrame({"nome": [nome]})
    res = df.select(metaphone_ptbr_expr(pl.col("nome")).alias("meta"))
    val = res["meta"][0]
    return "" if val is None else val
