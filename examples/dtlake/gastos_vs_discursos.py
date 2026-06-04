"""
Correlação entre Gastos de Gabinete e Atividade em Plenário.

Será que deputados com maiores gastos de gabinete também são os que
mais discursam? Cruza dados de despesas, discursos e perfil dos
deputados para explorar essa relação.

Domínios utilizados: despesas, discursos, deputados
"""

from pathlib import Path

import polars as pl
from ipolitico.core.logger import setup_logger

logger = setup_logger(__name__)
DATALAKE_PATH = Path("data/datalake")


def _gold_path(table: str) -> Path:
    return DATALAKE_PATH / "gold" / table / f"{table}.parquet"


def _fmt_brl(value: float) -> str:
    """Formata valor numérico como moeda brasileira (R$ 1.234,56)."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    paths = {
        "despesas": _gold_path("despesas"),
        "discursos": _gold_path("discursos"),
        "deputados": _gold_path("deputados"),
    }

    missing = [k for k, p in paths.items() if not p.exists()]
    if missing:
        logger.warning("Dados ausentes: %s. Execute o ETL primeiro!", ", ".join(missing))
        return

    try:
        lazy_gastos = pl.scan_parquet(paths["despesas"])
        lazy_discursos = pl.scan_parquet(paths["discursos"])
        lazy_dep = pl.scan_parquet(paths["deputados"])

        # Agrega gastos por deputado
        gastos_agg = lazy_gastos.group_by("id_deputado").agg(
            pl.col("valorLiquido").sum().alias("total_gasto"),
            pl.col("valorLiquido").mean().alias("media_por_despesa"),
            pl.col("nomeFornecedor").n_unique().alias("qtd_fornecedores"),
            pl.len().alias("qtd_despesas"),
        )

        # Agrega discursos por deputado
        discursos_agg = lazy_discursos.group_by("id_deputado").agg(
            pl.len().alias("qtd_discursos"),
            pl.col("transcricao")
            .fill_null("")
            .str.len_chars()
            .sum()
            .alias("total_caracteres_discursos"),
            pl.col("tipoDiscurso").n_unique().alias("tipos_discurso"),
        )

        # Junta tudo com perfil do deputado
        perfil = (
            gastos_agg.join(discursos_agg, on="id_deputado", how="full")
            .join(
                lazy_dep.select(["id", "nome", "partido", "uf"]),
                left_on="id_deputado",
                right_on="id",
                how="left",
            )
            .with_columns(
                pl.col("total_gasto").fill_null(0.0),
                pl.col("qtd_discursos").fill_null(0),
                pl.col("total_caracteres_discursos").fill_null(0),
            )
            .sort("total_gasto", descending=True)
        )

        logger.info("\n=== TOP 15 DEPUTADOS POR GASTO TOTAL (vs. discursos) ===")
        top_gastos = perfil.select(
            [
                "nome",
                "partido",
                "uf",
                pl.col("total_gasto")
                .map_elements(_fmt_brl, return_dtype=pl.String)
                .alias("total_gasto_br"),
                "qtd_despesas",
                "qtd_discursos",
            ]
        ).limit(15)

        with pl.Config(fmt_str_lengths=80):
            print(top_gastos.collect())

        # Deputados que mais discursam (vs. gastos)
        logger.info("\n=== TOP 15 DEPUTADOS POR QUANTIDADE DE DISCURSOS (vs. gastos) ===")
        top_discursos = (
            perfil.select(
                [
                    "nome",
                    "partido",
                    "uf",
                    "qtd_discursos",
                    pl.col("total_gasto")
                    .map_elements(_fmt_brl, return_dtype=pl.String)
                    .alias("total_gasto_br"),
                ]
            )
            .sort("qtd_discursos", descending=True)
            .limit(15)
        )

        with pl.Config(fmt_str_lengths=80):
            print(top_discursos.collect())

        # Correlação: gasto vs discursos
        correl = perfil.select(
            pl.corr("total_gasto", "qtd_discursos").alias("correlacao_gasto_discursos"),
            pl.corr("total_gasto", "total_caracteres_discursos").alias(
                "correlacao_gasto_caracteres"
            ),
        ).collect()

        logger.info("\n=== CORRELAÇÃO GASTOS × DISCURSOS ===")
        print(correl)

    except Exception as e:
        logger.error("Erro na análise gastos vs discursos: %s", e)


if __name__ == "__main__":
    main()
