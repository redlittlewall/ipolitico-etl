"""Passo 0 do ticket 04 — baixar UM dump anual de viagens via o cliente real.

Usa o ``PortalTransparenciaClient.download_file`` (Range-resume, User-Agent de
navegador, host S3) para baixar o dump anual ``/download-de-dados/viagens/2016``
(~131 MB) para ``data/portal_dumps/viagens_2016.zip`` — o mesmo caminho que o
extrator bulk usa em produção. Valida o download real e deixa o arquivo para a
verificação do schema/uniqueness do ``*_Viagem.csv`` e extração de fixture.

Uso: python .scratch/portal-transparencia/tools/_capture_viagens_dump.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from ipolitico.core.config import DATA_DIR
from ipolitico.core.portal_transparencia_client import PortalTransparenciaClient

URL = "https://portaldatransparencia.gov.br/download-de-dados/viagens/2016"
DEST = Path(DATA_DIR) / "portal_dumps" / "viagens_2016.zip"


async def main() -> None:
    """
    Baixa UM dump anual de viagens via o cliente real de produção.

    Usa ``PortalTransparenciaClient.download_file`` (Range-resume, WAF-gracioso)
    para validar o download real e deixar o ZIP para a verificação de schema/
    unicidade do ``*_Viagem.csv`` e extração de fixture.
    """
    client = PortalTransparenciaClient()
    try:
        ok = await client.download_file(URL, DEST)
        print(f"download_ok={ok}")
        print(f"local_bytes={os.path.getsize(DEST) if DEST.exists() else 0}")
        print(f"dest={DEST}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
