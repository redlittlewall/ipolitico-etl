"""Testes para os transformadores da Fatia 1 da CGU (Sanções e Integridade).

Testes puros em Polars sem I/O sobre DataFrames sintéticos:
- PortalCeisTransformer
- PortalCnepTransformer
- PortalCepimTransformer
- PortalCeafTransformer
- PortalAcordosLenienciaTransformer
"""

import polars as pl
import pytest

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.ceis_transformer import PortalCeisTransformer
from ipolitico.transformers.portal_transparencia.cnep_transformer import PortalCnepTransformer
from ipolitico.transformers.portal_transparencia.cepim_transformer import PortalCepimTransformer
from ipolitico.transformers.portal_transparencia.ceaf_transformer import PortalCeafTransformer
from ipolitico.transformers.portal_transparencia.acordos_leniencia_transformer import (
    PortalAcordosLenienciaTransformer,
)


class TestPortalCeisTransformer:
    """Testes para o PortalCeisTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalCeisTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalCeisTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/ceis?pagina=1"],
            "id": [12345],
            "dataReferencia": ["23/08/2026"],
            "dataInicioSancao": ["01/01/2024"],
            "dataFimSancao": ["31/12/2025"],
            "dataPublicacaoSancao": ["02/01/2024"],
            "dataTransitadoJulgado": ["15/12/2023"],
            "dataOrigemInformacao": ["02/01/2024"],
            "tipoSancao": [{"descricaoResumida": "Suspensão", "descricaoPortal": "Suspensão temporária"}],
            "fonteSancao": [{"nomeExibicao": "CGU", "telefoneContato": "1234-5678", "enderecoContato": "Brasília/DF"}],
            "orgaoSancionador": [{"nome": "Ministério da Educação", "siglaUf": "DF", "poder": "Executivo", "esfera": "Federal"}],
            "sancionado": [{"nome": "EMPRESA X LTDA", "codigoFormatado": "12.345.678/0001-90"}],
            "pessoa": [{
                "id": 999,
                "cpfFormatado": None,
                "cnpjFormatado": "12.345.678/0001-90",
                "numeroInscricaoSocial": None,
                "nome": "EMPRESA X LTDA",
                "razaoSocialReceita": "EMPRESA X LTDA",
                "nomeFantasiaReceita": "X TECH",
                "tipo": "JURIDICA"
            }],
            "textoPublicacao": ["Publicado no DOU"],
            "linkPublicacao": ["http://dou.gov.br"],
            "detalhamentoPublicacao": ["Artigo 87"],
            "numeroProcesso": ["001/2023"],
            "abrangenciaDefinidaDecisaoJudicial": ["Nacional"],
            "informacoesAdicionaisDoOrgaoSancionador": ["Sem observações"],
            "fundamentacao": [[{"codigo": "LEI_8666", "descricao": "Lei 8.666/93 Art. 87"}]],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CEIS.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["id"][0] == 12345
        assert result["tipoSancao_descricaoResumida"][0] == "Suspensão"
        assert result["orgaoSancionador_nome"][0] == "Ministério da Educação"
        assert result["sancionado_nome"][0] == "EMPRESA X LTDA"
        assert result["pessoa_cnpjFormatado"][0] == "12.345.678/0001-90"
        assert "LEI_8666" in result["fundamentacao"][0]


class TestPortalCnepTransformer:
    """Testes para o PortalCnepTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalCnepTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_with_multa(self):
        transformer = PortalCnepTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/cnep?pagina=1"],
            "id": [54321],
            "dataReferencia": ["23/08/2026"],
            "dataInicioSancao": ["01/06/2024"],
            "dataFimSancao": ["01/06/2026"],
            "dataPublicacaoSancao": ["02/06/2024"],
            "dataTransitadoJulgado": [None],
            "dataOrigemInformacao": ["02/06/2024"],
            "tipoSancao": [{"descricaoResumida": "Multa e Publicação", "descricaoPortal": "Multa Lei 12.846"}],
            "fonteSancao": [{"nomeExibicao": "CGU", "telefoneContato": None, "enderecoContato": None}],
            "orgaoSancionador": [{"nome": "CGU", "siglaUf": "DF", "poder": "Executivo", "esfera": "Federal"}],
            "sancionado": [{"nome": "EMPRESA Y S.A.", "codigoFormatado": "98.765.432/0001-10"}],
            "valorMulta": ["1.500.250,75"],
            "pessoa": [{
                "id": 888,
                "cpfFormatado": None,
                "cnpjFormatado": "98.765.432/0001-10",
                "numeroInscricaoSocial": None,
                "nome": "EMPRESA Y S.A.",
                "razaoSocialReceita": "EMPRESA Y S.A.",
                "nomeFantasiaReceita": "Y CORP",
                "tipo": "JURIDICA"
            }],
            "textoPublicacao": ["DOU Edição 100"],
            "linkPublicacao": None,
            "detalhamentoPublicacao": None,
            "numeroProcesso": ["002/2024"],
            "abrangenciaDefinidaDecisaoJudicial": None,
            "informacoesAdicionaisDoOrgaoSancionador": None,
            "fundamentacao": [[{"codigo": "LEI_12846", "descricao": "Lei 12.846/2013"}]],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CNEP.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["id"][0] == 54321
        assert result["valorMulta"][0] == 1500250.75
        assert result["sancionado_nome"][0] == "EMPRESA Y S.A."


