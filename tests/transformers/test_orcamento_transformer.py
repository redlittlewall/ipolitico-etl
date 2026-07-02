"""Testes dos transformers de orçamento do Senado — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.orcamento_transformer import (
    OrcamentoEmendasTransformer,
    OrcamentoOficiosTransformer,
)


class TestOrcamentoEmendasTransformer:
    """Testes do contrato SILVER para orcamento_emendas."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada (CamelCase → snake_case)."""
        tr = OrcamentoEmendasTransformer()
        raw = pl.DataFrame(
            [
                {
                    "NomeAutorOrcamento": "Abilio Brunini",
                    "IndicadorAtivo": "Não",
                    "EmailAutorOrcamento": "dep.abiliobrunini@camara.leg.br",
                    "CodigoAutorOrcamento": "4290",
                    "DataOperacao": "2023-11-29",
                    "QuantidadeEmendas": "10",
                    "AnoExecucao": "2024",
                    "NumeroMateria": "29",
                    "AnoMateria": "2023",
                    "SiglaTipoPlOrcamento": "LOA",
                    "DescricaoTipoPlOrcamento": "Lei Orçamentária Anual",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["nome_autor_orcamento"][0] == "Abilio Brunini"
        assert out["ano_execucao"][0] == 2024
        assert out["quantidade_emendas"][0] == 10
        assert out["sigla_tipo_pl_orcamento"][0] == "LOA"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = OrcamentoEmendasTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = OrcamentoEmendasTransformer()
        raw = pl.DataFrame(
            [
                {
                    "NomeAutorOrcamento": "Autor Teste",
                    "CodigoAutorOrcamento": "1234",
                    "AnoExecucao": "2025",
                    "QuantidadeEmendas": "5",
                    "SiglaTipoPlOrcamento": "LOA",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["codigo_autor_orcamento"] == pl.Int64
        assert out.schema["ano_execucao"] == pl.Int64
        assert out.schema["quantidade_emendas"] == pl.Int64
        assert out.schema["nome_autor_orcamento"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: CamposExtras) são descartadas."""
        tr = OrcamentoEmendasTransformer()
        raw = pl.DataFrame(
            [
                {
                    "NomeAutorOrcamento": "Autor Teste",
                    "CamposExtras": "valor extra",
                    "InfoAdicional": "não mapeado",
                }
            ]
        )
        out = tr.transform(raw)

        assert "CamposExtras" not in out.columns
        assert "InfoAdicional" not in out.columns

    def test_missing_fields_become_null(self):
        """Campos do contrato ausentes no input viram null."""
        tr = OrcamentoEmendasTransformer()
        raw = pl.DataFrame([{"NomeAutorOrcamento": "Autor Teste"}])
        out = tr.transform(raw)

        assert out["nome_autor_orcamento"][0] == "Autor Teste"
        assert out["indicador_ativo"][0] is None
        assert out["quantidade_emendas"][0] is None


class TestOrcamentoOficiosTransformer:
    """Testes do contrato SILVER para orcamento_oficios."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada com emendas serializadas."""
        tr = OrcamentoOficiosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 7905,
                    "tratamento": "Deputado(a)",
                    "nome": "Robinson Faria",
                    "numeroProtocoloApresentacao": "CD261863719800",
                    "dataInclusao": "2026-06-26T16:52:30.000+00:00",
                    "emendas": [
                        {
                            "id": 11496,
                            "numero": "202181000740",
                            "ano": "2021",
                            "autor": "RELATOR GERAL",
                        }
                    ],
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id"][0] == 7905
        assert out["nome"][0] == "Robinson Faria"
        assert out["numero_protocolo_apresentacao"][0] == "CD261863719800"
        assert "emendas" in out.columns
        assert isinstance(out["emendas"][0], str)

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = OrcamentoOficiosTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = OrcamentoOficiosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": "7905",
                    "tratamento": "Deputado(a)",
                    "nome": "Autor Teste",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["id"] == pl.Int64
        assert out.schema["nome"] == pl.String

    def test_emendas_serialized_when_present(self):
        """Campo 'emendas' (lista de dicts) vira string JSON."""
        tr = OrcamentoOficiosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 1,
                    "tratamento": "Senador(a)",
                    "nome": "Senador Teste",
                    "numeroProtocoloApresentacao": "SF123456",
                    "emendas": [
                        {"id": 100, "numero": "2024000001", "ano": "2024"},
                        {"id": 101, "numero": "2024000002", "ano": "2024"},
                    ],
                }
            ]
        )
        out = tr.transform(raw)

        assert isinstance(out["emendas"][0], str)
        assert "2024000001" in out["emendas"][0]
        assert "2024000002" in out["emendas"][0]

    def test_emendas_null_handling(self):
        """'emendas' como None não quebra."""
        tr = OrcamentoOficiosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 1,
                    "tratamento": "Senador(a)",
                    "nome": "Senador Teste",
                    "numeroProtocoloApresentacao": "SF123456",
                    "emendas": None,
                }
            ]
        )
        out = tr.transform(raw)

        assert out["emendas"][0] is None

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: anexos) são descartadas."""
        tr = OrcamentoOficiosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 1,
                    "tratamento": "Senador(a)",
                    "nome": "Teste",
                    "anexos": ["doc1.pdf"],
                    "historico": "algum historico",
                }
            ]
        )
        out = tr.transform(raw)

        assert "anexos" not in out.columns
        assert "historico" not in out.columns
