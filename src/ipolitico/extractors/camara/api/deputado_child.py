"""Extratores de rotas filhas de /deputados/{id}/<suffix> (profissões, ocupações)."""

from __future__ import annotations

from typing import Any, Optional

import polars as pl

from ipolitico.extractors.camara.api.deputados import DeputadosExtractor


class DeputadoChildRouteExtractor(DeputadosExtractor):
    """Extrai uma rota estática por deputado (profissoes, ocupacoes, ...)."""

    route_suffix: str = ""

    async def extract(self, deputado_id: Optional[int] = None, **kwargs: Any) -> pl.DataFrame:
        if deputado_id is None:
            return pl.DataFrame()

        df = await self.extract_child_route(int(deputado_id), self.route_suffix)
        if df.is_empty():
            return df
        return df.with_columns(pl.lit(int(deputado_id)).alias("id_deputado"))


class ProfissoesExtractor(DeputadoChildRouteExtractor):
    route_suffix = "profissoes"


class OcupacoesExtractor(DeputadoChildRouteExtractor):
    route_suffix = "ocupacoes"


class DeputadoTemporalChildExtractor(DeputadosExtractor):
    """Rotas paginadas por deputado e janela (discursos, orgaos, ...)."""

    route_suffix: str = ""

    async def extract(
        self,
        deputado_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        if deputado_id is None or not start_date or not end_date:
            return pl.DataFrame()

        df = await self.extract_temporal_route(
            int(deputado_id), self.route_suffix, start_date, end_date
        )
        if df.is_empty():
            return df
        return df.with_columns(pl.lit(int(deputado_id)).alias("id_deputado"))


class DiscursosExtractor(DeputadoTemporalChildExtractor):
    route_suffix = "discursos"
