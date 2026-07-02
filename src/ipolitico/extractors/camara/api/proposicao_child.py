"""Rotas filhas de /proposicoes/{id}/<suffix> (tramitações, autores)."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class ProposicaoChildRouteExtractor(CamaraBaseExtractor):
    """Extrator base para rotas filhas de /proposicoes/{id}/<suffix>.

    Percorre a lista de IDs de proposições fornecida e coleta os dados
    da rota filha para cada uma, adicionando colunas de auditoria
    (``id_proposicao`` e ``_source_url``).
    """

    route_suffix: str = ""

    async def extract(self, proposicao_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai dados da rota filha para cada proposição informada.

        Args:
            proposicao_ids: Lista de IDs das proposições a consultar.

        Returns:
            pl.DataFrame: DataFrame com os dados brutos acrescidos de
                          ``id_proposicao`` e ``_source_url``, ou vazio
                          se não houver IDs ou dados.
        """
        if not proposicao_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for pid in proposicao_ids:
            endpoint = f"{ApiRoutes.PROPOSICOES.value}/{pid}/{self.route_suffix}"
            url = self.build_source_url(endpoint)
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                if not data:
                    continue
                for item in data:
                    if isinstance(item, dict):
                        rows.append(
                            {
                                **item,
                                "id_proposicao": int(pid),
                                "_source_url": url,
                            }
                        )
            except Exception as e:
                logger.warning("Erro em %s para proposição %s: %s", self.route_suffix, pid, e)

        if not rows:
            return pl.DataFrame()
        df = pl.DataFrame(rows, infer_schema_length=None)
        return df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])


class TramitacoesExtractor(ProposicaoChildRouteExtractor):
    """Rota /proposicoes/{id}/tramitacoes."""

    route_suffix = "tramitacoes"


class AutoresExtractor(ProposicaoChildRouteExtractor):
    """Rota /proposicoes/{id}/autores."""

    route_suffix = "autores"


class RelacionadasExtractor(ProposicaoChildRouteExtractor):
    """Rota /proposicoes/{id}/relacionadas."""

    route_suffix = "relacionadas"


class TemasExtractor(ProposicaoChildRouteExtractor):
    """Rota /proposicoes/{id}/temas."""

    route_suffix = "temas"


class ProposicoesVotacoesExtractor(ProposicaoChildRouteExtractor):
    """Rota /proposicoes/{id}/votacoes."""

    route_suffix = "votacoes"
