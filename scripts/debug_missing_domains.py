#!/usr/bin/env python3
"""
Debug script: test extraction + transformation for 3 missing domains
and save detailed debug output to a file.
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import asyncio

from ipolitico.core.client import CamaraClient

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS

OUT = Path("/tmp/domain_debug.txt")


def log(msg):
    with open(OUT, "a") as f:
        f.write(str(msg) + "\n")
    print(msg)


async def test_referencias(client):
    log("\n=== REFERENCIAS ===")

    # Check schema
    schema = SILVER_SCHEMAS.get(DomainType.REFERENCIAS.value)
    log(f"Schema exists: {schema is not None}")
    if schema:
        log(f"Schema columns: {list(schema.keys())}")

    # Try extract
    from ipolitico.extractors.camara.api.referencias import REFERENCE_ROUTES, ReferenciasExtractor

    ext = ReferenciasExtractor(client)

    try:
        df = await ext.extract(routes=list(REFERENCE_ROUTES))
        log(f"Raw DataFrame: {df.shape}, columns: {list(df.columns)}")
        if not df.is_empty():
            log(f"First row: {df.row(0, named=True)}")
    except Exception as e:
        log(f"EXTRACT ERROR: {e}")
        traceback.print_exc(file=open(OUT, "a"))
        return

    # Try transform
    from ipolitico.transformers.camara.referencias_transformer import CamaraReferenciasTransformer

    trans = CamaraReferenciasTransformer()

    try:
        clean = trans.transform(df)
        log(f"Clean DataFrame: {clean.shape}, columns: {list(clean.columns)}")
        if not clean.is_empty():
            log(f"First row: {clean.row(0, named=True)}")
    except Exception as e:
        log(f"TRANSFORM ERROR: {e}")
        traceback.print_exc(file=open(OUT, "a"))


async def test_orgaos_votacoes(client):
    log("\n=== ORGAOS_VOTACOES ===")

    schema = SILVER_SCHEMAS.get(DomainType.ORGAOS_VOTACOES.value)
    log(f"Schema exists: {schema is not None}")
    if schema:
        log(f"Schema columns: {list(schema.keys())}")

    from ipolitico.extractors.camara.api.orgao_child import OrgaoVotacoesExtractor

    ext = OrgaoVotacoesExtractor(client)

    # Just test with a few orgao IDs
    orgao_ids = [2, 3, 4, 200, 367, 456]
    try:
        df = await ext.extract(orgao_ids=orgao_ids)
        log(f"Raw DataFrame: {df.shape}, columns: {list(df.columns)}")
        if not df.is_empty():
            log(f"First row: {df.row(0, named=True)}")
    except Exception as e:
        log(f"EXTRACT ERROR: {e}")
        traceback.print_exc(file=open(OUT, "a"))
        return

    from ipolitico.transformers.camara.evento_child_transformer import CamaraEventoChildTransformer

    trans = CamaraEventoChildTransformer()

    try:
        clean = trans.transform(df, sub_domain="orgaos_votacoes")
        log(f"Clean DataFrame: {clean.shape}, columns: {list(clean.columns)}")
        if not clean.is_empty():
            log(f"First row: {clean.row(0, named=True)}")
    except Exception as e:
        log(f"TRANSFORM ERROR: {e}")
        traceback.print_exc(file=open(OUT, "a"))


async def test_partidos_lideres(client):
    log("\n=== PARTIDOS_LIDERES ===")

    schema = SILVER_SCHEMAS.get(DomainType.PARTIDOS_LIDERES.value)
    log(f"Schema exists: {schema is not None}")
    if schema:
        log(f"Schema columns: {list(schema.keys())}")

    from ipolitico.extractors.camara.api.partido_child import PartidoLideresExtractor

    ext = PartidoLideresExtractor(client)

    partido_ids = [367, 368, 369, 370, 379]
    try:
        df = await ext.extract(partido_ids=partido_ids, legislatura_id=57)
        log(f"Raw DataFrame: {df.shape}, columns: {list(df.columns)}")
        if not df.is_empty():
            log(f"First row: {df.row(0, named=True)}")
            for r in range(min(5, df.height)):
                log(f"  Row {r}: {df.row(r, named=True)}")
    except Exception as e:
        log(f"EXTRACT ERROR: {e}")
        traceback.print_exc(file=open(OUT, "a"))
        return

    from ipolitico.transformers.camara.membros_transformer import CamaraMembrosTransformer

    trans = CamaraMembrosTransformer()

    try:
        clean = trans.transform(df, sub_domain="partidos_lideres")
        log(f"Clean DataFrame: {clean.shape}, columns: {list(clean.columns)}")
        if not clean.is_empty():
            log(f"First row: {clean.row(0, named=True)}")
    except Exception as e:
        log(f"TRANSFORM ERROR: {e}")
        traceback.print_exc(file=open(OUT, "a"))


async def main():
    client = CamaraClient()

    await test_referencias(client)
    await test_orgaos_votacoes(client)
    await test_partidos_lideres(client)

    await client.aclose()
    log("\n=== DEBUG COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
