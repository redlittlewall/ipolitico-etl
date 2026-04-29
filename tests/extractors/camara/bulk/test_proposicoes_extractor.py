import polars as pl
from ipolitico.extractors.camara.bulk.proposicoes_bulk import ProposicoesBulkExtractor

# ==========================================
# TESTES: PROPOSIÇÕES BULK (Schema Drift)
# ==========================================


def test_proposicoes_bulk_schema_standardization():
    """
    Garante que a coluna de data (dataApresentacao)
    é convertida do CSV (String) para um tipo forte Datetime no Polars.
    """
    ext = ProposicoesBulkExtractor(None)
    df_sujo = pl.DataFrame({"dataApresentacao": ["2026-05-10T14:00:00"]})

    df_limpo = ext._standardize_schema(df_sujo)

    # A tipagem tem que ter sido forçada para Datetime
    assert df_limpo["dataApresentacao"].dtype == pl.Datetime


def test_proposicoes_bulk_missing_date_column():
    """
    O governo mandou o CSV de Proposições sem a coluna 'dataApresentacao'.
    O Polars não pode estourar um 'ColumnNotFoundError'.
    """
    ext = ProposicoesBulkExtractor(None)

    # DF sem a coluna esperada
    df_sujo = pl.DataFrame({"outra_coluna": ["PL 123/2026"]})
    df_limpo = ext._standardize_schema(df_sujo)

    # Deve passar reto e manter os dados que existem
    assert "outra_coluna" in df_limpo.columns
    assert "dataApresentacao" not in df_limpo.columns
