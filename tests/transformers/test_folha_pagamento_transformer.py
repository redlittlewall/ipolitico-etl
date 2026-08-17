"""Issue 04 — Transformer da folha de pagamento: normalização + moeda BR.

O CSV consolidado tem colunas com acento/espaços/parênteses. O transformer
normaliza para snake_case (contrato Silver), converte moeda BR (``"1.234,56"``)
para ``Float64`` e preserva ``Cargo = "Deputado {id}"`` (grupo "Parlamentar")
para a atribuição downstream do subsídio ao ``id_deputado``.
"""

import polars as pl

from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.camara.institutional_transformer import (
    CamaraFolhaPagamentoTransformer,
)


def _raw_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Cargo Individualizado do Servidor": ["Deputado 42", "Servidor João da Silva"],
            "Grupo Funcional": ["Parlamentar", "Técnico Legislativo"],
            "Folha de Pagamento": ["Subsídio", "Salário e Remunerações"],
            "Ano Ingresso": ["2019", "2011"],
            "Remuneração Fixa": ["39.293,32", "8.642,77"],
            "Vantagens de Natureza Pessoal": ["0", "1.200,00"],
            "Função ou Cargo em Comissão": ["0", "1.500,00"],
            "Gratificação Natalina": ["0", "0"],
            "Férias (1/3 Constitucional)": ["0", "0"],
            "Outras Remunerações Eventuais/Provisórias(*)": ["0", "0"],
            "Abono de Permanência": ["0", "650,00"],
            "Redutor Constitucional": ["0", "0"],
            "Constribuição Previdenciária": ["4.328,93", "1.276,00"],
            "Imposto de Renda": ["8.928,06", "900,00"],
            "Remuneração Após Descontos Obrigatórios": ["26.036,33", "9.816,77"],
            "Diárias": ["0", "0"],
            "Auxílios": ["0", "400,00"],
            "Vantagens Indenizatórias": ["14.274,20", "0"],
        }
    )


class TestCamaraFolhaPagamentoTransformer:
    def test_normaliza_colunas_para_snake_case(self):
        out = CamaraFolhaPagamentoTransformer().transform(_raw_df())
        assert "cargo" in out.columns
        assert "Cargo Individualizado do Servidor" not in out.columns
        assert "remuneracao_apos_descontos" in out.columns

    def test_cobre_o_contrato_silver_completo(self):
        out = CamaraFolhaPagamentoTransformer().transform(_raw_df())
        assert set(out.columns) == set(SILVER_SCHEMAS["folha_pagamento"])
        assert out.columns[0] == "_source_url"

    def test_preserva_cargo_deputado_e_grupo(self):
        out = CamaraFolhaPagamentoTransformer().transform(_raw_df())
        assert out["cargo"].to_list()[0] == "Deputado 42"
        assert out["grupo_funcional"].to_list()[0] == "Parlamentar"

    def test_moeda_br_vira_float64(self):
        out = CamaraFolhaPagamentoTransformer().transform(_raw_df())
        assert out["remuneracao_fixa"].dtype == pl.Float64
        assert out["remuneracao_fixa"].to_list()[0] == 39293.32
        assert out["remuneracao_apos_descontos"].to_list()[0] == 26036.33
        assert out["vantagens_indenizatorias"].to_list()[0] == 14274.20

    def test_ano_ingresso_int64(self):
        out = CamaraFolhaPagamentoTransformer().transform(_raw_df())
        assert out["ano_ingresso"].dtype == pl.Int64
        assert out["ano_ingresso"].to_list() == [2019, 2011]

    def test_vazio_permanece_vazio(self):
        out = CamaraFolhaPagamentoTransformer().transform(pl.DataFrame())
        assert out.is_empty()
