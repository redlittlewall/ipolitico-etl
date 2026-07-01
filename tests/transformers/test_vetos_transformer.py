"""Testes do contrato Silver para vetos presidenciais — novo envelope ListaVetosAnoCN."""

import polars as pl

from ipolitico.transformers.senado.vetos_transformer import (
    VetosDetalheTransformer,
    VetosPresidenciaisTransformer,
)


def _flat_record() -> dict:
    """Gera um registro flat (como produzido pelo _flatten_record do extrator)."""
    return {
        "Codigo": "17011",
        "Total": "Nao",
        "Assunto": "Créditos de Descarbonização",
        "DataRecebimentoCongresso": "2025-01-02",
        "DataPublicacao": "2024-12-31",
        "DataSobrestacaoPauta": "2025-03-05",
        "SobrestandoPauta": "Nao",
        "QuantidadeDispositivos": "3",
        "UrlDispositivos": "https://exemplo.com/disp",
        # Materia
        "Materia_Codigo": "166968",
        "Materia_SiglaCasa": "CN",
        "Materia_NomeCasa": "Congresso Nacional",
        "Materia_Sigla": "VET",
        "Materia_Numero": "50",
        "Materia_Ano": "2024",
        "Materia_EmTramitacao": "Sim",
        "Materia_Ementa": "Veto parcial aposto ao PL...",
        "Materia_UrlMovimentacoes": "https://exemplo.com/mov",
        # MateriaVetada
        "MateriaVetada_Codigo": "166093",
        "MateriaVetada_SiglaCasa": "CN",
        "MateriaVetada_NomeCasa": "Congresso Nacional",
        "MateriaVetada_Sigla": "PL",
        "MateriaVetada_Numero": "3149",
        "MateriaVetada_Ano": "2020",
        "MateriaVetada_DescricaoObjetivoProcesso": "Revisora",
        "MateriaVetada_EmTramitacao": "Nao",
        "MateriaVetada_Ementa": "Altera a Lei...",
        "MateriaVetada_UrlMovimentacoes": "https://exemplo.com/mov",
        "MateriaVetada_UrlRelatorias": "https://exemplo.com/rel",
        # NormaGerada (dentro de MateriaVetada)
        "MateriaVetada_NormaGerada_NomeNorma": "Lei 15.082",
        "MateriaVetada_NormaGerada_UrlNorma": "https://exemplo.com/lei",
        "MateriaVetada_NormaGerada_CodigoNorma": "40035256",
        "MateriaVetada_NormaGerada_SiglaTipoNorma": "LEI",
        "MateriaVetada_NormaGerada_DescricaoTipoNorma": "Lei Numerada",
        "MateriaVetada_NormaGerada_NumeroNorma": "15082",
        "MateriaVetada_NormaGerada_AnoNorma": "2024",
        "MateriaVetada_NormaGerada_DataAssinatura": "2024-12-30",
        "MateriaVetada_NormaGerada_DataPublicacao": "2024-12-31",
        "MateriaVetada_NormaGerada_SiglaVeiculoPublicacao": "DOU",
        "MateriaVetada_NormaGerada_DescricaoVeiculoPublicacao": "Diário Oficial",
        # Mensagem
        "Mensagem_Sigla": "MSG",
        "Mensagem_Numero": "1709",
        "Mensagem_Ano": "2024",
        "Mensagem_UrlPlanalto": "https://planalto.gov.br/msg",
    }


class TestVetosPresidenciaisTransformer:
    """Testes do contrato SILVER para vetos_presidenciais — novo envelope."""

    def test_happy_path(self):
        """Campos completos produzem saída tipada com snake_case."""
        tr = VetosPresidenciaisTransformer()
        raw = pl.DataFrame([_flat_record()])
        out = tr.transform(raw)

        assert out.height == 1
        # Campos flat
        assert out["codigo"][0] == 17011
        assert out["total"][0] == "Nao"
        assert out["assunto"][0] == "Créditos de Descarbonização"
        assert out["data_recebimento_congresso"][0] == "2025-01-02"
        assert out["quantidade_dispositivos"][0] == 3
        # Campos aninhados aplainados
        assert out["materia_codigo"][0] == 166968
        assert out["materia_sigla"][0] == "VET"
        assert out["materia_vetada_sigla"][0] == "PL"
        assert out["materia_vetada_ementa"][0] == "Altera a Lei..."
        assert out["materia_vetada_norma_gerada_nome_norma"][0] == "Lei 15.082"
        assert out["mensagem_url_planalto"][0] == "https://planalto.gov.br/msg"

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = VetosPresidenciaisTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos mesmo se input vier como string."""
        tr = VetosPresidenciaisTransformer()
        raw = pl.DataFrame([{"Codigo": "17011", "Materia_Codigo": "166968"}])
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["materia_codigo"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas não mapeadas (ex: link_extra) são descartadas."""
        tr = VetosPresidenciaisTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "17011",
                    "link_extra": "http://exemplo.com/extra",
                    "texto_livre": "Algum texto",
                }
            ]
        )
        out = tr.transform(raw)

        assert "link_extra" not in out.columns
        assert "texto_livre" not in out.columns


class TestVetosDetalheTransformer:
    """Testes do contrato SILVER para vetos_detalhe — novo envelope ResultadoVetoItemCN."""

    def _detail_record(self) -> dict:
        """Registro flat de detalhe com Dispositivos."""
        rec = _flat_record()
        rec["Dispositivos"] = '{"Dispositivo": [{"Codigo": "45256", "Situacao": "Mantido"}]}'
        return rec

    def test_happy_path(self):
        """Campos completos + Dispositivos produzem saída tipada."""
        tr = VetosDetalheTransformer()
        raw = pl.DataFrame([self._detail_record()])
        out = tr.transform(raw)

        assert out.height == 1
        assert out["codigo"][0] == 17011
        assert out["assunto"][0] == "Créditos de Descarbonização"
        assert out["materia_sigla"][0] == "VET"
        assert out["dispositivos"][0] is not None

    def test_empty_df(self):
        """DataFrame vazio retorna vazio."""
        tr = VetosDetalheTransformer()
        assert tr.transform(pl.DataFrame()).is_empty()

    def test_type_coercion(self):
        """Campos numéricos são coeridos."""
        tr = VetosDetalheTransformer()
        raw = pl.DataFrame([{"Codigo": "17011", "Materia_Ano": "2024"}])
        out = tr.transform(raw)

        assert out.schema["codigo"] == pl.Int64
        assert out.schema["materia_ano"] == pl.Int64

    def test_extra_columns_dropped(self):
        """Colunas extras são descartadas."""
        tr = VetosDetalheTransformer()
        raw = pl.DataFrame(
            [
                {
                    "Codigo": "17011",
                    "observacao": "Extra",
                    "dados_adicionais": "Mais dados",
                }
            ]
        )
        out = tr.transform(raw)

        assert "observacao" not in out.columns
        assert "dados_adicionais" not in out.columns
