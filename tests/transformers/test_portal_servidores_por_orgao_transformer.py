"""Testes do PortalServidoresPorOrgaoTransformer — contrato Silver para cg_servidores.

Prior art: ``tests/transformers/test_portal_orgaos_transformer.py`` — transformer
puro sobre DataFrame conhecido, saída exata de ``SILVER_SCHEMAS[cg_servidores]``.
O contrato espelha o agregado da API v3 ``servidores/por-orgao`` (13 campos):
contagens e dimensões SK tipadas estritas, órgão SIAPE como String (zeros à
esquerda preservados).
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.servidores_por_orgao_transformer import (
    PortalServidoresPorOrgaoTransformer,
)

API_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/servidores/por-orgao?pagina=1"


def _raw_row(
    orgao: str = "81300",
    nom_orgao: str = "MINISTERIO DA IGUALDADE RACIAL",
) -> dict:
    """Monta linha bruta como sai do extrator (com _source_url já injetado)."""
    return {
        "_source_url": API_URL,
        "qntPessoas": 1,
        "qntVinculos": 1,
        "skSituacao": 1,
        "descSituacao": "Ativo",
        "skTipoVinculo": 3,
        "descTipoVinculo": "Outros",
        "skTipoServidor": 1,
        "descTipoServidor": "Civil",
        "licenca": 0,
        "codOrgaoExercicioSiape": orgao,
        "nomOrgaoExercicioSiape": nom_orgao,
        "codOrgaoSuperiorExercicioSiape": "60000",
        "nomOrgaoSuperiorExercicioSiape": "PRESIDENCIA",
    }


class TestPortalServidoresPorOrgaoTransformer:
    """Contrato Silver: preserva contagens/dimensões e tipa estrito."""

    def test_happy_path(self):
        tr = PortalServidoresPorOrgaoTransformer()
        raw = pl.DataFrame([_raw_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.height == 1
        assert out["qntPessoas"][0] == 1
        assert out["qntVinculos"][0] == 1
        assert out["descSituacao"][0] == "Ativo"
        assert out["codOrgaoExercicioSiape"][0] == "81300"
        assert out["_source_url"][0] == API_URL

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = PortalServidoresPorOrgaoTransformer()
        raw = pl.DataFrame([_raw_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_SERVIDORES.value]
        assert set(out.columns) == set(contract)
        assert out.schema["qntPessoas"] == pl.Int64
        assert out.schema["codOrgaoExercicioSiape"] == pl.String
        assert out.schema["descTipoVinculo"] == pl.String

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalServidoresPorOrgaoTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras na resposta (ex: novo campo futuro do portal) são descartadas."""
        tr = PortalServidoresPorOrgaoTransformer()
        row = _raw_row()
        row["campo_futuro"] = "deve sumir"
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert "campo_futuro" not in out.columns
        contract = SILVER_SCHEMAS[DomainType.CG_SERVIDORES.value]
        assert set(out.columns) == set(contract)

    def test_coluna_ausente_vira_nulo(self):
        """Campo do contrato ausente na resposta → nulo, sem crash."""
        tr = PortalServidoresPorOrgaoTransformer()
        row = _raw_row()
        del row["descTipoServidor"]
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert out["descTipoServidor"][0] is None
        assert out.height == 1

    def test_zero_a_esquerda_preservado(self):
        """Órgão SIAPE com zero à esquerda permanece String ("081300" não vira 81300)."""
        tr = PortalServidoresPorOrgaoTransformer()
        raw = pl.DataFrame([_raw_row(orgao="081300")], infer_schema_length=None)
        out = tr.transform(raw)

        assert out["codOrgaoExercicioSiape"][0] == "081300"
