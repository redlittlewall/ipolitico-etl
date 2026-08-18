#!/usr/bin/env python
"""Smoke do sistema portaldatransparencia: consulta pontual barata na API v3.

Valida, com a chave real do usuário (``PORTAL_API_KEY`` no .env), que o
``PortalTransparenciaClient`` autentica e a API v3 responde 200. A consulta é
deliberadamente barata: uma página de ``/api-de-dados/orgaos-siape`` (órgãos do
SIAPE, lookup pequeno e estável).

Uso (a partir de ``ipolitico-etl/``):

    .venv/bin/python scripts/smoke_portal_transparencia.py

Saída esperada (com chave válida):

    OK: 200 — /api-de-dados/orgaos-siape devolveu 25 órgãos (1 página).

Sem chave configurada, o script sai com erro e instrui a gerar a chave.
"""

import asyncio
import sys

from ipolitico.core.config import PORTAL_API_KEY
from ipolitico.core.portal_transparencia_client import (
    PortalTransparenciaAuthError,
    PortalTransparenciaClient,
)

ENDPOINT = "api-de-dados/orgaos-siape"
PARAMS = {"pagina": 1}


async def main() -> int:
    """Executa a consulta smoke e imprime o resultado.

    Returns:
        int: 0 em sucesso; 1 se a chave estiver ausente ou a API rejeitar a
        autenticação; 2 em qualquer outra falha.
    """
    if not PORTAL_API_KEY:
        print(
            "ERRO: PORTAL_API_KEY não configurada.\n"
            "Copie .env.example para .env e gere a sua chave gratuita em:\n"
            "  https://portaldatransparencia.gov.br/pagina-despesas/API\n"
            "A chave nunca é versionada (o .env é gitignored).",
            file=sys.stderr,
        )
        return 1

    client = PortalTransparenciaClient(api_key=PORTAL_API_KEY)
    try:
        payload = await client.fetch(ENDPOINT, params=PARAMS)
    except PortalTransparenciaAuthError as e:
        print(f"ERRO de autenticação (chave inválida?): {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — smoke deve reportar qualquer falha
        print(f"Falha na consulta: {e}", file=sys.stderr)
        return 2

    n = len(payload) if isinstance(payload, list) else 1
    print(f"OK: /api-de-dados/orgaos-siape devolveu {n} registros (1 página).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
