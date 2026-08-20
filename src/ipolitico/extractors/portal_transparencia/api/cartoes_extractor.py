"""Extrator do domínio cg_cartoes — cartões de pagamento (API v3, rota pontual).

ROTA DUPLA (exigência explícita do ticket 04): em FULL_LOAD o histórico vem do
bulk mensal (cpgf/cpcc/cpdc); em INCREMENTAL a janela curta (≤12 meses) é
atendida pela consulta pontual da API v3 ``/api-de-dados/cartoes``. A API exige
≥1 filtro — o período ``mesExtratoInicio``/``mesExtratoFim`` (máximo 12 meses)
é o natural para a janela: o extrator consulta em BLOCOS MENSAIS (1 mês ≤ 12),
alinhados aos jobs ``{"year", "month"}`` do ``MonthlyBulkStrategy``.

Sem janela (year/month ausentes), levanta ``ValueError``: chamar a API sem
filtro responde 400 real ("Ao menos um filtro deve ser preenchido") — o erro
antecipa a falha em vez de paginá-la. O construtor aceita ``modules`` (kwarg
compartilhado do YAML com o extrator bulk — ignorado aqui).
"""

from __future__ import annotations

from typing import Any, Optional

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalCartoesApiExtractor(PortalTransparenciaBaseExtractor):
    """
    Extrator de cartões de pagamento (API v3, consulta pontual por bloco mensal).

    Monta o filtro ``mesExtratoInicio``/``mesExtratoFim`` do mês (mesmo mês —
    1 mês ≤ 12 ✓) a partir do job ``{"year", "month"}`` e página
    ``api-de-dados/cartoes`` até esgotar, injetando ``_source_url`` por página
    (``...?mesExtratoInicio=MM/AAAA&mesExtratoFim=MM/AAAA&pagina=N``). Devolve o
    raw como veio da API (``tipoCartao`` int, ``valorTransacao`` string
    vírgula-decimal, ``mesExtrato`` "MM/AAAA", ``dataTransacao`` "DD/MM/AAAA" —
    a normalização/tipagem vive no transformer), sem regras de negócio.
    """

    ENDPOINT = "api-de-dados/cartoes"

    def __init__(self, client: Any, modules: Optional[list[str]] = None):
        """
        Inicializa o extrator de cartões da API v3.

        Args:
            client: Cliente HTTP já configurado com a chave do usuário.
            modules: Lista de módulos bulk (``["cpgf", "cpcc", "cpdc"]`` do
                YAML) — kwarg COMPARTILHADO com o ``PortalCartoesBulkExtractor``;
                ignorado na rota API (o filtro é o período, não o módulo).
        """
        super().__init__(client)

    async def extract(
        self, year: int | None = None, month: int | None = None, **kwargs: Any
    ) -> pl.DataFrame:
        """
        Extrai as transações de cartão de um mês (bloco mensal ≤ 12 meses).

        Args:
            year: Ano do mês da consulta (ex: 2026).
            month: Mês 1-12 da consulta (ex: 6 → ``mesExtrato`` "06/2026").
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com as colunas do DTO de cartões e ``_source_url``
            por linha apontando para a página de origem (com o filtro de mês no
            query string). DataFrame vazio se a API não tiver transações no mês.

        Raises:
            ValueError: Se ``year`` ou ``month`` ausentes — a API exige ≥1
                filtro (período ``mesExtratoInicio/Fim`` ≤ 12 meses) e chamá-la
                sem filtro responde 400 real.
        """
        if year is None or month is None:
            raise ValueError(
                "PortalCartoesApiExtractor exige year e month (bloco mensal): a API "
                "v3 /cartoes responde 400 sem ao menos um filtro (período "
                "mesExtratoInicio/mesExtratoFim ≤ 12 meses)."
            )
        mes = f"{month:02d}/{year}"
        params = {"mesExtratoInicio": mes, "mesExtratoFim": mes}
        data = await self.fetch_paginated(self.ENDPOINT, params=params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=params)
