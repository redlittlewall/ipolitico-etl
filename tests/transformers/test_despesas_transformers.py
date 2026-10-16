"""Testes para os transformadores da Fatia 4 da CGU (Despesas, Empenhos e Pagamentos).

Testes puros em Polars sem I/O sobre DataFrames sintéticos:
- PortalDespesasEmpenhosTransformer
- PortalDespesasPagamentosTransformer
"""

import polars as pl
import pytest

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.despesas_empenhos_transformer import (
    PortalDespesasEmpenhosTransformer,
)
from ipolitico.transformers.portal_transparencia.despesas_pagamentos_transformer import (
    PortalDespesasPagamentosTransformer,
)


class TestPortalDespesasEmpenhosTransformer:
    """Testes para o PortalDespesasEmpenhosTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalDespesasEmpenhosTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalDespesasEmpenhosTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/despesas/documentos?dataEmissao=15/01/2024&fase=1&pagina=1"],
            "data": ["15/01/2024"],
            "documento": ["2024NE000123"],
            "documentoResumido": ["2024NE000123"],
            "observacao": ["AQUISIÇÃO DE EQUIPAMENTOS HOSPITALARES"],
            "funcao": ["Saúde"],
            "subfuncao": ["Atenção Básica"],
            "programa": ["ATENCAO ESPECIALIZADA A SAUDE"],
            "acao": ["ESTRUTURACAO DE UNIDADES DE SAUDE"],
            "subTitulo": ["NACIONAL"],
            "localizadorGasto": ["BR"],
            "fase": ["Empenho"],
            "especie": ["Original"],
            "favorecido": ["EMPRESA MEDICA LTDA"],
            "codigoFavorecido": ["12345678000190"],
            "nomeFavorecido": ["EMPRESA MEDICA LTDA"],
            "ufFavorecido": ["DF"],
            "valor": ["1.234.567,89"],
            "codigoUg": ["250001"],
            "ug": ["FUNDO NACIONAL DE SAUDE"],
            "codigoUo": ["25000"],
            "uo": ["MINISTERIO DA SAUDE"],
            "codigoOrgao": ["36000"],
            "orgao": ["MINISTERIO DA SAUDE"],
            "codigoOrgaoSuperior": ["36000"],
            "orgaoSuperior": ["MINISTERIO DA SAUDE"],
            "categoria": ["DESPESAS DE CAPITAL"],
            "grupo": ["INVESTIMENTOS"],
            "elemento": ["EQUIPAMENTOS E MATERIAL PERMANENTE"],
            "modalidade": ["TRANSFERENCIAS A MUNICIPIOS"],
            "numeroProcesso": ["25000.001234/2024-11"],
            "planoOrcamentario": ["0000 - PLANO ORCAMENTARIO PADRAO"],
            "autor": ["EMENDA DE COMISSAO"],
            "favorecidoIntermediario": [False],
            "favorecidoListaFaturas": [False],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_DESPESAS_EMPENHOS.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["documento"][0] == "2024NE000123"
        assert result["valor"][0] == 1234567.89
        assert result["fase"][0] == "Empenho"
        assert result["favorecidoIntermediario"][0] is False


class TestPortalDespesasPagamentosTransformer:
    """Testes para o PortalDespesasPagamentosTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalDespesasPagamentosTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalDespesasPagamentosTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/despesas/documentos?dataEmissao=20/02/2024&fase=3&pagina=1"],
            "data": ["20/02/2024"],
            "documento": ["2024OB800456"],
            "documentoResumido": ["2024OB800456"],
            "observacao": ["PAGAMENTO DE ORDEM BANCARIA"],
            "funcao": ["Educação"],
            "subfuncao": ["Ensino Superior"],
            "programa": ["EDUCACAO SUPERIOR - GRADUACAO, POS-GRADUACAO"],
            "acao": ["FUNCIONAMENTO DE INSTITUICOES FEDERAIS"],
            "subTitulo": ["NACIONAL"],
            "localizadorGasto": ["BR"],
            "fase": ["Pagamento"],
            "especie": ["Original"],
            "favorecido": ["UNIVERSIDADE FEDERAL DE EXEMPLO"],
            "codigoFavorecido": ["00123456000100"],
            "nomeFavorecido": ["UNIVERSIDADE FEDERAL DE EXEMPLO"],
            "ufFavorecido": ["MG"],
            "valor": ["98.765,43"],
            "codigoUg": ["153001"],
            "ug": ["UNIVERSIDADE FEDERAL DE EXEMPLO"],
            "codigoUo": ["26101"],
            "uo": ["MINISTERIO DA EDUCACAO"],
            "codigoOrgao": ["26000"],
            "orgao": ["MINISTERIO DA EDUCACAO"],
            "codigoOrgaoSuperior": ["26000"],
            "orgaoSuperior": ["MINISTERIO DA EDUCACAO"],
            "categoria": ["DESPESAS CORRENTES"],
            "grupo": ["OUTRAS DESPESAS CORRENTES"],
            "elemento": ["SERVICOS DE TERCEIROS - PESSOA JURIDICA"],
            "modalidade": ["APLICACOES DIRETAS"],
            "numeroProcesso": ["23000.009876/2024-22"],
            "planoOrcamentario": ["0000 - PLANO ORCAMENTARIO PADRAO"],
            "autor": ["RECURSOS ORDINARIOS"],
            "favorecidoIntermediario": [False],
            "favorecidoListaFaturas": [True],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_DESPESAS_PAGAMENTOS.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["documento"][0] == "2024OB800456"
        assert result["valor"][0] == 98765.43
        assert result["fase"][0] == "Pagamento"
        assert result["favorecidoListaFaturas"][0] is True
