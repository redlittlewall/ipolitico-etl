"""
Testes para transformers de entidades institucionais e novos domínios bulk-only.
"""

import logging

import polars as pl
import pytest

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.camara.institutional_transformer import (
    CamaraBlocosTransformer,
    CamaraFrentesTransformer,
    CamaraFuncionariosTransformer,
    CamaraGruposTransformer,
    CamaraLegislaturasTransformer,
    CamaraTecadCategoriasTransformer,
    CamaraTecadTermosTransformer,
    _apply_contract,
)


class TestCamaraFuncionariosTransformer:
    """Transformer para funcionários da Câmara (bulk-only snapshot)."""

    @pytest.fixture
    def transformer(self):
        return CamaraFuncionariosTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.FUNCIONARIOS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_minimal_columns(self, transformer):
        """Campos mínimos são tipados e selecionados corretamente."""
        raw = pl.DataFrame(
            {
                "ponto": ["P_1234", "P_5678"],
                "codGrupo": ["1", "2"],
                "grupo": ["Quadro Efetivo", "CNE"],
                "nome": ["Ana Silva", "Carlos Souza"],
                "cargo": ["Técnico", "Analista"],
                "lotacao": ["Setor A", "Setor B"],
                "atoNomeacao": ["", ""],
                "dataNomeacao": ["", "2023-01-15"],
                "dataInicioHistorico": ["2020-03-01", "2020-05-10"],
                "dataPubNomeacao": ["", ""],
                "funcao": ["FC-1", ""],
                "uriLotacao": [
                    "https://dadosabertos.camara.leg.br/api/v2/orgaos/100046",
                    "",
                ],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["ponto"] == pl.String
        assert result.schema["codGrupo"] == pl.Int64
        assert result.schema["nome"] == pl.String
        # Verifica valores após cast
        pontos = result["ponto"].to_list()
        assert "P_1234" in pontos
        assert result["codGrupo"].to_list() == [1, 2]

    def test_transform_missing_column_adds_null(self, transformer):
        """Coluna faltante no CSV ganha NULL, não quebra."""
        raw = pl.DataFrame(
            {
                "ponto": ["P_001"],
                "codGrupo": ["1"],
                "grupo": ["Teste"],
                "nome": ["Teste"],
                "cargo": [""],
                "lotacao": [""],
                "dataInicioHistorico": ["2020-01-01"],
                # demais colunas ausentes
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["uriLotacao"] == pl.String
        assert result["uriLotacao"][0] is None


class TestCamaraTecadCategoriasTransformer:
    """Transformer para categorias TECAD (bulk-only snapshot)."""

    @pytest.fixture
    def transformer(self):
        return CamaraTecadCategoriasTransformer()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "codCategoria": ["200", "300"],
                "categoria": ["Administração Pública", "Agricultura"],
                "codSubCategoria": ["200", "301"],
                "subCategoria": ["Administração Pública", "Pecuária"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["codCategoria"] == pl.Int64
        assert result["codCategoria"].to_list() == [200, 300]
        assert result["codSubCategoria"].to_list() == [200, 301]

    def test_transform_empty(self, transformer):
        raw = pl.DataFrame(
            {
                "codCategoria": pl.Series([], dtype=pl.String),
                "categoria": pl.Series([], dtype=pl.String),
                "codSubCategoria": pl.Series([], dtype=pl.String),
                "subCategoria": pl.Series([], dtype=pl.String),
            }
        )
        result = transformer.transform(raw)
        assert result.is_empty()


class TestCamaraTecadTermosTransformer:
    """Transformer para termos TECAD (bulk-only snapshot)."""

    @pytest.fixture
    def transformer(self):
        return CamaraTecadTermosTransformer()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "codTermo": ["46892", "51668"],
                "termo": ["1ª Guerra Mundial", "14º salário"],
                "categorias": ["Identificador", "Trabalho e Emprego"],
                "subcategorias": ["Identificador de Tempo", "Trabalho e Emprego"],
                "notasExplicativas": ["", ""],
                "notasHistoricas": ["", ""],
                "notasAplicativas": ["", ""],
                "fontes": ["", ""],
                "use": ["Primeira Guerra Mundial", "Décimo quarto salário"],
                "usadoPara": ["", ""],
                "termosEspecificos": ["", ""],
                "termosGenericos": ["", ""],
                "termosRelacionados": ["", ""],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["codTermo"] == pl.Int64
        assert result["codTermo"].to_list() == [46892, 51668]
        assert "use" in result.columns

    def test_transform_empty(self, transformer):
        raw = pl.DataFrame(
            {
                "codTermo": pl.Series([], dtype=pl.String),
                "termo": pl.Series([], dtype=pl.String),
            }
        )
        result = transformer.transform(raw)
        assert result.is_empty()


class TestCamaraLicitacoesTransformer:
    """Transformer para licitações (bulk-only, dumps CSV anuais)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraLicitacoesTransformer,
        )

        return CamaraLicitacoesTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.LICITACOES.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "idLicitacao": ["19616", "19738"],
                "numero": ["1", "2"],
                "ano": ["2024", "2024"],
                "numProcesso": ["365069", "249497"],
                "anoProcesso": ["2024", "2024"],
                "objeto": [
                    "Concurso para seleção de obras radiofônicas",
                    "Concurso de obras Audiovisuais",
                ],
                "modalidade": ["Concurso", "Concurso"],
                "tipo": ["Melhor Técnica", "Melhor Técnica"],
                "situacao": [
                    "Instrumento convocatório publicado",
                    "Instrumento convocatório publicado",
                ],
                "vlrEstimado": ["0", "50000"],
                "vlrContratado": ["0", "0"],
                "vlrPago": ["0", "0"],
                "dataAutorizacao": ["2024-06-05", "2024-07-15"],
                "dataPublicacao": ["2024-06-17", "2024-08-05"],
                "dataAbertura": ["", ""],
                "numItens": ["1", "1"],
                "numUnidades": ["1", "5"],
                "numPropostas": ["0", "0"],
                "numContratos": ["0", "0"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idLicitacao"] == pl.Int64
        assert result.schema["objeto"] == pl.String
        assert result.schema["vlrEstimado"] == pl.Float64
        assert result["idLicitacao"].to_list() == [19616, 19738]


class TestCamaraLicitacoesContratosTransformer:
    """Transformer para contratos de licitação (bulk-only, dumps CSV anuais)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraLicitacoesContratosTransformer,
        )

        return CamaraLicitacoesContratosTransformer()

    def test_transform_empty_df(self, transformer):
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.LICITACOES_CONTRATOS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "ano": ["2024", "2024"],
                "idLicitacao": ["19456", "19472"],
                "numContrato": ["93", "184"],
                "anoContrato": ["2025", "2024"],
                "tipoContrato": ["Contrato", "Contrato"],
                "situacaoContrato": ["Vigente", "Vigente"],
                "vlrOriginal": ["181000", "10099812"],
                "vlrTotal": ["226250", "10099812"],
                "objeto": [
                    "Aquisição de painel de videowall",
                    "PRESTAÇÃO DE SERVIÇOS DE AGENCIAMENTO",
                ],
                "dataAssinatura": ["2025-04-29", "2024-09-10"],
                "dataPublicacao": ["2025-04-30", "2024-09-10"],
                "dataInicioVigenciaOriginal": ["2025-04-29", "2024-09-10"],
                "dataFimVigenciaOriginal": ["2026-07-28", "2026-09-09"],
                "dataFimUltimaVigencia": ["2026-07-28", "2026-09-09"],
                "fornecedorCpfCnpj": [
                    "35.364.825/0001-70",
                    "16.604.411/0001-26",
                ],
                "fornecedorNome": [
                    "P1LED COMÉRCIO E IMPORTAÇÃO",
                    "ÉTICA TURISMO VIAGENS RECEPTIVOS",
                ],
                "fornecedorEndereco": [
                    "RUA ESTADOS UNIDOS, 2186",
                    "VENIDA FELICIANO COELHO, 1438",
                ],
                "fornecedorCidade": ["SÃO PAULO", "MACAPÁ"],
                "fornecedorSiglaUF": ["SP", "AP"],
                "numSeqArquivoInstrContratual": ["13816", "13320"],
                "txtNomeArquivo": [
                    "P1LED COMERCIO -  2025.093.0.pdf",
                    "ETICA TURISMO - 2024.184.0.pdf",
                ],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idLicitacao"] == pl.Int64
        assert result.schema["numContrato"] == pl.Int64
        assert result.schema["fornecedorNome"] == pl.String
        assert result.schema["vlrOriginal"] == pl.Float64
        assert result["numContrato"].to_list() == [93, 184]


class TestCamaraLicitacoesItensTransformer:
    """Transformer para itens de licitação (bulk-only, dumps CSV anuais)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraLicitacoesItensTransformer,
        )

        return CamaraLicitacoesItensTransformer()

    def test_transform_empty_df(self, transformer):
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.LICITACOES_ITENS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "ano": ["2024", "2024"],
                "idLicitacao": ["19425", "19425"],
                "numItem": ["8", "9"],
                "numSubitem": ["0", "0"],
                "descricao": ["TRANSPALETE MANUAL", "QUADRO BRANCO MAGNÉTICO"],
                "especificacao": ["", ""],
                "unidade": ["UN", "UN"],
                "qtdLicitada": ["1", "8"],
                "vlrUnitarioEstimado": ["2649", "2253"],
                "qtdContratada": ["1", "8"],
                "vlrUnitarioContratado": ["2349", "1910"],
                "vlrTotalContratado": ["34875", "34876"],
                "fornecedorCpfCnpj": [
                    "44.258.379/0001-00",
                    "29.926.189/0001-20",
                ],
                "fornecedorNome": ["Worker", "Cortiarte"],
                "uriContrato": ["", ""],
                "numContrato": ["34875", "34876"],
                "anoContrato": ["2024", "2024"],
                "tipoContrato": ["", ""],
                "situacaoItem": ["", ""],
                "observacoes": ["", ""],
                "naturezaDespesa": ["", ""],
                "programaTrabalho": ["", ""],
                "codPTRES": ["", ""],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idLicitacao"] == pl.Int64
        assert result.schema["numItem"] == pl.Int64
        assert result.schema["descricao"] == pl.String
        assert result.schema["vlrTotalContratado"] == pl.Float64
        assert result["numItem"].to_list() == [8, 9]


class TestCamaraLicitacoesPedidosTransformer:
    """Transformer para pedidos de licitação (bulk-only, dumps CSV anuais)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraLicitacoesPedidosTransformer,
        )

        return CamaraLicitacoesPedidosTransformer()

    def test_transform_empty_df(self, transformer):
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.LICITACOES_PEDIDOS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "ano": ["2024", "2024"],
                "idLicitacao": ["19246", "19246"],
                "tipoRegistro": ["Pedido", "Pedido"],
                "numPedido": ["151", "152"],
                "anoPedido": ["2022", "2022"],
                "dataHoraCadastro": [
                    "2022-04-27 17:23:55.843",
                    "2022-05-10 10:00:00.000",
                ],
                "idOrgao": ["", ""],
                "orgao": [
                    "DEPARTAMENTO TÉCNICO",
                    "DEPARTAMENTO TÉCNICO",
                ],
                "objeto": [
                    "Aquisição de Scanner Planetário",
                    "Aquisição de Scanner Planetário",
                ],
                "observacoes": ["", ""],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idLicitacao"] == pl.Int64
        assert result.schema["numPedido"] == pl.Int64
        assert result.schema["orgao"] == pl.String


class TestCamaraLicitacoesPropostasTransformer:
    """Transformer para propostas de licitação (bulk-only, dumps CSV anuais)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraLicitacoesPropostasTransformer,
        )

        return CamaraLicitacoesPropostasTransformer()

    def test_transform_empty_df(self, transformer):
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.LICITACOES_PROPOSTAS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "ano": ["2024", "2024"],
                "idLicitacao": ["19425", "19425"],
                "numItem": ["8", "9"],
                "descricao": ["TRANSPALETE MANUAL", "QUADRO BRANCO MAGNÉTICO"],
                "numSubitens": ["1", "1"],
                "unidadesLicitadas": ["1", "8"],
                "vlrEstimado": ["2649", "2253"],
                "unidadesProposta": ["1", "8"],
                "vlrProposta": ["2349", "1910"],
                "numProposta": ["34875", "34876"],
                "marcaProposta": ["Worker", "Cortiarte"],
                "fornecedorCpfCnpj": [
                    "44.258.379/0001-00",
                    "29.926.189/0001-20",
                ],
                "fornecedorSituacao": ["Incluído", "Incluído"],
                "dataProposta": ["2024-07-30", "2024-07-29"],
                "diasValidadeProposta": ["120", "60"],
                "observacoes": ["", ""],
                "urlDocumento": ["", ""],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idLicitacao"] == pl.Int64
        assert result.schema["numItem"] == pl.Int64
        assert result.schema["vlrProposta"] == pl.Float64
        assert result["numProposta"].to_list() == [34875, 34876]


class TestCamaraEventosPresencaDeputadosTransformer:
    """Transformer para eventosPresencaDeputados (bulk-only yearly)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraEventosPresencaDeputadosTransformer,
        )

        return CamaraEventosPresencaDeputadosTransformer()

    def test_transform_empty(self, transformer):
        schema = SILVER_SCHEMAS[DomainType.EVENTOS_PRESENCA_DEPUTADOS.value]
        df = pl.DataFrame({col: pl.Series([], dtype=t) for col, t in schema.items()})
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "idEvento": ["71665", "71666"],
                "uriEvento": [
                    "https://dadosabertos.camara.leg.br/api/v2/eventos/71665",
                    "https://dadosabertos.camara.leg.br/api/v2/eventos/71666",
                ],
                "dataHoraInicio": ["2024-03-26T10:13:03", "2024-03-26T11:00:00"],
                "idDeputado": ["74848", "88256"],
                "uriDeputado": [
                    "https://dadosabertos.camara.leg.br/api/v2/deputados/74848",
                    "https://dadosabertos.camara.leg.br/api/v2/deputados/88256",
                ],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idEvento"] == pl.Int64
        assert result.schema["idDeputado"] == pl.Int64
        assert result["idEvento"].to_list() == [71665, 71666]
        assert result["idDeputado"].to_list() == [74848, 88256]


class TestCamaraEventosRequerimentosTransformer:
    """Transformer para eventosRequerimentos (bulk-only yearly)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraEventosRequerimentosTransformer,
        )

        return CamaraEventosRequerimentosTransformer()

    def test_transform_empty(self, transformer):
        schema = SILVER_SCHEMAS[DomainType.EVENTOS_REQUERIMENTOS.value]
        df = pl.DataFrame({col: pl.Series([], dtype=t) for col, t in schema.items()})
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "idEvento": ["71834", "71837"],
                "uriEvento": [
                    "https://dadosabertos.camara.leg.br/api/v2/eventos/71834",
                    "https://dadosabertos.camara.leg.br/api/v2/eventos/71837",
                ],
                "tituloRequerimento": ["REQ 247/2024", "REQ 74/2024"],
                "uriRequerimento": [
                    "https://dadosabertos.camara.leg.br/api/v2/proposicoes/2417914",
                    "https://dadosabertos.camara.leg.br/api/v2/proposicoes/2417029",
                ],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idEvento"] == pl.Int64
        assert result.schema["tituloRequerimento"] == pl.String
        assert result["idEvento"].to_list() == [71834, 71837]


class TestCamaraVotacoesObjetosTransformer:
    """Transformer para votacoesObjetos (bulk-only yearly)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraVotacoesObjetosTransformer,
        )

        return CamaraVotacoesObjetosTransformer()

    def test_transform_empty(self, transformer):
        schema = SILVER_SCHEMAS[DomainType.VOTACOES_OBJETOS.value]
        df = pl.DataFrame({col: pl.Series([], dtype=t) for col, t in schema.items()})
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "idVotacao": ["2355879-42"],
                "uriVotacao": ["https://dadosabertos.camara.leg.br/api/v2/votacoes/2355879-42"],
                "data": ["2024-02-06"],
                "descricao": ["Aprovado o Substitutivo"],
                "proposicao_id": ["2380451"],
                "proposicao_uri": ["https://dadosabertos.camara.leg.br/api/v2/proposicoes/2380451"],
                "proposicao_ementa": ["Cria a Semana Cultural Interescolar"],
                "proposicao_codTipo": ["392"],
                "proposicao_siglaTipo": ["REQ"],
                "proposicao_numero": ["2617"],
                "proposicao_ano": ["2023"],
                "proposicao_titulo": ["REQ 2617/2023"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["idVotacao"] == pl.String
        assert result.schema["proposicao_id"] == pl.Int64
        assert result["proposicao_id"].to_list() == [2380451]
        assert result["proposicao_siglaTipo"].to_list() == ["REQ"]


class TestCamaraVotacoesProposicoesTransformer:
    """Transformer para votacoesProposicoes (bulk-only yearly)."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.camara.institutional_transformer import (
            CamaraVotacoesProposicoesTransformer,
        )

        return CamaraVotacoesProposicoesTransformer()

    def test_transform_empty(self, transformer):
        schema = SILVER_SCHEMAS[DomainType.VOTACOES_PROPOSICOES.value]
        df = pl.DataFrame({col: pl.Series([], dtype=t) for col, t in schema.items()})
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_happy_path(self, transformer):
        raw = pl.DataFrame(
            {
                "idVotacao": ["1006391-32", "1029052-77"],
                "uriVotacao": [
                    "https://dadosabertos.camara.leg.br/api/v2/votacoes/1006391-32",
                    "https://dadosabertos.camara.leg.br/api/v2/votacoes/1029052-77",
                ],
                "data": ["2024-02-20", "2024-06-19"],
                "descricao": ["Aprovado requerimento", "Aprovado o Parecer"],
                "proposicao_id": ["1006391", "1029052"],
                "proposicao_uri": [
                    "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1006391",
                    "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1029052",
                ],
                "proposicao_titulo": ["PL 742/2015", "PL 761/2015"],
                "proposicao_ementa": ["Dispõe sobre a obrigatoriedade", "Acrescenta o inciso VI"],
                "proposicao_codTipo": ["139", "139"],
                "proposicao_siglaTipo": ["PL", "PL"],
                "proposicao_numero": ["742", "761"],
                "proposicao_ano": ["2015", "2015"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["idVotacao"] == pl.String
        assert result.schema["proposicao_id"] == pl.Int64
        assert result["proposicao_numero"].to_list() == [742, 761]
        assert result["proposicao_ano"].to_list() == [2015, 2015]


class TestApplyContractLogging:
    """Testes de logging do _apply_contract sobre perda silenciosa de dados."""

    def test_data_loss_on_unparseable_value_logs_warning(self, caplog):
        """Valor inparseável no cast gera WARNING com nome da coluna e contagem."""
        caplog.set_level(logging.WARNING)
        df = pl.DataFrame(
            {
                "id": ["1", "abc", "3"],
                "idLegislatura": ["56", "57", "58"],
                "nome": ["Bloco A", "Bloco B", "Bloco C"],
                "uri": ["http://a", "http://b", "http://c"],
            }
        )

        _apply_contract(df, DomainType.BLOCOS.value)

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) >= 1, "Deveria ter emitido ao menos um WARNING"
        assert any("id" in w.message for w in warnings), (
            "WARNING deveria citar a coluna 'id' com perda de dados"
        )

    def test_clean_cast_emits_no_warning(self, caplog):
        """Cast bem-sucedido de todas as colunas não gera WARNING."""
        caplog.set_level(logging.WARNING)
        df = pl.DataFrame(
            {
                "id": ["1", "2", "3"],
                "idLegislatura": ["56", "57", "58"],
                "nome": ["Bloco A", "Bloco B", "Bloco C"],
                "uri": ["http://a", "http://b", "http://c"],
            }
        )

        _apply_contract(df, DomainType.BLOCOS.value)

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 0, "Cast limpo não deveria gerar WARNING"

    def test_missing_column_added_no_warning(self, caplog):
        """Coluna do contrato ausente no input é adicionada como null sem WARNING."""
        caplog.set_level(logging.WARNING)
        df = pl.DataFrame(
            {
                "id": ["1", "2", "3"],
                "idLegislatura": ["56", "57", "58"],
                "nome": ["Bloco A", "Bloco B", "Bloco C"],
                # 'uri' ausente — será adicionada como null
            }
        )

        _apply_contract(df, DomainType.BLOCOS.value)

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 0, "Coluna ausente adicionada como null não é perda de dados"

    def test_multiple_columns_with_data_loss(self, caplog):
        """Múltiplas colunas com valores inparseáveis geram WARNING para cada uma."""
        caplog.set_level(logging.WARNING)
        df = pl.DataFrame(
            {
                "id": ["1", "abc", "3"],
                "idLegislatura": ["xyz", "57", "58"],
                "nome": ["Bloco A", "Bloco B", "Bloco C"],
                "uri": ["http://a", "http://b", "http://c"],
            }
        )

        _apply_contract(df, DomainType.BLOCOS.value)

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 2, "Duas colunas com perda deveriam gerar 2 WARNINGs"
        messages = [w.message for w in warnings]
        assert any("id" in m for m in messages)
        assert any("idLegislatura" in m for m in messages)


class TestCamaraBlocosTransformer:
    """Transformer para blocos parlamentares."""

    @pytest.fixture
    def transformer(self):
        return CamaraBlocosTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.BLOCOS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_minimal_columns(self, transformer):
        """Campos mínimos são tipados e selecionados corretamente."""
        raw = pl.DataFrame(
            {
                "id": ["1", "2"],
                "idLegislatura": ["57", "57"],
                "nome": ["Bloco A", "Bloco B"],
                "uri": [
                    "https://dadosabertos.camara.leg.br/api/v2/blocos/1",
                    "https://dadosabertos.camara.leg.br/api/v2/blocos/2",
                ],
                "federacao": [True, False],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 2
        assert result.schema["id"] == pl.Int64
        assert result.schema["federacao"] == pl.Boolean

    def test_transform_adds_missing_columns(self, transformer):
        """Coluna 'federacao' ausente no input é adicionada como null."""
        raw = pl.DataFrame(
            {
                "id": ["1"],
                "idLegislatura": ["57"],
                "nome": ["Bloco A"],
                "uri": ["http://u"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert "federacao" in result.columns
        assert result["federacao"].is_null().all()


class TestCamaraFrentesTransformer:
    """Transformer para frentes parlamentares."""

    @pytest.fixture
    def transformer(self):
        return CamaraFrentesTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.FRENTES.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_minimal_columns(self, transformer):
        """Campos mínimos são tipados e selecionados corretamente."""
        raw = pl.DataFrame(
            {
                "id": ["10"],
                "idLegislatura": ["57"],
                "titulo": ["Frente Parlamentar X"],
                "uri": ["https://dadosabertos.camara.leg.br/api/v2/frentes/10"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["id"] == pl.Int64
        assert result.schema["titulo"] == pl.String


class TestCamaraGruposTransformer:
    """Transformer para grupos parlamentares."""

    @pytest.fixture
    def transformer(self):
        return CamaraGruposTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.GRUPOS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_minimal_columns(self, transformer):
        """Campos mínimos com ultimoStatus Struct são serializados."""
        raw = pl.DataFrame(
            {
                "id": ["1"],
                "nome": ["Grupo A"],
                "uri": ["http://u"],
                "anoCriacao": ["2023"],
                "ativo": ["Sim"],
                "ultimoStatus": [{"codSituacao": 1, "descricaoSituacao": "Ativo"}],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["ultimoStatus"] == pl.String
        assert '"descricaoSituacao"' in result["ultimoStatus"][0]

    def test_transform_ultimo_status_absent(self, transformer):
        """Coluna ultimoStatus ausente não quebra."""
        raw = pl.DataFrame(
            {
                "id": ["1"],
                "nome": ["Grupo A"],
                "uri": ["http://u"],
                "anoCriacao": ["2023"],
                "ativo": ["Sim"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result["ultimoStatus"].is_null().all()


class TestCamaraLegislaturasTransformer:
    """Transformer para legislaturas."""

    @pytest.fixture
    def transformer(self):
        return CamaraLegislaturasTransformer()

    def test_transform_empty_df(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame(
            {
                col: pl.Series([], dtype=t)
                for col, t in SILVER_SCHEMAS[DomainType.LEGISLATURAS.value].items()
            }
        )
        result = transformer.transform(df)
        assert result.is_empty()

    def test_transform_minimal_columns(self, transformer):
        """Campos mínimos são tipados e datas truncadas para 10 chars."""
        raw = pl.DataFrame(
            {
                "id": ["57"],
                "uri": ["http://u"],
                "dataInicio": ["2023-02-01T00:00:00Z"],
                "dataFim": ["2027-01-31T23:59:59Z"],
            }
        )
        result = transformer.transform(raw)
        assert result.height == 1
        assert result.schema["id"] == pl.Int64
        assert result["dataInicio"][0] == "2023-02-01"
        assert result["dataFim"][0] == "2027-01-31"
