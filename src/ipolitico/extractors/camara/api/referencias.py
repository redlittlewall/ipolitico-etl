"""Catálogos estáticos em /referencias/*."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)

# Catálogos /referencias/* documentados no Swagger da Câmara.
REFERENCE_ROUTES: tuple[str, ...] = (
    "referencias/uf",
    "referencias/deputados",
    "referencias/deputados/codSituacao",
    "referencias/deputados/codTipoProfissao",
    "referencias/deputados/siglaUF",
    "referencias/deputados/tipoDespesa",
    "referencias/eventos",
    "referencias/eventos/codSituacaoEvento",
    "referencias/eventos/codTipoEvento",
    "referencias/orgaos",
    "referencias/orgaos/codSituacao",
    "referencias/orgaos/codTipoOrgao",
    "referencias/proposicoes",
    "referencias/proposicoes/codSituacao",
    "referencias/proposicoes/codTema",
    "referencias/proposicoes/codTipoAutor",
    "referencias/proposicoes/codTipoTramitacao",
    "referencias/proposicoes/siglaTipo",
    "referencias/situacoesDeputado",
    "referencias/situacoesEvento",
    "referencias/situacoesOrgao",
    "referencias/situacoesProposicao",
    "referencias/tiposAutor",
    "referencias/tiposEvento",
    "referencias/tiposOrgao",
    "referencias/tiposProposicao",
    "referencias/tiposTramitacao",
)


class ReferenciasExtractor(CamaraBaseExtractor):
    async def extract(self, routes: list[str] | None = None, **kwargs: Any) -> pl.DataFrame:
        paths = routes or list(REFERENCE_ROUTES)
        rows: list[dict] = []

        for path in paths:
            try:
                data = await self.fetch_unpaginated(path, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "referencia": path})
            except Exception as e:
                logger.warning("Erro em referência %s: %s", path, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
