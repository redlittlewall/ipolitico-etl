"""Adapter de federação para a API administrativa do Senado (adm-dadosabertos).

Registra o provider ``senado-adm`` no ``FederationOrchestrator``. Diferente
dos providers Câmara/Senado — que encaminham todos os domínios e dependem do
manager para ignorar os não configurados — este provider filtra os domínios
para os que o manager conhece (``domain_configs`` do YAML). Assim, com a
config vazia desta fatia, ``--source all`` não gera erros ruidosos: o provider
é inerte até as fatias 07-09 registrarem os domínios no YAML.
"""

from typing import Any

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType


class SenadoAdmSourceProvider:
    """Adapter que executa o pipeline adm-dadosabertos do Senado."""

    name = "senado-adm"

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
            ``domain_configs`` da config do manager; lista vazia quando a
            config ainda não registra domínios (fatia 06).
        """
        config = getattr(self._manager, "config", {}) or {}
        known = set(config.get("domain_configs", {}))
        return [d for d in domains if d.value in known]
