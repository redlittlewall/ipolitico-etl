"""Testes do PortalOrgaosTransformer — contrato Silver para cg_orgaos.

Prior art: ``tests/transformers/test_senado_servidores_transformer.py`` —
transformer puro sobre DataFrame conhecido, saída exata de
``SILVER_SCHEMAS[cg_orgaos]``. O contrato espelha a API v3 ``orgaos-siape``
(``codigo``/``descricao`` — a correção de fonte do ticket 02).
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.orgaos_transformer import (
    PortalOrgaosTransformer,
)

API_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/orgaos-siape?pagina=1"


def _raw_row(
    codigo: str = "26284",
    descricao: str = "MINISTERIO DA FAZENDA",
) -> dict:
    """Monta linha bruta como sai do extrator (com _source_url já injetado).

    Colunas espelham a API v3 ``orgaos-siape``: ``codigo`` (String, preserva
    zeros à esquerda) e ``descricao``.

    Args:
        codigo: Código SIAPE do órgão (chave de dedup da Silver).
        descricao: Nome do órgão.

    Returns:
        Dict com os campos brutos da API + ``_source_url`` da página.
    """
    return {
        "_source_url": API_URL,
        "codigo": codigo,
        "descricao": descricao,
    }


class TestPortalOrgaosTransformer:
    """Contrato Silver: preserva colunas nativas do portal e tipa estrito."""

    def test_happy_path(self):
        tr = PortalOrgaosTransformer()
        raw = pl.DataFrame([_raw_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == "26284"
        assert out["descricao"][0] == "MINISTERIO DA FAZENDA"
        assert out["_source_url"][0] == API_URL

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = PortalOrgaosTransformer()
        raw = pl.DataFrame([_raw_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_ORGAOS.value]
        assert set(out.columns) == set(contract)
        assert out.schema["_source_url"] == pl.String
        assert out.schema["codigo"] == pl.String
        assert out.schema["descricao"] == pl.String

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalOrgaosTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras na resposta (ex: novo campo futuro do portal) são descartadas."""
        tr = PortalOrgaosTransformer()
        row = _raw_row()
        row["campo_futuro"] = "deve sumir"
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert "campo_futuro" not in out.columns
        contract = SILVER_SCHEMAS[DomainType.CG_ORGAOS.value]
        assert set(out.columns) == set(contract)

    def test_coluna_ausente_vira_nulo(self):
        """Campo do contrato ausente na resposta → nulo, sem crash."""
        tr = PortalOrgaosTransformer()
        row = _raw_row()
        del row["descricao"]
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert out["descricao"][0] is None
        assert out.height == 1
