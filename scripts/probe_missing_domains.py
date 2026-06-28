#!/usr/bin/env python3
"""Probe API data shapes for 3 missing domains."""

import json
import urllib.request


def get(path, params=None):
    url = f"https://dadosabertos.camara.leg.br/api/v2/{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp).get("dados", [])


def main():
    # Referencias
    for rp in [
        "referencias/uf",
        "referencias/deputados/codSituacao",
        "referencias/proposicoes/siglaTipo",
    ]:
        d = get(rp)
        print(f"{rp}: {len(d)} items")
        if d:
            print(f"  keys={list(d[0].keys())}")
            print(f"  sample={json.dumps(d[0], ensure_ascii=False)[:200]}")

    # Orgaos votacoes
    for oid in [2, 4, 200, 367]:
        d = get(f"orgaos/{oid}/votacoes")
        print(f"orgao_{oid}_votacoes: {len(d)} items")
        if d:
            print(f"  keys={list(d[0].keys())}")
            print(f"  sample={json.dumps(d[0], ensure_ascii=False)[:200]}")

    # Partidos lideres
    for pid in [367, 379, 368]:
        d = get(f"partidos/{pid}/lideres")
        print(f"partido_{pid}_lideres: {len(d)} items")
        if d:
            print(f"  keys={list(d[0].keys())}")
            print(f"  sample={json.dumps(d[0], ensure_ascii=False)[:200]}")


if __name__ == "__main__":
    main()
