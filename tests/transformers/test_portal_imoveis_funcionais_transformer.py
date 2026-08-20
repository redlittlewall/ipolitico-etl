"""Testes do PortalImoveisFuncionaisTransformer — contrato Silver do DTO real.

O DTO da API v3 (``/api-de-dados/imoveis``) traz ``orgaoResponsavel``,
``situacao`` e ``regiao`` como structs aninhadas. O transformer achata cada
struct em colunas ``<prefixo>_<campo>`` do contrato, preenche colunas ausentes
com nulo e aplica a tipagem estrita de ``SILVER_SCHEMAS[cg_imoveis_funcionais]``
(amostra real capturada na validação do ticket 04).
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.imoveis_funcionais_transformer import (
    PortalImoveisFuncionaisTransformer,
)

API_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/imoveis?pagina=1"

_ROW = {
    "_source_url": API_URL,
    "id": 303726581,
    "dataReferencia": "2025-11-01",
    "orgaoResponsavel": {"nome": "MINISTERIO DA DEFESA", "codigoSIAFI": "52000"},
    "situacao": {"id": 8300005, "descricao": "Ocupado"},
    "regiao": {"id": 23908718, "descricao": "Asa Sul"},
    "endereco": "SQS 112 G 103",
    "cep": "70375070",
}


class TestPortalImoveisFuncionaisTransformer:
    """Contrato real do DTO capturado (API v3)."""

    def test_happy_path(self):
        """Linha real: structs achatadas, tipos e valores preservados."""
        tr = PortalImoveisFuncionaisTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.height == 1
        assert out["id"][0] == 303726581
        assert out.schema["id"] == pl.Int64
        assert out["dataReferencia"][0] == "2025-11-01"
        assert out["orgaoResponsavel_nome"][0] == "MINISTERIO DA DEFESA"
        assert out["orgaoResponsavel_codigoSIAFI"][0] == "52000"
        assert out["situacao_id"][0] == 8300005
        assert out.schema["situacao_id"] == pl.Int64
        assert out["situacao_descricao"][0] == "Ocupado"
        assert out["regiao_id"][0] == 23908718
        assert out["regiao_descricao"][0] == "Asa Sul"
        assert out["endereco"][0] == "SQS 112 G 103"
        assert out["cep"][0] == "70375070"
        assert out["_source_url"][0] == API_URL

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = PortalImoveisFuncionaisTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_IMOVEIS_FUNCIONAIS.value]
        assert list(out.columns) == list(contract)
        assert out.schema["id"] == pl.Int64
        assert out.schema["dataReferencia"] == pl.String
        assert out.schema["cep"] == pl.String

    def test_struct_toda_nula_vira_nulo(self):
        """Struct ausente (ex: regiao nula) → colunas do contrato nulas, sem crash."""
        tr = PortalImoveisFuncionaisTransformer()
        row = {**_ROW, "regiao": None}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["regiao_id"][0] is None
        assert out["regiao_descricao"][0] is None
        # demais structs seguem achatadas normalmente
        assert out["orgaoResponsavel_nome"][0] == "MINISTERIO DA DEFESA"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalImoveisFuncionaisTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: campo futuro da API) são descartadas."""
        tr = PortalImoveisFuncionaisTransformer()
        row = {**_ROW, "campo_futuro": "deve sumir"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        contract = SILVER_SCHEMAS[DomainType.CG_IMOVEIS_FUNCIONAIS.value]
        assert list(out.columns) == list(contract)
