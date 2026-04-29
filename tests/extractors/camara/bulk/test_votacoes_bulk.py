import polars as pl
from ipolitico.extractors.camara.bulk.votacoes_bulk import VotacoesBulkExtractor, VotosBulkExtractor

# ==========================================
# TESTES: VOTAÇÕES BULK (Schema Drift)
# ==========================================


def test_votacoes_bulk_schema_standardization():
    """[BLINDAGEM] Garante que as colunas de data são convertidas para Datetime."""
    ext = VotacoesBulkExtractor(None)
    df_sujo = pl.DataFrame(
        {"data": ["2026-05-10T14:00:00"], "dataHoraRegistro": ["2026-05-10T14:30:00"]}
    )

    df_limpo = ext._standardize_schema(df_sujo)

    assert df_limpo["data"].dtype == pl.Datetime
    assert df_limpo["dataHoraRegistro"].dtype == pl.Datetime


def test_votacoes_bulk_missing_date_columns():
    """[BLINDAGEM] O governo mandou o CSV sem datas. Não pode estourar com with_columns([])."""
    ext = VotacoesBulkExtractor(None)
    df_sujo = pl.DataFrame({"outra_coluna": ["VOT-123"]})

    df_limpo = ext._standardize_schema(df_sujo)
    assert "outra_coluna" in df_limpo.columns
    assert "data" not in df_limpo.columns


# ==========================================
# TESTES: VOTOS BULK (Schema Drift)
# ==========================================


def test_votos_bulk_schema_standardization():
    """[BLINDAGEM] Traduz o idDeputado legado e tipa como Int64 forte."""
    ext = VotosBulkExtractor(None)
    df_sujo = pl.DataFrame({"idDeputado": ["999"], "voto": ["Sim"]})

    df_limpo = ext._standardize_schema(df_sujo)

    assert "deputado_id" in df_limpo.columns
    assert "idDeputado" not in df_limpo.columns
    assert df_limpo["deputado_id"][0] == 999
    assert df_limpo["deputado_id"].dtype == pl.Int64


def test_votos_bulk_missing_id_column():
    """[BLINDAGEM] O governo mandou o CSV sem idDeputado. Não pode estourar ColumnNotFoundError."""
    ext = VotosBulkExtractor(None)
    df_sujo = pl.DataFrame({"voto": ["Sim"]})

    df_limpo = ext._standardize_schema(df_sujo)
    assert "voto" in df_limpo.columns
    assert "deputado_id" not in df_limpo.columns
