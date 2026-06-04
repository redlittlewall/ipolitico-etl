from __future__ import annotations

from typing import TYPE_CHECKING

from ipolitico.core.constants import DomainType, SourceType
from ipolitico.extractors.base import BaseExtractor

if TYPE_CHECKING:
    from ipolitico.core.client import CamaraClient


class CamaraExtractorFactory:
    """
    Resolve extrator API vs Bulk conforme DomainType + SourceType.
    Mantém assinatura compatível com a suíte de testes em test_factory.py.
    """

    _API: dict[str, type[BaseExtractor]] = {}
    _BULK: dict[str, type[BaseExtractor]] = {}

    @classmethod
    def _load_maps(cls) -> None:
        if cls._API:
            return
        from ipolitico.extractors.camara.api.deputados import DeputadosExtractor
        from ipolitico.extractors.camara.api.despesas import DespesasExtractor
        from ipolitico.extractors.camara.api.proposicoes import ProposicoesExtractor
        from ipolitico.extractors.camara.api.votacoes import VotacoesExtractor
        from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor

        cls._API = {
            DomainType.DEPUTADOS.value: DeputadosExtractor,
            DomainType.DESPESAS.value: DespesasExtractor,
            DomainType.PROPOSICOES.value: ProposicoesExtractor,
            DomainType.VOTACOES.value: VotacoesExtractor,
        }
        cls._BULK = {
            DomainType.DEPUTADOS.value: BaseBulkExtractor,
            DomainType.DESPESAS.value: BaseBulkExtractor,
            DomainType.PROPOSICOES.value: BaseBulkExtractor,
            DomainType.VOTACOES.value: BaseBulkExtractor,
            DomainType.VOTOS.value: BaseBulkExtractor,
        }

    @classmethod
    def get_extractor(
        cls,
        domain,
        source,
        client: CamaraClient,
        state_store=None,
    ) -> BaseExtractor:
        cls._load_maps()
        dval = getattr(domain, "value", domain)
        sval = getattr(source, "value", source)

        try:
            dom = DomainType(dval)
        except ValueError as e:
            raise ValueError(f"Extrator não suportado para domínio {dval!r}") from e

        try:
            src = SourceType(sval)
        except ValueError as e:
            raise ValueError(f"Extrator não suportado para combinação {dval!r}/{sval!r}") from e

        key = dom.value
        if src == SourceType.API:
            ext_cls = cls._API.get(key)
            if not ext_cls:
                raise ValueError(f"Extrator não suportado para domínio {key!r}")
            return ext_cls(client)
        if src == SourceType.BULK:
            ext_cls = cls._BULK.get(key)
            if not ext_cls:
                raise ValueError(f"Extrator não suportado para domínio {key!r}")
            return ext_cls(client, domain_name=key)

        raise ValueError(f"Extrator não suportado para combinação {key}/{sval}")
