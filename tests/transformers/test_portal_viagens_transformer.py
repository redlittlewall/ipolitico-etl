"""Testes do PortalViagensTransformer — contrato Silver do CSV real capturado.

O extrator já renomeou as colunas do CSV via ``rename_map`` do registry (o
transformer recebe colunas em snake_case do contrato, ``_source_url`` como
primeira coluna, valores de moeda em string BR). O transformer converte moeda
BR → Float64, normaliza sentinels reais (``funcao = "-1"/"-11"`` e strings
vazias → nulo), preenche colunas do contrato ausentes com nulo e aplica a
tipagem estrita de ``SILVER_SCHEMAS[cg_viagens]``.
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.viagens_transformer import (
    PortalViagensTransformer,
)

API_URL = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/viagens/2016_20260816_Viagens.zip"

_ROW = {
    "_source_url": API_URL,
    "identificador_processo_viagem": "000000000001246317",
    "numero_pcdp": "009796/16",
    "situacao": "Realizada",
    "viagem_urgente": "NÃO",
    "justificativa_urgencia_viagem": "Sem informação",
    "cod_orgao_superior": "50000",
    "nome_orgao_superior": "MINISTERIO DA JUSTICA",
    "cod_orgao_solicitante": "52001",
    "nome_orgao_solicitante": "POLICIA FEDERAL",
    "cpf_viajante": "***.726.515-**",
    "nome_viajante": "JOAO DA SILVA",
    "cargo": "DELEGADO",
    "funcao": "DAS-1016",
    "descricao_funcao": "Cargo de Assessoramento",
    "data_inicio": "04/01/2016",
    "data_fim": "10/01/2016",
    "destinos": "BRASILIA",
    "motivo": "DILIGENCIA",
    "valor_diarias": "8.791,50",
    "valor_passagens": "0,00",
    "valor_devolucao": "0,00",
    "valor_outros_gastos": "1.234,56",
}


class TestPortalViagensTransformer:
    """Contrato real do CSV capturado (2016)."""

    def test_happy_path(self):
        """Linha real: moeda BR → Float64, datas/CPF mascarado preservados."""
        tr = PortalViagensTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.height == 1
        assert out["identificador_processo_viagem"][0] == "000000000001246317"
        assert out["situacao"][0] == "Realizada"
        assert out["cpf_viajante"][0] == "***.726.515-**"
        assert out["data_inicio"][0] == "04/01/2016"
        assert out["valor_diarias"][0] == 8791.50
        assert out["valor_passagens"][0] == 0.0
        assert out["valor_outros_gastos"][0] == 1234.56

    def test_sentinels_de_ausencia_viram_nulo(self):
        """funcao "-1" (Sem informação) e "-11" (Sigiloso) → nulo."""
        tr = PortalViagensTransformer()
        rows = [
            {**_ROW, "funcao": "-1"},
            {**_ROW, "funcao": "-11", "identificador_processo_viagem": "x2"},
            {**_ROW, "funcao": "DAS-1016", "identificador_processo_viagem": "x3"},
        ]
        out = tr.transform(pl.DataFrame(rows, infer_schema_length=None))

        assert out["funcao"].to_list() == [None, None, "DAS-1016"]

    def test_strings_vazias_viram_nulo(self):
        """Cargo/CPF vazios (reais no dump 2016) → nulo."""
        tr = PortalViagensTransformer()
        row = {**_ROW, "cargo": "", "cpf_viajante": ""}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["cargo"][0] is None
        assert out["cpf_viajante"][0] is None

    def test_texto_de_sigilo_permanece(self):
        """Texto "Informações protegidas por sigilo…" é status, não código."""
        tr = PortalViagensTransformer()
        row = {
            **_ROW,
            "cargo": "Informações protegidas por sigilo nos termos da legislação vigente",
        }
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert (
            out["cargo"][0] == "Informações protegidas por sigilo nos termos da legislação vigente"
        )

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = PortalViagensTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_VIAGENS.value]
        assert list(out.columns) == list(contract)
        assert out.schema["identificador_processo_viagem"] == pl.String
        assert out.schema["data_inicio"] == pl.String
        assert out.schema["valor_diarias"] == pl.Float64
        assert out.schema["valor_outros_gastos"] == pl.Float64

    def test_contrato_sem_id_numerico(self):
        """O CSV real NÃO tem id numérico: a chave é o identificador String."""
        contract = SILVER_SCHEMAS[DomainType.CG_VIAGENS.value]
        assert "id" not in contract
        assert contract["identificador_processo_viagem"] == pl.String

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalViagensTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: CSV de outro ano com coluna nova) são descartadas."""
        tr = PortalViagensTransformer()
        row = {**_ROW, "campo_futuro": "deve sumir"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        contract = SILVER_SCHEMAS[DomainType.CG_VIAGENS.value]
        assert list(out.columns) == list(contract)
