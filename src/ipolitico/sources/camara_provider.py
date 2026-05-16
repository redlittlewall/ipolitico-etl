from typing import Any, Protocol, runtime_checkable

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType


@runtime_checkable
class SourceProvider(Protocol):
    name: str

    async def run_domains(
        self,
        domains: list[DomainType],
        strategy: LoadStrategy,
        sink_type: SinkType,
        start_date: str | None,
        end_date: str | None,
    ) -> None: ...


class CamaraSourceProvider:
    """Adapter que executa o pipeline Câmara existente."""

    name = "camara"

    def __init__(self, pipeline_manager: Any) -> None:
        self._manager = pipeline_manager

    async def run_domains(
        self,
        domains: list[DomainType],
        strategy: LoadStrategy,
        sink_type: SinkType,
        start_date: str | None,
        end_date: str | None,
    ) -> None:
        for domain in domains:
            await self._manager.run_domain(
                domain=domain,
                sink_type=sink_type,
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
            )