class TestPortalCepimTransformer:
    """Testes para o PortalCepimTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalCepimTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalCepimTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/cepim?pagina=1"],
            "id": [112233],
            "dataReferencia": ["23/08/2026"],
            "motivo": ["Inadimplência na prestação de contas"],
            "orgaoSuperior": [{
                "nome": "Ministério da Saúde",
                "codigoSIAFI": "36000",
                "cnpj": "00394700000100",
                "sigla": "MS",
                "descricaoPoder": "Executivo"
            }],
            "pessoaJuridica": [{
                "id": 777,
                "cpfFormatado": None,
                "cnpjFormatado": "11.222.333/0001-44",
                "numeroInscricaoSocial": None,
                "nome": "INSTITUTO SOCIAL ABC",
                "razaoSocialReceita": "INSTITUTO SOCIAL ABC",
                "nomeFantasiaReceita": "ABC SOCIAL",
                "tipo": "JURIDICA"
            }],
            "convenio": [{
                "codigo": "CV-2022-001",
                "objeto": "Apoio a projetos comunitários",
                "numero": "887766"
            }],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CEPIM.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["id"][0] == 112233
        assert result["orgaoSuperior_sigla"][0] == "MS"
        assert result["pessoaJuridica_cnpjFormatado"][0] == "11.222.333/0001-44"
        assert result["convenio_numero"][0] == "887766"


class TestPortalCeafTransformer:
    """Testes para o PortalCeafTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalCeafTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_success(self):
        transformer = PortalCeafTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/ceaf?pagina=1"],
            "id": [445566],
            "dataPublicacao": ["10/05/2023"],
            "dataReferencia": ["23/08/2026"],
            "punicao": [{
                "cpfPunidoFormatado": "***.123.456-**",
                "nomePunido": "FULANO DE TAL",
                "portaria": "Portaria 123",
                "processo": "000123/2022",
                "paginaDOU": "12",
                "secaoDOU": "2"
            }],
            "tipoPunicao": [{"descricao": "Demissão"}],
            "pessoa": [{
                "id": 555,
                "cpfFormatado": "***.123.456-**",
                "cnpjFormatado": None,
                "numeroInscricaoSocial": None,
                "nome": "FULANO DE TAL",
                "razaoSocialReceita": None,
                "nomeFantasiaReceita": None,
                "tipo": "FISICA"
            }],
            "orgaoLotacao": [{
                "siglaDaPasta": "MF",
                "sigla": "RFB",
                "nome": "Receita Federal do Brasil",
                "nomeSemAcento": "Receita Federal do Brasil"
            }],
            "ufLotacaoPessoa": [{
                "codigoIBGE": "35",
                "codigoCNPJEstado": "46379400000150",
                "populacao": 44000000
            }],
            "cargoEfetivo": ["Auditor Fiscal"],
            "codigoCargoComissao": None,
            "cargoComissao": None,
            "fundamentacao": [[{"codigo": "LEI_8112_ART_132", "descricao": "Lei 8.112/90, art. 132"}]],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_CEAF.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        assert result["id"][0] == 445566
        assert result["punicao_nomePunido"][0] == "FULANO DE TAL"
        assert result["tipoPunicao_descricao"][0] == "Demissão"
        assert result["orgaoLotacao_sigla"][0] == "RFB"
        assert result["ufLotacaoPessoa_populacao"][0] == 44000000
        assert "LEI_8112" in result["fundamentacao"][0]


class TestPortalAcordosLenienciaTransformer:
    """Testes para o PortalAcordosLenienciaTransformer."""

    def test_empty_dataframe(self):
        transformer = PortalAcordosLenienciaTransformer()
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_with_sancoes_array(self):
        transformer = PortalAcordosLenienciaTransformer()
        raw_data = {
            "_source_url": ["https://api.portaldatransparencia.gov.br/api-de-dados/acordos-leniencia?pagina=1"],
            "id": [778899],
            "dataInicioAcordo": ["01/03/2021"],
            "dataFimAcordo": ["01/03/2031"],
            "orgaoResponsavel": ["CGU / AGU"],
            "situacaoAcordo": ["Cumprindo"],
            "quantidade": [2],
            "sancoes": [[
                {
                    "nomeInformadoOrgaoResponsavel": "CONSTRUTORA ALFA S/A",
                    "razaoSocial": "CONSTRUTORA ALFA S/A",
                    "nomeFantasia": "ALFA ENGENHARIA",
                    "cnpj": "12345678000199",
                    "cnpjFormatado": "12.345.678/0001-99"
                },
                {
                    "nomeInformadoOrgaoResponsavel": "ALFA PARTICIPACOES S/A",
                    "razaoSocial": "ALFA PARTICIPACOES S/A",
                    "nomeFantasia": "ALFA PART",
                    "cnpj": "98765432000188",
                    "cnpjFormatado": "98.765.432/0001-88"
                }
            ]],
        }
        df_raw = pl.DataFrame(raw_data)
        result = transformer.transform(df_raw)

        contract = SILVER_SCHEMAS[DomainType.CG_ACORDOS_LENIENCIA.value]
        assert list(result.columns) == list(contract.keys())
        for col, dtype in contract.items():
            assert result.schema[col] == dtype

        # 1 acordo com 2 empresas sancionadas vira 2 linhas
        assert len(result) == 2
        assert result["id"][0] == 778899
        assert result["id"][1] == 778899
        assert result["cnpjEmpresa"][0] == "12345678000199"
        assert result["cnpjEmpresa"][1] == "98765432000188"
        assert result["razaoSocialEmpresa"][0] == "CONSTRUTORA ALFA S/A"
        assert result["razaoSocialEmpresa"][1] == "ALFA PARTICIPACOES S/A"
