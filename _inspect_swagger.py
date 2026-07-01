#!/usr/bin/env python3
"""Extract composicao endpoint schemas from swagger."""

import json

with open("/home/red_guy/Documentos/iPolitico/ipolitico-etl/docs/swagger/senado_swagger.json") as f:
    spec = json.load(f)

paths = {k: v for k, v in spec.get("paths", {}).items() if "composicao" in k}
print(f"Found {len(paths)} composicao paths")
for p in sorted(paths.keys()):
    print(f"\n{'=' * 60}")
    print(f"Path: {p}")
    for m, d in paths[p].items():
        print(f"  Method: {m}")
        print(f"  Summary: {d.get('summary', '')}")
        resp = d.get("responses", {}).get("200", {})
        schema = resp.get("schema", resp)
        print(f"  Schema: {json.dumps(schema, indent=2, ensure_ascii=False)[:2000]}")
