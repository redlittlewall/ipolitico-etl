"""Testes para os transformadores da Fatia 3 da CGU (Convênios e Repasses).

Testes puros em Polars sem I/O sobre DataFrames sintéticos:
- PortalConveniosTransformer
- PortalConveniosAditivosTransformer
"""

import polars as pl
import pytest

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.convenios_transformer import (
    PortalConveniosTransformer,
)
from ipolitico.transformers.portal_transparencia.convenios_aditivos_transformer import (
    PortalConveniosAditivosTransformer,
)


class TestPortalConveniosTransformer:
    """Testes para o PortalConveniosTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalConveniosTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalConveniosTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/convenios?pagina=1"],
            "id": [5001],
            "dataReferencia": ["23/08/2026"],
            "dataInicioVigencia": ["01/05/2023"],
            "dataFinalVigencia": ["01/05/2026"],
            "dataPublicacao": ["10/05/2023"],
            "dataUltimaLiberacao": ["15/06/2024"],
            "dataConclusao": [None],
            "situacao": ["Em execução"],
            "numeroProcesso": ["00055.000123/2023-44"],
            "valor": [5000000.00],
            "valorLiberado": [2500000.00],
            "valorContrapartida": [500000.00],
            "valorDaUltimaLiberacao": [1000000.00],
            "dimConvenio": [{
                "codigo": "CV-899123",
                "objeto": "Construção de Unidades Básicas de Saúde no Município de Exemplo",
                "numero": "899123/2023",
            }],
            "convenente": [{
                "id": 1234,
                "cpfFormatado": None,
                "cnpjFormatado": "12.345.678/0001-90",
                "numeroInscricaoSocial": None,
                "nome": "PREFEITURA MUNICIPAL DE EXEMPLO",
                "razaoSocialReceita": "PREFEITURA MUNICIPAL DE EXEMPLO",
                "nomeFantasiaReceita": None,
                "tipo": "JURIDICA",
            }],
            "municipioConvenente": [{
                "codigoIBGE": "3106200",
                "nomeIBGE": "Belo Horizonte",
                "codigoRegiao": "3",
                "nomeRegiao": "Sudeste",
                "pais": "Brasil",
                "uf": {
                    "sigla": "MG",
                    "nome": "Minas Gerais",
                },
            }],
            "orgao": [{
                "codigoSIAFI": "36000",
                "nome": "MINISTERIO DA SAUDE",
                "cnpj": "00394700000100",
                "sigla": "MS",
                "descricaoPoder": "Executivo",
            }],
            "unidadeGestora": [{
                "codigo": "250001",
                "nome": "FUNDO NACIONAL DE SAUDE",
                "descricaoPoder": "Executivo",
            }],
            "tipoInstrumento": [{
                "codigo": "CONV",
                "descricao": "Convênio",
            }],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CONVENIOS.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["id"][0] == 5001
        assert result["valor"][0] == 5000000.00
        assert result["valorLiberado"][0] == 2500000.00
        assert result["dimConvenio_numero"][0] == "899123/2023"
        assert result["convenente_cnpjFormatado"][0] == "12.345.678/0001-90"
        assert result["municipioConvenente_nomeIBGE"][0] == "Belo Horizonte"
        assert result["municipioConvenente_uf_sigla"][0] == "MG"
        assert result["orgao_sigla"][0] == "MS"
        assert result["unidadeGestora_nome"][0] == "FUNDO NACIONAL DE SAUDE"
        assert result["tipoInstrumento_descricao"][0] == "Convênio"


class TestPortalConveniosAditivosTransformer:
    """Testes para o PortalConveniosAditivosTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalConveniosAditivosTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalConveniosAditivosTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/convenios?id=5001"],
            "idConvenio": [5001],
            "numero": ["TA-02/2024"],
            "dataPublicacao": ["15/06/2024"],
            "objetoAditivo": ["Prorrogação de vigência e suplementação orçamentária"],
            "valorAditivo": [250000.00],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CONVENIOS_ADITIVOS.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["idConvenio"][0] == 5001
        assert result["numero"][0] == "TA-02/2024"
        assert result["valorAditivo"][0] == 250000.00
        assert "Prorrogação" in result["objetoAditivo"][0]
