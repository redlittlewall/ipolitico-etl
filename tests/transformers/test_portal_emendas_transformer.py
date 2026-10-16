"""Testes do PortalEmendasTransformer — contrato Silver do DTO real (API v3).

O DTO da API v3 (``/api-de-dados/emendas``) é flat: ``ano`` inteiro, ``valor*``
em string de moeda brasileira (``"3.500.000,00"``). O transformer converte os
6 campos monetários para ``Float64``, preenche colunas ausentes com nulo e
aplica a tipagem estrita de ``SILVER_SCHEMAS[cg_emendas]`` (amostra real
capturada na validação do ticket 04).
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.emendas_transformer import (
    PortalEmendasTransformer,
)

API_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/emendas?ano=2016&pagina=1"

_ROW = {
    "_source_url": API_URL,
    "codigoEmenda": "REL. GERAL",
    "ano": 2016,
    "tipoEmenda": "Emenda de Comissão",
    "autor": "RELATOR GERAL",
    "nomeAutor": "RELATOR GERAL",
    "numeroEmenda": "S/I",
    "localidadeDoGasto": "Nacional",
    "funcao": "Organização agrária",
    "subfuncao": "Ordenamento territorial",
    "valorEmpenhado": "0,00",
    "valorLiquidado": "0,00",
    "valorPago": "0,00",
    "valorRestoInscrito": "0,00",
    "valorRestoCancelado": "3.500.000,00",
    "valorRestoPago": "0,00",
}


class TestPortalEmendasTransformer:
    """Contrato real do DTO capturado (API v3, emenda com resto cancelado)."""

    def test_happy_path(self):
        """Linha real: moeda BR (com milhar) → Float64, ano Int64."""
        tr = PortalEmendasTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.height == 1
        assert out["codigoEmenda"][0] == "REL. GERAL"
        assert out["ano"][0] == 2016
        assert out.schema["ano"] == pl.Int64
        assert out["tipoEmenda"][0] == "Emenda de Comissão"
        assert out["valorEmpenhado"][0] == 0.0
        assert out["valorRestoCancelado"][0] == 3500000.0
        assert out.schema["valorRestoCancelado"] == pl.Float64
        assert out["_source_url"][0] == API_URL

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = PortalEmendasTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_EMENDAS.value]
        assert list(out.columns) == list(contract)
        assert out.schema["codigoEmenda"] == pl.String
        assert out.schema["ano"] == pl.Int64
        assert out.schema["valorPago"] == pl.Float64

    def test_coluna_ausente_vira_nulo(self):
        """Campo monetário ausente na resposta (ex: sem valorLiquidado) → nulo."""
        tr = PortalEmendasTransformer()
        row = {k: v for k, v in _ROW.items() if k != "valorLiquidado"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["valorLiquidado"][0] is None
        assert out.schema["valorLiquidado"] == pl.Float64

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalEmendasTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: campo futuro da API) são descartadas."""
        tr = PortalEmendasTransformer()
        row = {**_ROW, "campo_futuro": "deve sumir"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        contract = SILVER_SCHEMAS[DomainType.CG_EMENDAS.value]
        assert list(out.columns) == list(contract)
