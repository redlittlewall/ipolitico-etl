"""Testes do SenadoProcessosTransformer — contrato Silver."""

import polars as pl

from ipolitico.transformers.senado.processos_transformer import (
    SenadoProcessosDetalheTransformer,
    SenadoProcessosDocumentosTransformer,
    SenadoProcessosEmendasTransformer,
    SenadoProcessosTransformer,
)


class TestSenadoProcessosTransformer:
    """Testes do contrato SILVER para processos."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoProcessosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 1326805,
                    "codigoMateria": 603,
                    "identificacao": "PDS 16/1984",
                    "ementa": "Aprova o texto...",
                    "autoria": "Câmara dos Deputados",
                    "tipoDocumento": "Projeto de Decreto Legislativo",
                    "dataApresentacao": "1949-05-31",
                    "situacaoAtual": "MATÉRIA COM A RELATORIA",
                    "dataSituacaoAtual": "2023-03-23",
                    "casaIdentificadora": "SF",
                    "tramitando": "Sim",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id"][0] == 1326805
        assert out["identificacao"][0] == "PDS 16/1984"
        assert out["tramitando"][0] == "Sim"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoProcessosTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = SenadoProcessosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": "1326805",
                    "codigoMateria": "603",
                    "identificacao": "PDS 16/1984",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["id"] == pl.Int64
        assert out.schema["codigo_materia"] == pl.Int64
        assert out.schema["identificacao"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas extras (ex: objetivo) são descartadas."""
        tr = SenadoProcessosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 1,
                    "codigoMateria": 1,
                    "identificacao": "Teste",
                    "objetivo": "Revisora",  # não está no contrato
                    "tipoConteudo": "Apreciação",
                }
            ]
        )
        out = tr.transform(raw)

        assert "objetivo" not in out.columns
        assert "tipoConteudo" not in out.columns


class TestSenadoProcessosDetalheTransformer:
    """Testes do contrato SILVER para processos_detalhe."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoProcessosDetalheTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 2904181,
                    "codigoMateria": 236,
                    "identificacao": "MSG 31/1991",
                    "sigla": "MSG",
                    "numero": "31",
                    "ano": 1991,
                    "casaIdentificadora": "CN",
                    "tramitando": "Sim",
                    "dataInicioEfetivo": "1991-04-15",
                    "situacaoAtual": "AGUARDANDO DESIGNAÇÃO DO RELATOR",
                    "dataSituacaoAtual": "2023-02-02",
                    "conteudo": {
                        "ementa": "Encaminha as Contas do Governo Federal...",
                    },
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id"][0] == 2904181
        assert out["identificacao"][0] == "MSG 31/1991"
        assert out["situacao_atual"][0] == "AGUARDANDO DESIGNAÇÃO DO RELATOR"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoProcessosDetalheTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = SenadoProcessosDetalheTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": "2904181",
                    "codigoMateria": "236",
                    "numero": "31",
                    "ano": "1991",
                    "identificacao": "MSG 31/1991",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["id"] == pl.Int64
        assert out.schema["ano"] == pl.Int64
        assert out.schema["identificacao"] == pl.String

    def test_extra_columns_dropped(self):
        """Colunas aninhadas (conteudo, documento, etc) são descartadas."""
        tr = SenadoProcessosDetalheTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 2904181,
                    "codigoMateria": 236,
                    "identificacao": "MSG 31/1991",
                    "despachos": [{"data": "2023-01-01"}],
                    "autoriaIniciativa": [{"autor": "Teste"}],
                    "outrosNumeros": [],
                }
            ]
        )
        out = tr.transform(raw)

        assert "despachos" not in out.columns
        assert "autoriaIniciativa" not in out.columns
        assert "outrosNumeros" not in out.columns


class TestSenadoProcessosEmendasTransformer:
    """Testes do contrato SILVER para processos_emendas."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoProcessosEmendasTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 9540193,
                    "idProcesso": 8294609,
                    "identificacao": "EMENDA 2 / CSP - PL 2253/2022",
                    "autoria": "Senador Sergio Moro (UNIÃO/PR)",
                    "casa": "SF",
                    "dataApresentacao": "2024-02-01",
                    "descricaoDocumentoEmenda": "Emenda ao PL 2253/2022 - CSP",
                    "tipo": "EMENDA_PARCIAL",
                    "numero": "2",
                    "nomeColegiado": "Comissão de Segurança Pública",
                    "siglaColegiado": "CSP",
                    "urlDocumentoEmenda": "http://...",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id_processo"][0] == 8294609
        assert out["identificacao"][0] == "EMENDA 2 / CSP - PL 2253/2022"
        assert out["tipo"][0] == "EMENDA_PARCIAL"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoProcessosEmendasTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos."""
        tr = SenadoProcessosEmendasTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": "9540193",
                    "idProcesso": "8294609",
                    "identificacao": "EMENDA 1",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["id"] == pl.Int64
        assert out.schema["id_processo"] == pl.Int64

    def test_decisoes_list_serialized(self):
        """Campo 'decisoes' (lista de dicts) é serializado como string."""
        tr = SenadoProcessosEmendasTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 9540193,
                    "idProcesso": 8294609,
                    "identificacao": "EMENDA 1",
                    "decisoes": [
                        {"data": "2024-02-06", "descricaoTipo": "Aprovada"},
                    ],
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert "decisoes" in out.columns
        assert isinstance(out["decisoes"][0], str)


class TestSenadoProcessosDocumentosTransformer:
    """Testes do contrato SILVER para processos_documentos."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada."""
        tr = SenadoProcessosDocumentosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 9538518,
                    "identificacao": "Termo de Adesão - SF245968923787",
                    "autoria": "Senador Jorge Seif (PL/SC)",
                    "casaEnteRecebedor": "SF",
                    "casaRecebedora": "CN",
                    "dataDocumento": "2023-10-31",
                    "dataRecebimento": "2024-01-08",
                    "descricao": "Termo de Adesão...",
                    "descricaoTipo": "Termo de Adesão",
                    "siglaTipo": "TERMO_ADESAO",
                    "siglaEnteRecebedor": "NPFG",
                    "nomeEnteRecebedor": "Núcleo de premiações",
                    "urlDocumento": "http://...",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.height == 1
        assert out["id"][0] == 9538518
        assert out["casa_ente_recebedor"][0] == "SF"
        assert out["sigla_tipo"][0] == "TERMO_ADESAO"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = SenadoProcessosDocumentosTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos."""
        tr = SenadoProcessosDocumentosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": "9538518",
                    "identificacao": "Documento 1",
                }
            ]
        )
        out = tr.transform(raw)

        assert out.schema["id"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas aninhadas (autores, etc) são descartadas."""
        tr = SenadoProcessosDocumentosTransformer()
        raw = pl.DataFrame(
            [
                {
                    "id": 9538518,
                    "identificacao": "Documento 1",
                    "autores": [{"autor": "Teste"}],
                    "apresentadoNosProcessos": None,
                }
            ]
        )
        out = tr.transform(raw)

        assert "autores" not in out.columns
        assert "apresentadoNosProcessos" not in out.columns
