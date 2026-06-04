from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple

from ipolitico.core.constants import DomainType, LoadStrategy
from ipolitico.core.domain_spec import spec_for
from ipolitico.storage.state_store import StateStore

logger = logging.getLogger(__name__)


class WindowResolver:
    """Resolve janela orquestrada (incremental / full) a partir do estado persistido."""

    def __init__(self, state_store: StateStore) -> None:
        self._store = state_store

    @staticmethod
    def watermark_column(domain: DomainType) -> Optional[str]:
        spec = spec_for(domain)
        if spec and spec.watermark_column:
            return spec.watermark_column
        return None

    def resolve(
        self,
        domain: DomainType,
        strategy: LoadStrategy,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[str, str]:
        actual_end = end_date or datetime.now().strftime("%Y-%m-%d")
        spec = spec_for(domain)
        earliest_possible = spec.earliest_iso if spec else "1826-04-29"

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
