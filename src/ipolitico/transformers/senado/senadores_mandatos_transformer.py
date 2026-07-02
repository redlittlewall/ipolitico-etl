"""Transformador para o domínio SENADORES_MANDATOS — aplaina mandatos de senador."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class SenadoMandatosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de mandatos de senadores.

    O DataFrame de entrada contém colunas no formato camelCase da API
    (ex: ``CodigoMandato``, ``UfParlamentar``) com estruturas aninhadas:

    - ``PrimeiraLegislaturaDoMandato`` / ``SegundaLegislaturaDoMandato``:
      structs com ``NumeroLegislatura``, ``DataInicio``, ``DataFim``
    - ``Partidos``: struct com ``Partido`` (array de structs com ``Sigla``,
      ``DataFiliacao``, ``DataDesfiliacao``)

    O transformer achata structs (com sufixos para evitar colisão de nomes)
    e extrai ``sigla_partido`` do primeiro partido da lista.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma dados brutos de mandatos para o formato Silver.

        Args:
            df: DataFrame com colunas no formato camelCase da API.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme o contrato
            Silver, ou DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.SENADORES_MANDATOS.value]

        # 1. Aplaina structs de legislatura com sufixo para evitar colisão
        if "PrimeiraLegislaturaDoMandato" in df.columns:
            df = df.with_columns(
                pl.col("PrimeiraLegislaturaDoMandato")
                .struct.field("NumeroLegislatura")
                .alias("_primeira_leg"),
                pl.col("PrimeiraLegislaturaDoMandato")
                .struct.field("DataInicio")
                .alias("_data_inicio"),
                pl.col("PrimeiraLegislaturaDoMandato").struct.field("DataFim").alias("_data_fim"),
            )
        if "SegundaLegislaturaDoMandato" in df.columns:
            df = df.with_columns(
                pl.col("SegundaLegislaturaDoMandato")
                .struct.field("NumeroLegislatura")
                .alias("_segunda_leg"),
            )

        # 2. Extrai sigla do partido (primeiro da lista, se houver)
        if "Partidos" in df.columns:
            _partido_col = pl.col("Partidos").struct.field("Partido")
            # XML-heritage: 1 partido → struct, 2+ → list. Tenta ambos.
            try:
                _sigla = _partido_col.list.get(0).struct.field("Sigla")
            except (pl.exceptions.ColumnNotFoundError, TypeError):
                _sigla = _partido_col.struct.field("Sigla")
            df = df.with_columns(
                pl.when(pl.col("Partidos").is_not_null())
                .then(_sigla)
                .otherwise(pl.lit(None))
                .alias("_sigla_partido")
            )

        # 3. Mapeamento direto: colunas flat da API → Silver
        mappings: list[tuple[str, str, type[pl.DataType]]] = [
            ("CodigoParlamentar", "codigo", pl.Int64),
            ("CodigoMandato", "codigo_mandato", pl.Int64),
            ("UfParlamentar", "uf", pl.String),
            ("DescricaoParticipacao", "descricao_participacao", pl.String),
            ("_primeira_leg", "primeira_legislatura", pl.Int64),
            ("_segunda_leg", "segunda_legislatura", pl.Int64),
            ("_sigla_partido", "sigla_partido", pl.String),
            ("_data_inicio", "data_inicio", pl.String),
            ("_data_fim", "data_fim", pl.String),
        ]

        for api_name, silver_col, dtype in mappings:
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                expr = pl.col(api_name)
                if dtype == pl.Int64:
                    expr = expr.cast(pl.Int64)
                df = df.with_columns(expr.alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # 4. Preenche colunas faltantes no contrato
        for col in contract:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
