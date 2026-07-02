"""Extratores para os 3 domínios de plenário do Senado.

Endpoints:
- ``/plenario/agenda/dia/{data}`` → PLENARIO_AGENDA
- ``/plenario/resultado/{data}`` → PLENARIO_RESULTADOS
- ``/plenario/legislatura/{data}`` → PLENARIO_SESSOES

Nota: A API do Senado espera datas no formato ``YYYYMMDD`` (sem hífens)
no path da URL. Cada extrator aceita ``YYYY-MM-DD`` (ISO) como entrada
e converte internamente.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class PlenarioAgendaExtractor(SenadoBaseExtractor):
    """Extrator da agenda do dia no plenário do Senado.

    Chama ``GET /plenario/agenda/dia/{data}`` e achata o envelope XML-heritage
    ``AgendaPlenario.Sessoes.Sessao``. Serializa structs aninhadas (Oradores,
    Evento) como JSON string.

    Nota: Aceita data no formato ``YYYY-MM-DD`` (ISO) e converte internamente
    para ``YYYYMMDD`` no path da URL (exigência da API do Senado).
    """

    async def extract(
        self,
        data: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai a agenda do plenário para uma data específica.

        Args:
            data: Data no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (aceita ``data`` via kwargs).

        Returns:
            DataFrame com os dados brutos da agenda (CodigoSessao, Data,
            Hora, etc.) com structs serializadas como JSON string,
            ou DataFrame vazio se a API não retornar dados.
        """
        dt = data or kwargs.get("data")
        if dt is None:
            return pl.DataFrame()

        # API do Senado espera YYYYMMDD no path da URL (sem hífens)
        url_dt = dt.replace("-", "")
        raw = await self.fetch_flat(f"plenario/agenda/dia/{url_dt}")
        records = self.flatten_response(raw, ["AgendaPlenario", "Sessoes", "Sessao"])

        if not records:
            return pl.DataFrame()

        # Serializa structs aninhadas como JSON string
        for record in records:
            for key in ("Oradores", "Evento"):
                val = record.get(key)
                if isinstance(val, (dict, list)):
                    record[key] = json.dumps(val, ensure_ascii=False)

        return pl.DataFrame(records, infer_schema_length=None)


class PlenarioResultadosExtractor(SenadoBaseExtractor):
    """Extrator de resultados de votações em plenário.

    Chama ``GET /plenario/resultado/{data}`` e achata o envelope XML-heritage
    ``ResultadoPlenario.Sessoes.Sessao``. Para cada sessão, mescla metadados
    da sessão (codigoSessao, dataSessao, siglaCasa) nos itens de pauta
    (``Itens.Item[]``).

    Nota: Aceita data no formato ``YYYY-MM-DD`` (ISO) e converte internamente
    para ``YYYYMMDD`` no path da URL (exigência da API do Senado).
    """

    async def extract(
        self,
        data: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai os resultados de votações para uma data específica.

        Args:
            data: Data no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (aceita ``data`` via kwargs).

        Returns:
            DataFrame com os itens de pauta votados, cada um com metadados
            da sessão (codigoSessao, dataSessao, siglaCasa) anexados,
            ou DataFrame vazio se a API não retornar dados.
        """
        dt = data or kwargs.get("data")
        if dt is None:
            return pl.DataFrame()

        # API do Senado espera YYYYMMDD no path da URL (sem hífens)
        url_dt = dt.replace("-", "")
        raw = await self.fetch_flat(f"plenario/resultado/{url_dt}")
        sessoes = self.flatten_response(raw, ["ResultadoPlenario", "Sessoes", "Sessao"])

        if not sessoes:
            return pl.DataFrame()

        all_items: list[dict[str, Any]] = []
        for sessao in sessoes:
            itens = sessao.get("Itens")
            if not isinstance(itens, dict):
                continue
            item_list = itens.get("Item")
            if not isinstance(item_list, list) or not item_list:
                continue

            for item in item_list:
                item["codigoSessao"] = sessao.get("codigoSessao")
                item["dataSessao"] = sessao.get("dataSessao")
                item["siglaCasa"] = sessao.get("siglaCasa")
                all_items.append(item)

        if not all_items:
            return pl.DataFrame()

        return pl.DataFrame(all_items, infer_schema_length=None)


class PlenarioSessoesExtractor(SenadoBaseExtractor):
    """Extrator de sessões legislativas do Senado.

    Chama ``GET /plenario/legislatura/{data}`` e achata o envelope XML-heritage
    ``ListaLegislatura.Legislaturas.Legislatura``. Para cada legislatura, acessa
    ``SessoesLegislativas.SessaoLegislativa[]`` e mescla dados da legislatura
    (NumeroLegislatura, DataEleicao, DataInicio, DataFim) em cada sessão.

    Nota: Aceita data no formato ``YYYY-MM-DD`` (ISO) e converte internamente
    para ``YYYYMMDD`` no path da URL (exigência da API do Senado).
    """

    async def extract(
        self,
        data: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai as sessões legislativas da legislatura vigente na data.

        Args:
            data: Data no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (aceita ``data`` via kwargs).

        Returns:
            DataFrame com as sessões legislativas encontradas, cada uma com
            metadados da legislatura (NumeroLegislatura, DataEleicao,
            DataInicio, DataFim) anexados,
            ou DataFrame vazio se a API não retornar dados.
        """
        dt = data or kwargs.get("data")
        if dt is None:
            return pl.DataFrame()

        # API do Senado espera YYYYMMDD no path da URL (sem hífens)
        url_dt = dt.replace("-", "")
        raw = await self.fetch_flat(f"plenario/legislatura/{url_dt}")
        legislaturas = self.flatten_response(
            raw, ["ListaLegislatura", "Legislaturas", "Legislatura"]
        )

        if not legislaturas:
            return pl.DataFrame()

        all_sessoes: list[dict[str, Any]] = []
        for leg in legislaturas:
            sessoes_data = leg.get("SessoesLegislativas", {})
            sessoes_list = sessoes_data.get("SessaoLegislativa", [])
            if not isinstance(sessoes_list, list) or not sessoes_list:
                continue

            for sessao in sessoes_list:
                sessao["NumeroLegislatura"] = leg.get("NumeroLegislatura")
                sessao["DataEleicao"] = leg.get("DataEleicao")
                sessao["DataInicioLegislatura"] = leg.get("DataInicio")
                sessao["DataFimLegislatura"] = leg.get("DataFim")
                all_sessoes.append(sessao)

        if not all_sessoes:
            return pl.DataFrame()

        return pl.DataFrame(all_sessoes, infer_schema_length=None)
