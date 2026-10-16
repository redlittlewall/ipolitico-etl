"""Testes para os transformadores da Fatia 2 da CGU (Compras Públicas).

Testes puros em Polars sem I/O sobre DataFrames sintéticos:
- PortalLicitacoesTransformer
- PortalContratosTransformer
- PortalContratosAditivosTransformer
"""

import polars as pl
import pytest

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.licitacoes_transformer import (
    PortalLicitacoesTransformer,
)
from ipolitico.transformers.portal_transparencia.contratos_transformer import (
    PortalContratosTransformer,
)
from ipolitico.transformers.portal_transparencia.contratos_aditivos_transformer import (
    PortalContratosAditivosTransformer,
)


class TestPortalLicitacoesTransformer:
    """Testes para o PortalLicitacoesTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalLicitacoesTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalLicitacoesTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/licitacoes?pagina=1"],
            "id": [1001],
            "dataResultadoCompra": ["15/03/2024"],
            "dataAbertura": ["01/02/2024"],
            "dataReferencia": ["23/08/2026"],
            "dataPublicacao": ["02/02/2024"],
            "situacaoCompra": ["Homologada"],
            "modalidadeLicitacao": ["Pregão Eletrônico"],
            "instrumentoLegal": ["Lei 14.133/21"],
            "valor": [750000.50],
            "licitacao": [{
                "numero": "001/2024",
                "objeto": "Aquisição de equipamentos de TI",
                "numeroProcesso": "23000.001234/2024-50",
                "contatoResponsavel": "pregoeiro@mec.gov.br",
            }],
            "municipio": [{
                "codigoIBGE": "5300108",
                "nomeIBGE": "Brasília",
                "codigoRegiao": "5",
                "nomeRegiao": "Centro-Oeste",
                "pais": "Brasil",
                "uf": {
                    "sigla": "DF",
                    "nome": "Distrito Federal",
                },
            }],
            "unidadeGestora": [{
                "codigo": "153000",
                "nome": "COORDENACAO-GERAL DE RECURSOS LOGISTICOS",
                "descricaoPoder": "Executivo",
                "orgaoVinculado": {
                    "codigoSIAFI": "26000",
                    "nome": "MINISTERIO DA EDUCACAO",
                    "sigla": "MEC",
                },
                "orgaoMaximo": {
                    "codigo": "26000",
                    "nome": "MINISTERIO DA EDUCACAO",
                    "sigla": "MEC",
                },
            }],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_LICITACOES.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["id"][0] == 1001
        assert result["valor"][0] == 750000.50
        assert result["licitacao_numero"][0] == "001/2024"
        assert result["licitacao_objeto"][0] == "Aquisição de equipamentos de TI"
        assert result["municipio_nomeIBGE"][0] == "Brasília"
        assert result["municipio_uf_sigla"][0] == "DF"
        assert result["unidadeGestora_nome"][0] == "COORDENACAO-GERAL DE RECURSOS LOGISTICOS"
        assert result["unidadeGestora_orgaoVinculado_sigla"][0] == "MEC"
        assert result["unidadeGestora_orgaoMaximo_nome"][0] == "MINISTERIO DA EDUCACAO"


class TestPortalContratosTransformer:
    """Testes para o PortalContratosTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalContratosTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalContratosTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/contratos?pagina=1"],
            "id": [2002],
            "numero": ["CT-045/2023"],
            "objeto": ["Prestação de serviços de nuvem e segurança cibernética"],
            "numeroProcesso": ["00100.00200/2023-11"],
            "fundamentoLegal": ["Art. 75, inciso II da Lei 14.133/2021"],
            "situacaoContrato": ["Ativo"],
            "modalidadeCompra": ["Dispensa de Licitação"],
            "dataAssinatura": ["10/01/2023"],
            "dataPublicacaoDOU": ["12/01/2023"],
            "dataInicioVigencia": ["15/01/2023"],
            "dataFimVigencia": ["15/01/2028"],
            "valorInicialCompra": [1200000.00],
            "valorFinalCompra": [1350000.00],
            "compra": [{
                "numero": "045/2023",
                "objeto": "Serviços de Nuvem",
                "numeroProcesso": "00100.00200/2023-11",
                "contatoResponsavel": "gestor.contrato@gov.br",
            }],
            "unidadeGestora": [{
                "codigo": "110001",
                "nome": "SECRETARIA DE GOVERNO DIGITAL",
                "descricaoPoder": "Executivo",
                "orgaoVinculado": {
                    "codigoSIAFI": "30000",
                    "nome": "MINISTERIO DA GESTAO E DA INOVACAO",
                    "sigla": "MGI",
                },
                "orgaoMaximo": {
                    "codigo": "30000",
                    "nome": "MINISTERIO DA GESTAO E DA INOVACAO",
                    "sigla": "MGI",
                },
            }],
            "unidadeGestoraCompras": [{
                "codigo": "110001",
                "nome": "SECRETARIA DE GOVERNO DIGITAL",
                "descricaoPoder": "Executivo",
            }],
            "fornecedor": [{
                "id": 9999,
                "cpfFormatado": None,
                "cnpjFormatado": "00.111.222/0001-33",
                "numeroInscricaoSocial": None,
                "nome": "CLOUD TECH BRASIL LTDA",
                "razaoSocialReceita": "CLOUD TECH BRASIL LTDA",
                "nomeFantasiaReceita": "CLOUD TECH",
                "tipo": "JURIDICA",
            }],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CONTRATOS.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["id"][0] == 2002
        assert result["numero"][0] == "CT-045/2023"
        assert result["valorInicialCompra"][0] == 1200000.00
        assert result["valorFinalCompra"][0] == 1350000.00
        assert result["compra_numero"][0] == "045/2023"
        assert result["unidadeGestora_orgaoVinculado_sigla"][0] == "MGI"
        assert result["unidadeGestoraCompras_codigo"][0] == "110001"
        assert result["fornecedor_cnpjFormatado"][0] == "00.111.222/0001-33"
        assert result["fornecedor_nome"][0] == "CLOUD TECH BRASIL LTDA"


class TestPortalContratosAditivosTransformer:
    """Testes para o PortalContratosAditivosTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalContratosAditivosTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalContratosAditivosTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/contratos/termo-aditivo?id=2002"],
            "idContrato": [2002],
            "numero": ["TA-01/2024"],
            "dataPublicacao": ["15/01/2024"],
            "objetoAditivo": ["Prorrogação de vigência por 12 meses e acréscimo de 10% no valor"],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CONTRATOS_ADITIVOS.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["idContrato"][0] == 2002
        assert result["numero"][0] == "TA-01/2024"
        assert result["dataPublicacao"][0] == "15/01/2024"
        assert "Prorrogação" in result["objetoAditivo"][0]
