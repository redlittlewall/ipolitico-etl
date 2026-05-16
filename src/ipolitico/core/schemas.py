import polars as pl

from ipolitico.core.constants import ApiParams, DomainType

DESPESAS_PARTITION_KEYS = (
    ApiParams.DEPUTADO_ID.value,
    "numDocumento",
    "codDocumento",
    "parcela",
    "valorLiquido",
)


def despesas_optimizer_partition_sql() -> str:
    """Colunas PARTITION BY compatíveis com DuckDB (dedup Gold)."""
    return ", ".join(DESPESAS_PARTITION_KEYS)


SILVER_SCHEMAS = {
    DomainType.DEPUTADOS.value: {
        "id": pl.Int64,
        "nome": pl.String,
        "partido": pl.String,
        "uf": pl.String,
        "idLegislatura": pl.Int64,
        "url_foto": pl.String,
        "email": pl.String,
    },
    DomainType.DESPESAS.value: {
        "id_deputado": pl.Int64,
        "ano": pl.Int64,
        "mes": pl.Int64,
        "tipoDespesa": pl.String,
        "codDocumento": pl.Int64,
        "tipoDocumento": pl.String,
        "dataDocumento": pl.String,
        "numDocumento": pl.String,
        "parcela": pl.Int64,
        "valorDocumento": pl.Float64,
        "valorGlosa": pl.Float64,
        "valorLiquido": pl.Float64,
        "nomeFornecedor": pl.String,
        "cnpjCpfFornecedor": pl.String,
        "urlDocumento": pl.String,
    },
    DomainType.PROPOSICOES.value: {
        "id": pl.Int64,
        "uri": pl.String,
        "siglaTipo": pl.String,
        "numero": pl.Int64,
        "ano": pl.Int64,
        "ementa": pl.String,
        "dataApresentacao": pl.Datetime,
        "uriOrgaoNumerador": pl.String,
    },
    DomainType.VOTACOES.value: {
        "id": pl.String,
        "uri": pl.String,
        "data": pl.Datetime,
        "dataHoraRegistro": pl.Datetime,
        "siglaOrgao": pl.String,
        "uriOrgao": pl.String,
        "uriEvento": pl.String,
        "proposicaoObjeto": pl.String,
        "descricao": pl.String,
        "aprovacao": pl.Int64,
    },
    DomainType.VOTOS.value: {
        "tipoVoto": pl.String,
        "dataRegistroVoto": pl.String,
        ApiParams.DEPUTADO_ID.value: pl.Int64,
        "partido": pl.String,
        "uf": pl.String,
        "votacao_id": pl.String,
    },
}
