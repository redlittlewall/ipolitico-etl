from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple

from ipolitico.core.constants import EARLIEST_DATE_MAP, DomainType, LoadStrategy
from ipolitico.sinks.base import BaseSink

logger = logging.getLogger(__name__)


class WindowResolver:
    """Resolve janela orquestrada (incremental / full) a partir do estado persistido."""

    def __init__(self, state_store: BaseSink) -> None:
        self._store = state_store

    @staticmethod
    def watermark_column(domain: DomainType) -> Optional[str]:
        mapping = {
            DomainType.DESPESAS: "dataDocumento",
            DomainType.PROPOSICOES: "dataApresentacao",
            DomainType.VOTACOES: "data",
        }
        return mapping.get(domain)

    def resolve(
        self,
        domain: DomainType,
        strategy: LoadStrategy,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[str, str]:
        actual_end = end_date or datetime.now().strftime("%Y-%m-%d")
        earliest_possible = EARLIEST_DATE_MAP.get(domain, "1826-04-29")

        if start_date:
            actual_start = max(start_date, earliest_possible)
            if start_date != actual_start:
                logger.warning(
                    f"[{domain.value.upper()}] A data {start_date} é anterior à existência "
                    f"destes dados. Ajustando limite inicial para {actual_start}."
                )
            return actual_start, actual_end

        if strategy == LoadStrategy.FULL_LOAD:
            actual_start = earliest_possible
            logger.info(
                f"[{domain.value.upper()}] Estratégia FULL LOAD."
                f" Iniciando extração desde a origem segura: {actual_start}."
            )
            return actual_start, actual_end

        watermark_col = self.watermark_column(domain)
        if not watermark_col:
            logger.info(
                f"[{domain.value.upper()}] Entidade dimensional detectada."
                " Assumindo janela completa para atualização (UPSERT)."
            )
            return earliest_possible, actual_end

        watermark = self._store.get_watermark(domain.value, watermark_col)

        if watermark:
            raw_watermark = str(watermark).split("T")[0]
            actual_start = max(raw_watermark, earliest_possible)
            logger.info(
                f"[{domain.value.upper()}] Estratégia INCREMENTAL."
                f" Retomando da marca d'água: {actual_start}."
            )
        else:
            actual_start = earliest_possible
            logger.info(
                f"[{domain.value.upper()}] Tabela sem histórico."
                f" Iniciando carga a partir de {actual_start}."
            )

        return actual_start, actual_end
