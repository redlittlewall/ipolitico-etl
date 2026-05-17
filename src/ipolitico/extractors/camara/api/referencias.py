"""Catálogos estáticos em /referencias/*."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)

# Rotas de referência mais usadas em joins e validação de códigos.
REFERENCE_ROUTES: tuple[str, ...] = (
    "referencias/uf",
    "referencias/deputados/siglaUF",
    "referencias/deputados/tipoDespesa",
    "referencias/proposicoes/siglaTipo",
    "referencias/proposicoes/codTema",
    "referencias/proposicoes/codTipoAutor",
    "referencias/proposicoes/codTipoTramitacao",
    "referencias/orgaos/codTipoOrgao",
    "referencias/eventos/codTipoEvento",
    "referencias/situacoesDeputado",
    "referencias/situacoesProposicao",
    "referencias/tiposProposicao",
    "referencias/tiposTramitacao",
)


class ReferenciasExtractor(CamaraBaseExtractor):
    async def extract(self, routes: list[str] | None = None, **kwargs: Any) -> pl.DataFrame:
        paths = routes or list(REFERENCE_ROUTES)
        rows: list[dict] = []

        for path in paths:
            try:
                data = await self.fetch_paginated(path, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "referencia": path})
            except Exception as e:
                logger.error("Erro em referência %s: %s", path, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
