import asyncio
from typing import Iterable

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.sources.camara_provider import SourceProvider


class FederationOrchestrator:
    """Orquestra múltiplos `SourceProvider` (ex.: Câmara + Senado) em paralelo."""

    def __init__(self, providers: Iterable[SourceProvider]) -> None:
        self._providers = list(providers)

    async def run_all(
        self,
        domains: list[DomainType],
        strategy: LoadStrategy,
        sink_type: SinkType,
        start_date: str | None,
        end_date: str | None,
        warmup: bool = True,
    ) -> None:
        if not self._providers:
            return
        await asyncio.gather(
            *(
                p.run_domains(domains, strategy, sink_type, start_date, end_date, warmup=warmup)
                for p in self._providers
            )
        )
