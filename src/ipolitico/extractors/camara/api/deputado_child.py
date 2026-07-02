"""Extratores de rotas filhas de /deputados/{id}/<suffix> (profissões, ocupações)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import polars as pl

from ipolitico.extractors.camara.api.deputados import DeputadosExtractor

# A API da Câmara rejeita janelas temporais maiores que 4 anos
# (HTTP 400: "data de início não pode ser maior que 4 anos").
_MAX_TEMPORAL_WINDOW_DAYS = 365 * 4  # ~4 anos


class DeputadoChildRouteExtractor(DeputadosExtractor):
    """Extrai uma rota estática por deputado (profissoes, ocupacoes, ...)."""

    route_suffix: str = ""

    async def extract(self, deputado_id: Optional[int] = None, **kwargs: Any) -> pl.DataFrame:
        if deputado_id is None:
            return pl.DataFrame()

        df = await self.extract_child_route(int(deputado_id), self.route_suffix)
        if df.is_empty():
            return df
        df = df.with_columns(pl.lit(int(deputado_id)).alias("id_deputado"))
        endpoint = f"deputados/{int(deputado_id)}/{self.route_suffix}"
        return self._inject_source_url(df, endpoint)


class ProfissoesExtractor(DeputadoChildRouteExtractor):
    route_suffix = "profissoes"


class OcupacoesExtractor(DeputadoChildRouteExtractor):
    route_suffix = "ocupacoes"


def _chunk_date_range(start_iso: str, end_iso: str) -> list[tuple[str, str]]:
    """Quebra uma janela ISO em pedaços de no máximo ``_MAX_TEMPORAL_WINDOW_DAYS``.

    A API da Câmara rejeita janelas > 4 anos para rotas temporais
    (discursos, orgaos, eventos). Esta função particiona a janela
    em fatias menores que cabem no limite da API.

    Args:
        start_iso: Data inicial ISO (YYYY-MM-DD).
        end_iso: Data final ISO (YYYY-MM-DD).

    Returns:
        Lista de tuplas (chunk_start, chunk_end) cada uma dentro do limite.
    """
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    delta = (end - start).days
    if delta <= _MAX_TEMPORAL_WINDOW_DAYS:
        return [(start_iso, end_iso)]

    chunks: list[tuple[str, str]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=_MAX_TEMPORAL_WINDOW_DAYS), end)
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return chunks


class DeputadoTemporalChildExtractor(DeputadosExtractor):
    """Rotas paginadas por deputado e janela (discursos, orgaos, ...).

    A janela temporal completa é automaticamente particionada em chunks
    de no máximo 4 anos para respeitar o limite da API da Câmara.
    Resultados parciais são concatenados em um único DataFrame.
    """

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

        chunks = _chunk_date_range(start_date, end_date)
        frames: list[pl.DataFrame] = []
        for chunk_start, chunk_end in chunks:
            df = await self.extract_temporal_route(
                int(deputado_id), self.route_suffix, chunk_start, chunk_end
            )
            if not df.is_empty():
                frames.append(df)

        if not frames:
            return pl.DataFrame()

        result = pl.concat(frames)
        result = result.with_columns(pl.lit(int(deputado_id)).alias("id_deputado"))
        endpoint = f"deputados/{int(deputado_id)}/{self.route_suffix}"
        params = {"dataInicio": start_date, "dataFim": end_date}
        return self._inject_source_url(result, endpoint, params=params)


class DiscursosExtractor(DeputadoTemporalChildExtractor):
    route_suffix = "discursos"


class FrentesDeputadoExtractor(DeputadoChildRouteExtractor):
    route_suffix = "frentes"


class HistoricoDeputadoExtractor(DeputadoChildRouteExtractor):
    route_suffix = "historico"


class OrgaosDeputadoExtractor(DeputadoTemporalChildExtractor):
    route_suffix = "orgaos"


class EventosDeputadoExtractor(DeputadoTemporalChildExtractor):
    route_suffix = "eventos"


class MandatosExternosExtractor(DeputadoChildRouteExtractor):
    route_suffix = "mandatosExternos"
