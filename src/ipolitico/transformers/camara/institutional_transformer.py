"""Transformers para entidades institucionais (blocos, frentes, grupos, legislaturas)."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns

logger = logging.getLogger(__name__)


def _apply_contract(df: pl.DataFrame, domain_key: str) -> pl.DataFrame:
    """
    Aplica o schema SILVER_SCHEMAS[domain_key] ao DataFrame via cast.

    Colunas faltantes no input são adicionadas como NULL. Colunas existentes
    com tipos incompatíveis são convertidas com ``strict=False``, e valores
    inparseáveis tornam-se NULL. Um WARNING é emitido quando colunas que
    continham dados não-nulos no input resultam em nulls após o cast,
    sinalizando perda silenciosa de dados.

    Args:
        df: DataFrame bruto (tipicamente lido de CSV ou API).
        domain_key: Chave no SILVER_SCHEMAS que define o contrato de tipos.

    Returns:
        DataFrame com as colunas do contrato nos tipos especificados.
    """
    contract = SILVER_SCHEMAS[domain_key]
    input_cols = set(df.columns)

    for col in contract:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    result = df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])

    for col in contract:
        if col not in input_cols:
            continue
        nulls = result[col].is_null().sum()
        if nulls > 0:
            non_null_input = df[col].is_not_null().sum()
            if non_null_input > 0:
                logger.warning(
                    "Perda de dados em '%s.%s': %d null(s) após cast para %s "
                    "(de %d valores não-nulos no input)",
                    domain_key,
                    col,
                    nulls,
                    contract[col],
                    non_null_input,
                )

    return result


class CamaraBlocosTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        if "id" in df.columns:
            df = df.with_columns(pl.col("id").cast(pl.Int64, strict=False))
        return _apply_contract(df, DomainType.BLOCOS.value)


class CamaraFrentesTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.FRENTES.value)


class CamaraGruposTransformer(BaseTransformer):
    """Transformer para o domínio Grupos (bancadas, minoria, etc.).

    Serializa ultimoStatus (Struct da API) para string usando expressão nativa
    Polars, em vez de map_elements, para preservar paralelismo vetorizado.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        if "ultimoStatus" in df.columns:
            dtype = df.schema["ultimoStatus"]
            if isinstance(dtype, pl.Struct):
                df = df.with_columns(pl.col("ultimoStatus").struct.json_encode())
        return _apply_contract(df, DomainType.GRUPOS.value)


class CamaraLegislaturasTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        for col in ("dataInicio", "dataFim"):
            if col in df.columns:
                df = df.with_columns(
                    pl.when(pl.col(col).is_not_null())
                    .then(pl.col(col).cast(pl.Utf8).str.slice(0, 10))
                    .alias(col)
                )
        return _apply_contract(df, DomainType.LEGISLATURAS.value)


class CamaraFuncionariosTransformer(BaseTransformer):
    """Transformer para o domínio funcionarios (servidores da Câmara, bulk-only snapshot).

    O CSV bruto tem colunas como ponto (String com prefixo P_),
    codGrupo (numérico), nome, cargo, lotação etc. O transformer apenas
    aplica o contrato SILVER_SCHEMAS — a conversão de tipos numéricos é
    feita via schema_overrides no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.FUNCIONARIOS.value)


class CamaraTecadCategoriasTransformer(BaseTransformer):
    """Transformer para o domínio tecadCategorias (categorias do tesauro, bulk-only snapshot).

    O CSV bruto tem colunas: codCategoria, categoria, codSubCategoria, subCategoria.
    A conversão de códigos numéricos para Int64 é feita via schema_overrides
    no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.TECAD_CATEGORIAS.value)


class CamaraTecadTermosTransformer(BaseTransformer):
    """Transformer para o domínio tecadTermos (termos do tesauro, bulk-only snapshot).

    O CSV bruto tem colunas: codTermo, termo, categorias, subcategorias,
    notas*, use, usadoPara, termosEspecificos, termosGenericos, termosRelacionados.
    A conversão de codTermo para Int64 é feita via schema_overrides
    no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.TECAD_TERMOS.value)


class CamaraLicitacoesTransformer(BaseTransformer):
    """Transformer para o domínio licitacoes (bulk-only, dumps CSV anuais).

    O CSV bruto tem colunas: idLicitacao, numero, ano, numProcesso, anoProcesso,
    objeto, modalidade, tipo, situacao, vlrEstimado, vlrContratado, vlrPago,
    datas e contagens numéricas. A conversão de tipos numéricos é feita via
    schema_overrides no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.LICITACOES.value)


class CamaraLicitacoesContratosTransformer(BaseTransformer):
    """Transformer para o domínio licitacoesContratos (bulk-only, dumps CSV anuais).

    O CSV bruto tem colunas: ano, idLicitacao, numContrato, anoContrato,
    tipoContrato, situacaoContrato, vlrOriginal, vlrTotal, objeto, datas vigência,
    fornecedor*, numSeqArquivoInstrContratual, txtNomeArquivo.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.LICITACOES_CONTRATOS.value)


class CamaraLicitacoesItensTransformer(BaseTransformer):
    """Transformer para o domínio licitacoesItens (bulk-only, dumps CSV anuais).

    O CSV bruto tem colunas: ano, idLicitacao, numItem, numSubitem, descricao,
    especificacao, unidade, qtdLicitada, vlrUnitarioEstimado, qtdContratada,
    vlrUnitarioContratado, vlrTotalContratado, fornecedor*, uriContrato,
    numContrato, anoContrato, tipoContrato, situacaoItem, observacoes,
    naturezaDespesa, programaTrabalho, codPTRES.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.LICITACOES_ITENS.value)


