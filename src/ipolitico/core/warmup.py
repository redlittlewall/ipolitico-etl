"""
Pré-aquecimento seletivo de cache para rotas da API da Câmara com histórico de 504.

A API da Câmara utiliza um proxy reverso que cacheia respostas JSON por alguns
minutos. A primeira requisição a um recurso frio pode levar 5-12s e gerar HTTP 504
(Gateway Timeout) quando o servidor de origem não responde a tempo.

Este módulo permite pré-aquecer o cache fazendo uma requisição GENTIL (sequencial,
sem concorrência) para cada ID antes da extração concorrente normal. Isso é
relevante apenas para rotas filhas que comprovadamente sofrem de cache miss:
``deputados_historico``, ``eventos_pauta`` e ``relacionadas``.

Princípios:
    - Apenas rotas com histórico de 504 recebem warmup.
    - Requisições sequenciais para não pressionar a API.
    - Best-effort: erros são ignorados.
    - Deduplicação global na sessão: cada URL é aquecida no máximo uma vez.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ipolitico.core.constants import DomainType


@dataclass
class WarmupSpec:
    """Especificação de pré-aquecimento para um domínio.

    Define o template de rota e como extrair IDs dos jobs gerados pelo
    ``CamaraJobPlanner`` para construir as URLs de pré-aquecimento.

    Attributes:
        route_template: Template de rota com placeholders para os IDs.
            Ex: ``"/deputados/{deputado_id}/historico"``.
        id_keys: Chaves para extrair valores dos jobs. O primeiro elemento
            é usado como chave posicional no template; os demais são
            ignorados no template mas usados na deduplicação.
        is_list_key: Se True, o valor extraído via ``id_keys[0]`` é uma
            lista de IDs que deve ser achatada (um URL por elemento).
    """

    route_template: str
    id_keys: list[str] = field(default_factory=list)
    is_list_key: bool = False


# Rotas com histórico comprovado de 504 em execuções FULL_LOAD.
# Apenas domínios listados aqui recebem pré-aquecimento.
# Demais domínios confiam no retry+backoff do CamaraClient.
WARMUP_CONFIG: dict[DomainType, WarmupSpec] = {
    DomainType.DEPUTADOS_HISTORICO: WarmupSpec(
        route_template="deputados/{id}/historico",
        id_keys=["deputado_id"],
    ),
    DomainType.EVENTOS_PAUTA: WarmupSpec(
        route_template="eventos/{id}/pauta",
        id_keys=["evento_ids"],
        is_list_key=True,
    ),
    DomainType.RELACIONADAS: WarmupSpec(
        route_template="proposicoes/{id}/relacionadas",
        id_keys=["proposicao_ids"],
        is_list_key=True,
    ),
}


def build_warmup_urls(base_url: str, jobs: list[dict[str, Any]], spec: WarmupSpec) -> list[str]:
    """Constrói URLs de pré-aquecimento a partir dos jobs do domínio.

    Extrai IDs dos jobs conforme a especificação (chave única ou lista),
    deduplica e monta URLs absolutas.

    Args:
        base_url: Base URL da API (ex: ``"https://dadosabertos.camara.leg.br/api/v2"``).
        jobs: Lista de jobs gerados pelo ``CamaraJobPlanner``.
        spec: Especificação de warmup do domínio.

    Returns:
        Lista de URLs absolutas para pré-aquecimento, sem duplicatas.
    """
    if not jobs or not spec.id_keys:
        return []

    key = spec.id_keys[0]
    ids: set[Any] = set()

    for job in jobs:
        raw = job.get(key)
        if raw is None:
            continue
        if spec.is_list_key and isinstance(raw, list):
            for item in raw:
                if item is not None:
                    ids.add(str(item))
        elif not spec.is_list_key:
            ids.add(str(raw))

    base = base_url.rstrip("/")
    urls: list[str] = []
    for id_val in sorted(ids):
        url = f"{base}/{spec.route_template.format(id=id_val)}"
        urls.append(url)

    return urls
