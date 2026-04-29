import polars as pl
from ipolitico.extractors.camara.bulk.despesas_bulk import DespesasBulkExtractor

# ==========================================
# TESTES: DESPESAS BULK (Conversão e Mapeamento)
# ==========================================


def test_despesas_bulk_schema_standardization():
    """
    Testa a resiliência bruta de parsing financeiro:
    1. Tradução do dicionário legado ('nuDeputadoId' -> 'id_deputado')
    2. Conversão do padrão monetário Brasileiro (vírgula) para Americano (Float64)
    3. Casting de datas.
    """
    ext = DespesasBulkExtractor(None)

    df_sujo = pl.DataFrame(
        {
            "nuDeputadoId": ["100"],
            "datEmissao": ["2026-05-10T14:00:00"],
            "vlrLiquido": ["1.234,56"],  # Pegadinha clássica: valor com vírgula
            "vlrDocumento": ["-150,00"],  # Valores negativos (glosas)
            "coluna_inutil": ["lixo"],
        }
    )

    df_limpo = ext._standardize_schema(df_sujo)

    # Valida traduções de nomes
    assert "id_deputado" in df_limpo.columns
    assert "nuDeputadoId" not in df_limpo.columns
    assert "coluna_inutil" in df_limpo.columns  # Colunas desconhecidas não devem ser apagadas

    # Valida casting e conversões decimais
    assert df_limpo["id_deputado"][0] == 100
    assert df_limpo["valorLiquido"][0] == 1234.56
    assert df_limpo["valorDocumento"][0] == -150.00
    assert df_limpo["dataDocumento"].dtype == pl.Datetime


def test_despesas_bulk_missing_columns():
    """
    Garante que a padronização não explode se o CSV vier
    sem uma das colunas listadas no 'mapping' (ignora erros graciosamente
    graças ao strict=False do Polars).
    """
    ext = DespesasBulkExtractor(None)

    # Mandamos um DF quase vazio
    df_sujo = pl.DataFrame({"txtFornecedor": ["Posto Gasolina"]})
    df_limpo = ext._standardize_schema(df_sujo)

    # Renomeou o que tinha
    assert "nomeFornecedor" in df_limpo.columns
    # E não crashou reclamando das outras colunas faltando
