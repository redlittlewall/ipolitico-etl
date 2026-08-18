from typing import Any

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType


class SenadoSourceProvider:
    """Adapter que executa o pipeline Senado existente."""

    name = "senado"

    def __init__(self, pipeline_manager: Any) -> None:
        self._manager = pipeline_manager

    async def run_domains(
        self,
        domains: list[DomainType],
        strategy: LoadStrategy,
        sink_type: SinkType,
        start_date: str | None,
        end_date: str | None,
        warmup: bool = True,
    ) -> None:
        # Filtra pelos domínios que este manager conhece no YAML: sem isso,
        # --source all encaminha domínios de outras fontes ao manager, que
        # registra logger.error ("Configuração não encontrada no YAML") para
        # cada um — ruído que poluía o log sem afetar a execução.
        for domain in self._owned_domains(domains):
            await self._manager.run_domain(
                domain=domain,
                sink_type=sink_type,
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                warmup=warmup,
            )

    def _owned_domains(self, domains: list[DomainType]) -> list[DomainType]:
        """Filtra os domínios que o manager desta fonte conhece na config.

        Args:
            domains: Domínios solicitados na execução (todas as fontes).

        Returns:
            Subconjunto de ``domains`` cujo valor está presente em
            ``domain_configs`` da config do manager.
        """
        config = self._manager.config or {}
        known = set(config.get("domain_configs", {}))
        return [d for d in domains if d.value in known]
