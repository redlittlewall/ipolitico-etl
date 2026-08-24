"""Extrator do domínio cg_convenios — Convênios e Transferências Voluntárias (API v3).

Página o recurso ``api-de-dados/convenios`` via ``PortalTransparenciaBaseExtractor``.
Suporta parâmetros opcionais (``codigoOrgao``, ``uf``, ``dataInicial``, ``dataFinal``,
``convenente``, ``numero``, etc.) ou walk livre por página. Devolve o raw da API
com ``_source_url`` injetado por página para auditoria replayável.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalConveniosApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator de convênios federais via API v3."""

    ENDPOINT = "api-de-dados/convenios"

    async def extract(
        self,
        codigoOrgao: str | None = None,
        uf: str | None = None,
        dataInicial: str | None = None,
        dataFinal: str | None = None,
        convenente: str | None = None,
        numero: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai convênios com filtros opcionais.

        Args:
            codigoOrgao: Código SIAFI do órgão concedente (opcional).
            uf: Sigla da UF do convenente (opcional).
            dataInicial: Data de referência/início em DD/MM/AAAA (opcional).
            dataFinal: Data de referência/fim em DD/MM/AAAA (opcional).
            convenente: Nome ou CNPJ do convenente (opcional).
            numero: Número do convênio (opcional).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        params: dict[str, Any] = {}
        if codigoOrgao:
            params["codigoOrgao"] = codigoOrgao
        if uf:
            params["uf"] = uf
        if convenente:
            params["convenente"] = convenente
        if numero:
            params["numero"] = numero

        dt_ini = dataInicial or (kwargs.get("start_date") if kwargs.get("start_date") != "1826-04-29" else None)
        if dt_ini:
            if "-" in str(dt_ini):
                parts = str(dt_ini).split("-")
                dt_ini = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else dt_ini
            params["dataInicial"] = dt_ini

        dt_fim = dataFinal or (kwargs.get("end_date") if kwargs.get("start_date") != "1826-04-29" else None)
        if dt_fim and dt_ini:
            if "-" in str(dt_fim):
                parts = str(dt_fim).split("-")
                dt_fim = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else dt_fim
            params["dataFinal"] = dt_fim

        # Se nenhum filtro for fornecido, a API v3 exige período de até 1 mês ou órgão/UF.
        # Usa codigoOrgao=26000 como default seguro para chamadas abertas de snapshot.
        if not params:
            params["codigoOrgao"] = "26000"

        data = await self.fetch_paginated(self.ENDPOINT, params=params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=params)