class CamaraLicitacoesPedidosTransformer(BaseTransformer):
    """Transformer para o domínio licitacoesPedidos (bulk-only, dumps CSV anuais).

    O CSV bruto tem colunas: ano, idLicitacao, tipoRegistro, numPedido,
    anoPedido, dataHoraCadastro, idOrgao, orgao, objeto, observacoes.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.LICITACOES_PEDIDOS.value)


class CamaraLicitacoesPropostasTransformer(BaseTransformer):
    """Transformer para o domínio licitacoesPropostas (bulk-only, dumps CSV anuais).

    O CSV bruto tem colunas: ano, idLicitacao, numItem, descricao, numSubitens,
    unidadesLicitadas, vlrEstimado, unidadesProposta, vlrProposta, numProposta,
    marcaProposta, fornecedorCpfCnpj, fornecedorSituacao, dataProposta,
    diasValidadeProposta, observacoes, urlDocumento.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.LICITACOES_PROPOSTAS.value)


class CamaraEventosPresencaDeputadosTransformer(BaseTransformer):
    """Transformer para o domínio eventosPresencaDeputados (bulk-only yearly).

    O CSV bruto tem colunas: idEvento, uriEvento, dataHoraInicio, idDeputado,
    uriDeputado. A conversão de tipos numéricos é feita via schema_overrides
    no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.EVENTOS_PRESENCA_DEPUTADOS.value)


class CamaraEventosRequerimentosTransformer(BaseTransformer):
    """Transformer para o domínio eventosRequerimentos (bulk-only yearly).

    O CSV bruto tem colunas: idEvento, uriEvento, tituloRequerimento,
    uriRequerimento. A conversão de idEvento para Int64 é feita via
    schema_overrides + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.EVENTOS_REQUERIMENTOS.value)


class CamaraVotacoesObjetosTransformer(BaseTransformer):
    """Transformer para o domínio votacoesObjetos (bulk-only yearly).

    O CSV bruto tem colunas: idVotacao, uriVotacao, data, descricao,
    proposicao_id, proposicao_uri, proposicao_ementa, proposicao_codTipo,
    proposicao_siglaTipo, proposicao_numero, proposicao_ano, proposicao_titulo.
    A conversão de tipos numéricos é feita via schema_overrides + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.VOTACOES_OBJETOS.value)


class CamaraVotacoesProposicoesTransformer(BaseTransformer):
    """Transformer para o domínio votacoesProposicoes (bulk-only yearly).

    O CSV bruto tem colunas: idVotacao, uriVotacao, data, descricao,
    proposicao_id, proposicao_uri, proposicao_titulo, proposicao_ementa,
    proposicao_codTipo, proposicao_siglaTipo, proposicao_numero, proposicao_ano.
    A conversão de tipos numéricos é feita via schema_overrides + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.VOTACOES_PROPOSICOES.value)


class CamaraFolhaPagamentoTransformer(BaseTransformer):
    """Transformer para o domínio folhaPagamento (bulk-only mensal, issue 04).

    O consolidado mensal da folha da Câmara é anônimo: valores por pessoa,
    sem nome/CPF/lotação. O CSV tem colunas com acento/espaços/parênteses
    (ex: "Remuneração Após Descontos Obrigatórios") que são normalizadas para
    snake_case via ``_FOLHA_COLUMN_MAP``, os valores em moeda BR ("1.234,56")
    são convertidos para ``Float64`` e o contrato SILVER_SCHEMAS é aplicado.

    ``Cargo = "Deputado {id}"`` (grupo "Parlamentar") é preservado intacto
    para permitir a atribuição downstream do subsídio ao ``id_deputado``.
    """

    # Colunas acentuadas do CSV → nomes normalizados (contrato Silver).
    _FOLHA_COLUMN_MAP = {
        "Cargo Individualizado do Servidor": "cargo",
        "Grupo Funcional": "grupo_funcional",
        "Folha de Pagamento": "folha",
        "Ano Ingresso": "ano_ingresso",
        "Remuneração Fixa": "remuneracao_fixa",
        "Vantagens de Natureza Pessoal": "vantagens_pessoais",
        "Função ou Cargo em Comissão": "funcao_comissao",
        "Gratificação Natalina": "gratificacao_natalina",
        "Férias (1/3 Constitucional)": "ferias",
        "Outras Remunerações Eventuais/Provisórias(*)": "outras_remuneracoes_eventuais",
        "Abono de Permanência": "abono_permanencia",
        "Redutor Constitucional": "redutor_constitucional",
        "Constribuição Previdenciária": "contribuicao_previdenciaria",
        "Imposto de Renda": "imposto_renda",
        "Remuneração Após Descontos Obrigatórios": "remuneracao_apos_descontos",
        "Diárias": "diarias",
        "Auxílios": "auxilios",
        "Vantagens Indenizatórias": "vantagens_indenizatorias",
    }

    # Colunas monetárias (formato BR) após a normalização de nomes.
    _FOLHA_MONEY_COLUMNS = (
        "remuneracao_fixa",
        "vantagens_pessoais",
        "funcao_comissao",
        "gratificacao_natalina",
        "ferias",
        "outras_remuneracoes_eventuais",
        "abono_permanencia",
        "redutor_constitucional",
        "contribuicao_previdenciaria",
        "imposto_renda",
        "remuneracao_apos_descontos",
        "diarias",
        "auxilios",
        "vantagens_indenizatorias",
    )

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        existing_map = {
            src: dst for src, dst in self._FOLHA_COLUMN_MAP.items() if src in df.columns
        }
        df = df.rename(existing_map)

        df = convert_br_currency_columns(df, columns=list(self._FOLHA_MONEY_COLUMNS))

        return _apply_contract(df, DomainType.FOLHA_PAGAMENTO.value)
