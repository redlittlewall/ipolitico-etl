from pathlib import Path

import polars as pl
from ipolitico.core.logger import setup_logger

logger = setup_logger()

DATALAKE_PATH = Path("datalake")


def main():
    logger.info("Iniciando Auditoria Global no Data Lake...")

    if not DATALAKE_PATH.exists():
        logger.error(f"Diretório {DATALAKE_PATH} não encontrado. Execute o ETL primeiro.")
        return

    # Dicionário mapeando a tabela para a sua coluna temporal mais representativa
    # Tabelas que não estão aqui serão consideradas "Estáticas" (apenas contagem de volume)
    COLUNAS_TEMPORAIS = {
        "deputados_discursos": "dataHoraInicio",
        "deputados_historico": "dataHora",
        "deputados_orgaos": "dataInicio",
        "deputados_eventos": "dataHoraInicio",
        "deputados_ocupacoes": "anoInicio",
        "deputados_mandatos_externos": "anoInicio",
        "despesas": "dataDocumento",
        "proposicoes": "dataApresentacao",
        "votacoes": "data",
    }

    resultados = []

    # Lê dinamicamente todos os arquivos .parquet na pasta
    arquivos = list(DATALAKE_PATH.glob("*.parquet"))

    if not arquivos:
        logger.warning("Nenhum arquivo .parquet encontrado no Data Lake.")
        return

    for arquivo_parquet in arquivos:
        tabela = arquivo_parquet.stem  # Pega o nome do ficheiro sem o .parquet
        coluna_data = COLUNAS_TEMPORAIS.get(tabela)

        try:
            lazy_df = pl.scan_parquet(arquivo_parquet)
            colunas_existentes = lazy_df.collect_schema().names()

            # Conta SEMPRE o total de linhas (muito rápido no Parquet)
            total = lazy_df.select(pl.len()).collect().item()

            mais_antigo = "Estática"
            mais_recente = "Estática"

            # Se a tabela tem uma coluna temporal mapeada e ela existe no schema
            if coluna_data and coluna_data in colunas_existentes:
                agregacao = (
                    lazy_df.filter(pl.col(coluna_data).is_not_null()).select(
                        [
                            pl.col(coluna_data).cast(pl.String).min().alias("min_data"),
                            pl.col(coluna_data).cast(pl.String).max().alias("max_data"),
                        ]
                    )
                ).collect()

                if not agregacao.is_empty() and agregacao["min_data"][0] is not None:
                    mais_antigo = str(agregacao["min_data"][0])[:10]
                    mais_recente = str(agregacao["max_data"][0])[:10]

            resultados.append(
                {
                    "Tabela": tabela,
                    "Total Linhas": total,
                    "Mais Antigo": mais_antigo,
                    "Mais Recente": mais_recente,
                }
            )

            logger.info(f"     ∟ Analisado {tabela}: {total} registos.")

        except Exception as e:
            logger.error(f"Erro ao processar {tabela}: {e}")

    # Ordenar os resultados alfabeticamente para facilitar a leitura
    resultados = sorted(resultados, key=lambda x: x["Tabela"])

    if resultados:
        df_relatorio = pl.DataFrame(resultados)
        logger.info("\n=== RELATÓRIO DE OBSERVABILIDADE GLOBAL ===")
        # tbl_rows=-1 garante que o Polars não oculta linhas se tivermos mais de 8 tabelas
        with pl.Config(
            tbl_formatting="ASCII_MARKDOWN", tbl_hide_column_data_types=True, tbl_rows=-1
        ):
            print(df_relatorio)


if __name__ == "__main__":
    main()
