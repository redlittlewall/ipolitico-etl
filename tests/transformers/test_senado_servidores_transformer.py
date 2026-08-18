"""Testes do SenadoServidoresTransformer — contrato Silver para servidores (issue 07).

Prior art: ``tests/transformers/test_senado_senadores_transformer.py`` — transformer
puro sobre DataFrame conhecido.
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.senado.servidores_transformer import (
    SenadoServidoresTransformer,
)

COLLECTION_URL = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/servidores"


def _raw_row(
    sequencial: int = 3008398,
    nome: str = "AARÃO PRADO BAYMA",
    cedido: dict | None = None,
) -> dict:
    """Monta linha bruta como sai do extrator (com _source_url já injetado).

    Args:
        sequencial: Sequencial do servidor (chave de dedup da Silver).
        nome: Nome do servidor.
        cedido: Objeto cedido ou None (servidor não cedido).

    Returns:
        Dict com os 12 campos brutos + ``_source_url`` da coleção.
    """
    return {
        "_source_url": COLLECTION_URL,
        "ano_admissao": "2011",
        "cargo": "Secretário Parlamentar",
        "categoria": {"codigo": "CARGO EM COMISSÃO", "nome": "Cargo em comissão"},
        "cedido": cedido,
        "especialidade": None,
        "funcao": "Assessoria",
        "lotacao": {"sigla": "E1JVIA", "nome": "Escritório de Apoio 1 do Senador Jorge Viana"},
        "nome": nome,
        "padrao": None,
        "sequencial": sequencial,
        "situacao": "DESLIGADO",
        "vinculo": "COMISSIONADO",
    }


def _cedido() -> dict:
    """Objeto cedido típico (servidor cedido ao Senado).

    Returns:
        Dict com tipo_cessao e órgãos de origem/destino.
    """
    return {
        "tipo_cessao": "CEDIDO",
        "orgao_origem": "Ministério da Fazenda",
        "orgao_destino": "Senado Federal",
    }


class TestSenadoServidoresTransformer:
    """Contrato Silver: desaninha lotacao/categoria/cedido e tipa estrito."""

    def test_happy_path_desaninha_aninhados(self):
        """Aninhados achatados em colunas snake_case com valores corretos."""
        tr = SenadoServidoresTransformer()
        raw = pl.DataFrame([_raw_row(cedido=_cedido())], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.height == 1
        assert out["sequencial"][0] == 3008398
        assert out["nome"][0] == "AARÃO PRADO BAYMA"
        assert out["vinculo"][0] == "COMISSIONADO"
        assert out["situacao"][0] == "DESLIGADO"
        assert out["ano_admissao"][0] == 2011
        assert out["lotacao_sigla"][0] == "E1JVIA"
        assert out["lotacao_nome"][0] == "Escritório de Apoio 1 do Senador Jorge Viana"
        assert out["categoria_codigo"][0] == "CARGO EM COMISSÃO"
        assert out["tipo_cessao"][0] == "CEDIDO"
        assert out["orgao_origem"][0] == "Ministério da Fazenda"
        assert out["orgao_destino"][0] == "Senado Federal"

    def test_cedido_nulo_vira_nulo_na_silver(self):
        """Servidor não cedido (``cedido: None``) → campos de cessão nulos."""
        tr = SenadoServidoresTransformer()
        raw = pl.DataFrame([_raw_row(cedido=None)], infer_schema_length=None)
        out = tr.transform(raw)

        assert out["tipo_cessao"][0] is None
        assert out["orgao_origem"][0] is None
        assert out["orgao_destino"][0] is None
        assert out["lotacao_sigla"][0] == "E1JVIA"  # demais campos intactos

    def test_cedido_ausente_vira_nulo(self):
        """Registro sem a chave ``cedido`` → campos de cessão nulos (sem crash)."""
        tr = SenadoServidoresTransformer()
        row = _raw_row()
        del row["cedido"]
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert out["tipo_cessao"][0] is None
        assert out.height == 1

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tipos e ordem com _source_url."""
        tr = SenadoServidoresTransformer()
        raw = pl.DataFrame([_raw_row()], infer_schema_length=None)
        out = tr.transform(raw)

        assert out.schema["_source_url"] == pl.String
        assert out.schema["sequencial"] == pl.Int64
        assert out.schema["nome"] == pl.String
        assert out.schema["ano_admissao"] == pl.Int64
        assert out.columns[0] == "_source_url"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoServidoresTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras no input (ex: futuro campo novo da API) são descartadas."""
        tr = SenadoServidoresTransformer()
        row = _raw_row()
        row["campo_futuro"] = "deve sumir"
        raw = pl.DataFrame([row], infer_schema_length=None)
        out = tr.transform(raw)

        assert "campo_futuro" not in out.columns
        contract = SILVER_SCHEMAS[DomainType.SERVIDORES.value]
        assert set(out.columns) == set(contract)
