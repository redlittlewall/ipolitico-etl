import polars as pl
import pytest
from ipolitico.extractors.camara.bulk.deputados_bulk import DeputadosBulkExtractor

# ==========================================
# TESTES: DEPUTADOS BULK (Schema Drift)
# ==========================================


def test_deputados_bulk_extracts_id_from_uri():
    """
    [BLINDAGEM] O governo removeu a coluna 'id', mas manteve a 'uri'.
    O sistema deve ser capaz de extrair a PK fatiando a string da URI.
    Cobre as linhas onde 'uri_col' existe e 'id_col' não.
    """
    ext = DeputadosBulkExtractor(None)
    df_sujo = pl.DataFrame({"uri": ["https://dadosabertos.camara.leg.br/api/v2/deputados/12345"]})

    df_limpo = ext._standardize_schema(df_sujo)

    assert "id" in df_limpo.columns
    assert df_limpo["id"][0] == 12345
    assert df_limpo["id"].dtype == pl.Int64


def test_deputados_bulk_renames_capitalized_id():
    """
    [BLINDAGEM] O governo mandou a coluna como 'Id' ou 'ID' em vez de 'id'.
    Bancos de dados case-sensitive (como Postgres, se migrarmos no futuro)
    e o próprio Polars odiariam isso.
    """
    ext = DeputadosBulkExtractor(None)
    df_sujo = pl.DataFrame({"Id": ["99"], "idLegislatura": ["57"]})

    df_limpo = ext._standardize_schema(df_sujo)

    assert "id" in df_limpo.columns
    assert "Id" not in df_limpo.columns
    assert df_limpo["id"][0] == 99
    assert df_limpo["idLegislatura"][0] == 57


def test_deputados_bulk_contract_violation():
    """
    [FAIL-FAST] O governo mudou tudo e não temos nem 'id' nem 'uri'.
    O sistema DEVE abortar imediatamente (ValueError) em vez de corromper o Data Lake
    inserindo registros sem Chave Primária (PK).
    """
    ext = DeputadosBulkExtractor(None)
    df_sujo = pl.DataFrame({"nome_parlamentar": ["Tiririca"]})

    with pytest.raises(ValueError, match="ERRO DE CONTRATO"):
        ext._standardize_schema(df_sujo)
