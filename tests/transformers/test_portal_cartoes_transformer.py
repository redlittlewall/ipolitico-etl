"""Testes do PortalCartoesTransformer — rota dupla (bulk mensal + API v3).

O domínio CG_CARTOES tem duas fontes (ticket 04): dump bulk mensal de
``/download-de-dados/{cpgf,cpcc,cpdc}/{YYYYMM}`` (FULL_LOAD) e API v3
``/api-de-dados/cartoes`` por bloco mensal (INCREMENTAL). O transformer detecta
a rota pelo shape e normaliza ambas para o mesmo contrato
``SILVER_SCHEMAS[cg_cartoes]``.

Amostras reais capturadas na validação (ticket 04): CSV bulk cpgf 202401 e DTO
da API v3 (mês 06/2025). Correções de fonte documentadas no transformer:
``favorecido`` ≡ ``estabelecimento`` (a API deriva ``favorecido_*`` do
estabelecimento para a UK alinhar entre rotas) e cpcc do bulk não tem portador.
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.cartoes_transformer import (
    PortalCartoesTransformer,
)

# UK do spec — identidade composta + `id` da API (correção da validação real,
# ticket 04): a composta colide em transações DISTINTAS da API com documentos
# mascarados; `id` é o único discriminador da rota API.
_UK = (
    "tipoCartao_codigo",
    "mesExtrato",
    "dataTransacao",
    "valorTransacao",
    "portador_cpfFormatado",
    "favorecido_cpfCnpj",
    "unidadeGestora_codigo",
    "id",
)
# A parte composta (sem `id`) — alinha entre rotas, mas NÃO é única na API.
_COMPOSITE_UK = _UK[:-1]

_BULK_URL_CPGF = "https://portaldatransparencia.gov.br/download-de-dados/cpgf/202401"
_BULK_URL_CPDC = "https://portaldatransparencia.gov.br/download-de-dados/cpdc/202506"

# Linha REAL do CSV cpgf 202401 (dados capturados).
_BULK_ROW = {
    "_source_url": _BULK_URL_CPGF,
    "CÓDIGO ÓRGÃO SUPERIOR": "63000",
    "NOME ÓRGÃO SUPERIOR": "Advocacia-Geral da União",
    "CÓDIGO ÓRGÃO": "63000",
    "NOME ÓRGÃO": "Advocacia-Geral da União - Unidades com vínculo direto",
    "CÓDIGO UNIDADE GESTORA": "110161",
    "NOME UNIDADE GESTORA": "SUPERINTENDENCIA REG. DE ADMIN. DA 1ª REGIAO",
    "ANO EXTRATO": "2024",
    "MÊS EXTRATO": "01",
    "CPF PORTADOR": "***.195.852-**",
    "NOME PORTADOR": "JOSE UELISSON ALVES LEITE",
    "CNPJ OU CPF FAVORECIDO": "79379491017744",
    "NOME FAVORECIDO": "HAVAN S.A",
    "TRANSAÇÃO": "COMPRA A/V - R$ - APRES",
    "DATA TRANSAÇÃO": "07/12/2023",
    "VALOR TRANSAÇÃO": "607,41",
}

# Linha REAL do DTO da API v3 (mês 06/2025).
_API_ROW = {
    "_source_url": "https://api.portaldatransparencia.gov.br/api-de-dados/cartoes?pagina=1",
    "id": 476228285,
    "mesExtrato": "06/2025",
    "dataTransacao": "14/05/2025",
    "valorTransacao": "1.484,00",
    "tipoCartao": {
        "id": 1,
        "codigo": "1",
        "descricao": "Cartão de Pagamento do Governo Federal - CPGF",
    },
    "estabelecimento": {
        "id": 358918433,
        "cpfFormatado": "",
        "cnpjFormatado": "38.056.949/0001-86",
        "numeroInscricaoSocial": "",
        "nome": "IRACU NAZARENO SARMENTO DA COSTA LTDA",
        "razaoSocialReceita": "IRACU NAZARENO SARMENTO DA COSTA LTDA",
        "nomeFantasiaReceita": "AMAPA RACOES",
        "tipo": "Entidades Empresariais Privadas",
    },
    "unidadeGestora": {
        "codigo": "135008",
        "nome": "EMBRAPA/CPAF-AP",
        "descricaoPoder": "EXECUTIVO",
        "orgaoVinculado": {
            "codigoSIAFI": "22202",
            "cnpj": "00348003000110",
            "sigla": "EMBRAPA",
            "nome": "Empresa Brasileira de Pesquisa Agropecuária",
        },
        "orgaoMaximo": {
            "codigo": "22000",
            "sigla": "MAPA",
            "nome": "Ministério da Agricultura e Pecuária",
        },
    },
    "portador": {
        "cpfFormatado": "***.382.302-**",
        "nis": "",
        "nome": "BENEDITO PONTES SILVA",
    },
}


def _uk_key(df: pl.DataFrame) -> tuple:
    """Tupla UK da primeira linha do DataFrame transformado."""
    row = df.select(list(_UK)).row(0)
    return tuple(row)


def _composite_key(df: pl.DataFrame) -> tuple:
    """Tupla da parte composta da UK (sem `id`) da primeira linha."""
    row = df.select(list(_COMPOSITE_UK)).row(0)
    return tuple(row)


class TestPortalCartoesTransformerRotaBulk:
    """Rota bulk: CSV flat com colunas uppercase do dump mensal."""

    def test_happy_path(self):
        """Linha real do cpgf: mapeamento, mesExtrato combinado, moeda, tipoCartao."""
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([_BULK_ROW], infer_schema_length=None))

        assert out.height == 1
        # ANO EXTRATO + MÊS EXTRATO → "MM/AAAA"; DATA TRANSAÇÃO é de dez/2023
        # (extrato jan/2024 ≠ transação — a combinação usa o extrato).
        assert out["mesExtrato"][0] == "01/2024"
        assert out["dataTransacao"][0] == "07/12/2023"
        assert out["valorTransacao"][0] == 607.41
        assert out["tipoCartao_id"][0] == 1
        assert out.schema["tipoCartao_id"] == pl.Int64
        assert out["tipoCartao_codigo"][0] == "1"
        assert out["tipoCartao_descricao"][0] == "Cartão de Pagamento do Governo Federal - CPGF"
        assert out["unidadeGestora_codigo"][0] == "110161"
        assert out["unidadeGestora_orgaoMaximo_codigo"][0] == "63000"
        assert out["unidadeGestora_orgaoVinculado_codigoSIAFI"][0] == "63000"
        assert out["portador_cpfFormatado"][0] == "***.195.852-**"
        assert out["portador_nome"][0] == "JOSE UELISSON ALVES LEITE"
        assert out["favorecido_cpfCnpj"][0] == "79379491017744"
        assert out["favorecido_nome"][0] == "HAVAN S.A"
        assert out["transacao_descricao"][0] == "COMPRA A/V - R$ - APRES"
        # id/estabelecimento_* são da API — nulos no bulk
        assert out["id"][0] is None
        assert out["estabelecimento_nome"][0] is None
        assert out["_source_url"][0] == _BULK_URL_CPGF

    def test_cpcc_sem_portador_vira_nulo(self):
        """cpcc NÃO tem colunas de portador no CSV → portador_* nulo, tipo 2."""
        row = dict(_BULK_ROW)
        row.pop("CPF PORTADOR")
        row.pop("NOME PORTADOR")
        row["_source_url"] = _BULK_URL_CPGF.replace("/cpgf/", "/cpcc/")
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["portador_cpfFormatado"][0] is None
        assert out["portador_nome"][0] is None
        assert out["tipoCartao_codigo"][0] == "2"
        assert (
            out["tipoCartao_descricao"][0] == "Cartão de Pagamento de Compras Centralizadas - CPCC"
        )

    def test_cpdc_colunas_de_convenio_descartadas(self):
        """Extras de cpdc (convênio) e de cpcc (TIPO AQUISIÇÃO) não entram."""
        row = dict(_BULK_ROW)
        row.update(
            {
                "_source_url": _BULK_URL_CPDC,
                "EXECUTOR DESPESA": "BRASILEIA / AC",
                "NÚMERO CONVÊNIO": "671987",
                "CÓDIGO CONVENENTE": "04508933000145",
                "NOME CONVENENTE": "MUNICIPIO DE BRASILEIA",
                "REPASSE": "Não",
                "TIPO AQUISIÇÃO": "Aquisição de Passagem Aérea",
            }
        )
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        contract = SILVER_SCHEMAS[DomainType.CG_CARTOES.value]
        assert list(out.columns) == list(contract)
        assert "NÚMERO CONVÊNIO" not in out.columns
        assert out["tipoCartao_codigo"][0] == "3"
        assert out["tipoCartao_descricao"][0] == "Cartão de Pagamento da Defesa Civil - CPDC"

    def test_valor_com_milhar(self):
        """VALOR TRANSAÇÃO com separador de milhar → Float64."""
        row = {**_BULK_ROW, "VALOR TRANSAÇÃO": "70.922,36"}
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))
        assert out["valorTransacao"][0] == 70922.36

    def test_favorecido_canonicalizado_e_mascarado_vira_nulo(self):
        """Bulk também canonicaliza CNPJ/CPF e anula documento mascarado.

        Espec (ticket 04, "Normalização no transformer, ambas as rotas"): a UK
        composta alinha entre rotas só se as DUAS canonicalizam — a API deriva
        ``favorecido_*`` do ``estabelecimento`` já em dígitos canônicos; um dump
        bulk futuro pode publicar formatado ("02.012.862/0001-60"). Documento
        mascarado ("*") vira nulo — a mesma regra da rota API.
        """
        tr = PortalCartoesTransformer()

        row = {**_BULK_ROW, "CNPJ OU CPF FAVORECIDO": "02.012.862/0001-60"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))
        assert out["favorecido_cpfCnpj"][0] == "02012862000160"

        row_mask = {**_BULK_ROW, "CNPJ OU CPF FAVORECIDO": "***.542.243-**"}
        out_mask = tr.transform(pl.DataFrame([row_mask], infer_schema_length=None))
        assert out_mask["favorecido_cpfCnpj"][0] is None

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()


class TestPortalCartoesTransformerRotaApi:
    """Rota API: structs aninhadas do DTO da v3."""

    def test_happy_path(self):
        """Linha real do DTO: structs achatadas, moeda, favorecido derivado."""
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([_API_ROW], infer_schema_length=None))

        assert out.height == 1
        assert out["id"][0] == 476228285
        assert out.schema["id"] == pl.Int64
        assert out["mesExtrato"][0] == "06/2025"
        assert out["dataTransacao"][0] == "14/05/2025"
        assert out["valorTransacao"][0] == 1484.0
        assert out["tipoCartao_id"][0] == 1
        assert out["tipoCartao_codigo"][0] == "1"
        assert out["estabelecimento_id"][0] == 358918433
        # cnpjFormatado da API preservado como veio (coluna "formatada")
        assert out["estabelecimento_cnpjFormatado"][0] == "38.056.949/0001-86"
        assert out["estabelecimento_nome"][0] == "IRACU NAZARENO SARMENTO DA COSTA LTDA"
        # unidadeGestora + structs aninhadas (orgaoVinculado/orgaoMaximo)
        assert out["unidadeGestora_codigo"][0] == "135008"
        assert out["unidadeGestora_descricaoPoder"][0] == "EXECUTIVO"
        assert out["unidadeGestora_orgaoVinculado_codigoSIAFI"][0] == "22202"
        assert out["unidadeGestora_orgaoVinculado_cnpj"][0] == "00348003000110"
        assert out["unidadeGestora_orgaoMaximo_codigo"][0] == "22000"
        assert out["unidadeGestora_orgaoMaximo_sigla"][0] == "MAPA"
        assert out["portador_cpfFormatado"][0] == "***.382.302-**"
        assert out["portador_nome"][0] == "BENEDITO PONTES SILVA"
        # favorecido derivado do estabelecimento (mesma entidade) — correção 1
        assert out["favorecido_cpfCnpj"][0] == "38056949000186"
        assert out["favorecido_nome"][0] == "IRACU NAZARENO SARMENTO DA COSTA LTDA"
        # transacao_descricao é só do bulk → nulo na API
        assert out["transacao_descricao"][0] is None

    def test_strings_vazias_reais_viram_nulo(self):
        """cpfFormatado/nis vazios no DTO real → nulo."""
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([_API_ROW], infer_schema_length=None))

        assert out["estabelecimento_cpfFormatado"][0] is None
        assert out["estabelecimento_numeroInscricaoSocial"][0] is None
        assert out["portador_nis"][0] is None

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS (33 colunas, _source_url 1ª)."""
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([_API_ROW], infer_schema_length=None))

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_CARTOES.value]
        assert list(out.columns) == list(contract)
        assert out.schema["valorTransacao"] == pl.Float64
        assert out.schema["mesExtrato"] == pl.String
        assert out.schema["dataTransacao"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: campo futuro da API) são descartadas."""
        tr = PortalCartoesTransformer()
        row = {**_API_ROW, "campo_futuro": "deve sumir"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        contract = SILVER_SCHEMAS[DomainType.CG_CARTOES.value]
        assert list(out.columns) == list(contract)

    def test_documento_mascarado_vira_favorecido_nulo(self):
        """CPF mascarado (CPDC/beneficiário) → favorecido nulo, NÃO "542243"."""
        # DTO real de beneficiário da Defesa Civil: SEM cnpjFormatado (nulo) e
        # CPF mascarado ("***.542.243-**"). Sem a correção, o coalesce pegava o
        # CPF mascarado e o canonical virava "542243" (lixo de 6 dígitos que não
        # casa com o CNPJ completo do bulk).
        row = {
            **_API_ROW,
            "estabelecimento": {
                **_API_ROW["estabelecimento"],
                "cpfFormatado": "***.542.243-**",
                "cnpjFormatado": None,
            },
        }
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["favorecido_cpfCnpj"][0] is None
        assert out["favorecido_nome"][0] == "IRACU NAZARENO SARMENTO DA COSTA LTDA"

    def test_estabelecimento_sem_documento_vira_favorecido_nulo(self):
        """Estab "SEM INFORMACAO" (sem cnpj/cpf) → favorecido cpfCnpj nulo."""
        row = {
            **_API_ROW,
            "estabelecimento": {
                **_API_ROW["estabelecimento"],
                "cpfFormatado": "",
                "cnpjFormatado": "",
                "nome": "SEM INFORMACAO",
            },
        }
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["favorecido_cpfCnpj"][0] is None
        assert out["favorecido_nome"][0] == "SEM INFORMACAO"

    def test_transacoes_distintas_mesmo_composite_nao_merge(self):
        """Duas transações API com composta igual e `id` distinto → AMBAS ficam.

        Caso real da validação (645 linhas/mês, 197 grupos "SEM INFORMACAO"/
        "NAO SE APLICA"): o `id` na UK impede o merge de transações distintas.
        """
        row2 = {**_API_ROW, "id": 476228286}
        tr = PortalCartoesTransformer()
        out = tr.transform(pl.DataFrame([_API_ROW, row2], infer_schema_length=None))

        assert out.height == 2
        keys = [tuple(r) for r in out.select(list(_UK)).rows()]
        # Chaves distintas apenas pelo `id` (composta igual).
        assert keys[0] != keys[1]
        assert keys[0][:-1] == keys[1][:-1]


class TestPortalCartoesTransformerUkEntreRotas:
    """UK = identidade composta + `id` (correção da validação real, ticket 04)."""

    def test_composite_alinha_mas_id_distinguir_rotas_nao_deduplica_overlap(self):
        """Mesma transação nas rotas: composta igual, mas `id` (nulo vs real) difere.

        A validação real mostrou que a composta sozinha colide em transações
        DISTINTAS da API (documentos mascarados em ~5% das linhas: "SEM
        INFORMACAO", CPDC) — o `id` da API é o único discriminador. UK inclui
        `id`; consequência documentada: o overlap bulk×API NÃO deduplica no Gold.
        """
        # Transação análoga à real da API, expressa no shape do CSV bulk.
        bulk_row = {
            "_source_url": _BULK_URL_CPGF.replace("/202401", "/202506"),
            "CÓDIGO ÓRGÃO SUPERIOR": "22000",
            "NOME ÓRGÃO SUPERIOR": "Ministério da Agricultura e Pecuária",
            "CÓDIGO ÓRGÃO": "22202",
            "NOME ÓRGÃO": "Empresa Brasileira de Pesquisa Agropecuária",
            "CÓDIGO UNIDADE GESTORA": "135008",
            "NOME UNIDADE GESTORA": "EMBRAPA/CPAF-AP",
            "ANO EXTRATO": "2025",
            "MÊS EXTRATO": "06",
            "CPF PORTADOR": "***.382.302-**",
            "NOME PORTADOR": "BENEDITO PONTES SILVA",
            "CNPJ OU CPF FAVORECIDO": "38056949000186",
            "NOME FAVORECIDO": "IRACU NAZARENO SARMENTO DA COSTA LTDA",
            "TRANSAÇÃO": "COMPRA A/V - R$ - APRES",
            "DATA TRANSAÇÃO": "14/05/2025",
            "VALOR TRANSAÇÃO": "1.484,00",
        }
        tr = PortalCartoesTransformer()
        out_bulk = tr.transform(pl.DataFrame([bulk_row], infer_schema_length=None))
        out_api = tr.transform(pl.DataFrame([_API_ROW], infer_schema_length=None))

        # A parte composta alinha entre rotas (mesma transação real).
        assert _composite_key(out_bulk) == _composite_key(out_api)
        assert _composite_key(out_bulk) == (
            "1",
            "06/2025",
            "14/05/2025",
            1484.0,
            "***.382.302-**",
            "38056949000186",
            "135008",
        )
        # Mas `id` difere (None no bulk vs 476228285 na API) → chaves distintas
        # → o Gold NÃO deduplica o overlap (limitação documentada do desenho).
        assert _uk_key(out_bulk) == (
            "1",
            "06/2025",
            "14/05/2025",
            1484.0,
            "***.382.302-**",
            "38056949000186",
            "135008",
            None,
        )
        assert _uk_key(out_api)[-1] == 476228285
