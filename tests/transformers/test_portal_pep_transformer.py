"""Testes do PortalPepTransformer — contrato Silver PROVISÓRIO (API v3 peps).

O dump bulk ``pep`` está indisponível (403/AccessDenied no host de dumps —
validado real no ticket 04); o contrato é provisório, derivado do JSON real da
API v3 (``/api-de-dados/peps`` — "Pessoas Expostas Politicamente"). O DTO já
vem em snake_case idêntico ao contrato, com padding fixo de espaços à direita
em ``nome``/``sigla_funcao``/``nome_orgao`` (removido pelo transformer),
``nivel_funcao`` com zeros à esquerda (String) e ``cod_orgao`` não-numérico
(ex: ``"CGUSIAPE"``).
"""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.portal_transparencia.pep_transformer import PortalPepTransformer

API_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/peps?pagina=1"

_ROW = {
    "_source_url": API_URL,
    "cpf": "***.848.518-**",
    "nome": "LUIZ MARINHO                            ",
    "sigla_funcao": "001   ",
    "descricao_funcao": "MINISTRO DE ESTADO",
    "nivel_funcao": "005",
    "cod_orgao": "CGUSIAPE",
    "nome_orgao": "MINISTERIO DO TRABALHO E PREVIDENCIA    ",
    "dt_inicio_exercicio": "2023-01-01",
    "dt_fim_exercicio": "2023-02-01",
    "dt_fim_carencia": "2028-02-01",
}


class TestPortalPepTransformer:
    """Contrato real (provisório) do DTO de peps capturado."""

    def test_happy_path(self):
        """Linha real: padding removido, tipos String e valores preservados."""
        tr = PortalPepTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.height == 1
        # padding fixo de espaços à direita removido
        assert out["nome"][0] == "LUIZ MARINHO"
        assert out["sigla_funcao"][0] == "001"
        assert out["nome_orgao"][0] == "MINISTERIO DO TRABALHO E PREVIDENCIA"
        # CPF mascarado preservado (não é normalizado)
        assert out["cpf"][0] == "***.848.518-**"
        # zeros à esquerda de nivel_funcao preservados (String, não numérico)
        assert out["nivel_funcao"][0] == "005"
        # cod_orgao não-numérico preservado
        assert out["cod_orgao"][0] == "CGUSIAPE"
        assert out["dt_fim_carencia"][0] == "2028-02-01"
        assert out["_source_url"][0] == API_URL

    def test_schema_estrito_do_contrato(self):
        """Saída segue exatamente SILVER_SCHEMAS: tudo String, _source_url 1ª."""
        tr = PortalPepTransformer()
        out = tr.transform(pl.DataFrame([_ROW], infer_schema_length=None))

        assert out.columns[0] == "_source_url"
        contract = SILVER_SCHEMAS[DomainType.CG_PEP.value]
        assert list(out.columns) == list(contract)
        assert all(out.schema[c] == pl.String for c in contract)

    def test_sem_padding_nao_quebra(self):
        """Valor sem espaços extras permanece inalterado."""
        tr = PortalPepTransformer()
        row = {**_ROW, "nome": "MARIA SILVA", "nome_orgao": "MINISTERIO DA SAUDE"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["nome"][0] == "MARIA SILVA"
        assert out["nome_orgao"][0] == "MINISTERIO DA SAUDE"

    def test_coluna_ausente_vira_nulo(self):
        """Campo ausente (ex: dt_fim_exercicio nula na resposta) → nulo."""
        tr = PortalPepTransformer()
        row = {k: v for k, v in _ROW.items() if k != "dt_fim_exercicio"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        assert out["dt_fim_exercicio"][0] is None
        assert out.schema["dt_fim_exercicio"] == pl.String

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = PortalPepTransformer()
        out = tr.transform(pl.DataFrame())
        assert out.is_empty()

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: campo futuro da API) são descartadas."""
        tr = PortalPepTransformer()
        row = {**_ROW, "campo_futuro": "deve sumir"}
        out = tr.transform(pl.DataFrame([row], infer_schema_length=None))

        contract = SILVER_SCHEMAS[DomainType.CG_PEP.value]
        assert list(out.columns) == list(contract)
