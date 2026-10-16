"""Testes do PortalRemuneracoesBulkTransformer — contrato Silver provisório.

Prior art: ``tests/transformers/test_senado_remuneracoes_transformer.py`` — o
transformer converte moeda BR (string → Float64), preenche colunas ausentes do
contrato com nulo e aplica a tipagem estrita de ``SILVER_SCHEMAS``.

A folha do Executivo mudou de layout em 2020: pré-2020 os dumps não publicavam o
detalhe completo de rubricas (gratificação natalina, férias, pensão militar,
verbas indenizatórias detalhadas etc.). O fixture pré-2020 omite esses campos —
o transformer os preenche com nulo (compatibilidade retroativa do contrato).
Contrato PROVISIONAL: o dump real está bloqueado pelo WAF/CAPTCHA da CGU
(validado no ticket 03); quando o WAF liberar, o ticket reabre para travar a
renomeação real das colunas do CSV.
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.remuneracoes_bulk_transformer import (
    PortalRemuneracoesBulkTransformer,
)

API_URL = "https://portaldatransparencia.gov.br/download-de-dados/servidores/202401"

# Campos pós-2020: ausentes no fixture pré-2020 → nulo.
_POST_2020 = (
    "gratificacao_natalina",
    "ferias",
    "outras_remuneracoes_eventuais",
    "pensao_militar",
    "fundo_saude",
    "taxa_ocupacao_imovel_funcional",
    "verbas_indenizatorias_civil",
    "verbas_indenizatorias_militar",
    "verbas_indenizatorias_referentes_pdv",
)

# Base comum (identidade + buckets presentes nas duas eras).
_BASE_ROW = {
    "_source_url": API_URL,
    "id_servidor": "12345",
    "nome": "MARIA DA SILVA",
    "cpf": "000.000.000-00",
    "matricula": "9876543",
    "cod_orgao_lotacao": "60000",
    "nome_orgao_lotacao": "PRESIDENCIA DA REPUBLICA",
    "cod_orgao_exercicio": "81300",
    "nome_orgao_exercicio": "MINISTERIO DA IGUALDADE RACIAL",
    "mes_ano": "2024-01",
    "remuneracao_basica": "12.000,00",
    "imposto_retido_na_fonte": "-2.500,00",
    "previdencia_oficial": "-1.100,00",
    "outras_deducoes_obrigatorias": "-300,00",
    "verbas_indenizatorias": "500,00",
    "remuneracao_apos_deducoes": "8.600,00",
}


def _post_2020_row() -> dict:
    row = dict(_BASE_ROW)
    row.update(
        {
            "gratificacao_natalina": "0,00",
            "ferias": "0,00",
            "outras_remuneracoes_eventuais": "200,00",
            "pensao_militar": "0,00",
            "fundo_saude": "-50,00",
            "taxa_ocupacao_imovel_funcional": "0,00",
            "verbas_indenizatorias_civil": "400,00",
            "verbas_indenizatorias_militar": "0,00",
            "verbas_indenizatorias_referentes_pdv": "100,00",
        }
    )
    return row


class TestPortalRemuneracoesBulkTransformer:
    """Contrato Silver provisório: compatibilidade retroativa pré-2020."""

    def test_happy_path_pos_2020(self):
        """Fixture pós-2020: buckets monetários BR viram Float64."""
        tr = PortalRemuneracoesBulkTransformer()
        raw = pl.DataFrame([_post_2020_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.height == 1
        assert out["nome"][0] == "MARIA DA SILVA"
        assert out["remuneracao_basica"][0] == 12000.0
        assert out["imposto_retido_na_fonte"][0] == -2500.0
        assert out["remuneracao_apos_deducoes"][0] == 8600.0
        assert out["verbas_indenizatorias_civil"][0] == 400.0

    def test_fixture_pre_2020_campos_split_nulos(self):
        """Fixture pré-2020: rubricas pós-2020 ausentes → nulo, sem crash."""
        tr = PortalRemuneracoesBulkTransformer()
        raw = pl.DataFrame([dict(_BASE_ROW)], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.height == 1
        for col in _POST_2020:
            assert out[col][0] is None, f"{col} deveria ser nulo no fixture pré-2020"
        # Buckets comuns continuam preenchidos e tipados.
        assert out["remuneracao_basica"][0] == 12000.0

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = PortalRemuneracoesBulkTransformer()
        raw = pl.DataFrame([_post_2020_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_REMUNERACOES.value]
        assert set(out.columns) == set(contract)
        assert out.schema["id_servidor"] == pl.Int64
        assert out.schema["cpf"] == pl.String
        assert out.schema["mes_ano"] == pl.String
        assert out.schema["remuneracao_basica"] == pl.Float64

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalRemuneracoesBulkTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras no CSV (ex: campo futuro) são descartadas."""
        tr = PortalRemuneracoesBulkTransformer()
        row = _post_2020_row()
        row["campo_futuro"] = "deve sumir"
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert "campo_futuro" not in out.columns
        contract = SILVER_SCHEMAS[DomainType.CG_REMUNERACOES.value]
        assert set(out.columns) == set(contract)

    def test_mes_ano_string_preservado(self):
        """``mes_ano`` permanece String ("2024-01" não vira número)."""
        tr = PortalRemuneracoesBulkTransformer()
        raw = pl.DataFrame([_post_2020_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out["mes_ano"][0] == "2024-01"
