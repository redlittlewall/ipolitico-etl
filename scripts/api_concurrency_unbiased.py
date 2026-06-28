#!/usr/bin/env python3
"""
Teste NÃO enviesado de concorrência vs 504.

Cada nível de concorrência é testado em uma SEÇÃO FRESCA da API
(endpoints diferentes) para não haver viés de cache quente.
"""

import json
import statistics
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://dadosabertos.camara.leg.br/api/v2"
TIMEOUT = 60


def fetch_retry(url: str, retries: int = 3) -> tuple[int, float, str]:
    """Fetch com retry exponencial (simula pipeline real)."""
    for attempt in range(retries):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                return r.status, (time.perf_counter() - t0) * 1000, f"ok attempt={attempt+1}"
        except urllib.error.HTTPError as e:
            elapsed = (time.perf_counter() - t0) * 1000
            if e.code in (504, 429) and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            return e.code, elapsed, f"attempt={attempt+1} retries exhausted"
        except Exception as e:
            return 0, (time.perf_counter() - t0) * 1000, str(e)[:100]
    return 0, 0, "max retries"


def test_concurrency_1pass(label: str, urls: list, conc: int, retries: int = 1):
    """Testa UMA VEZ cada URL (frio), sem reuso de cache."""
    statuses = defaultdict(int)
    latencies_ok = []
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as pool:
        fut = {pool.submit(fetch_retry, url, retries): url for url in urls}
        for f in as_completed(fut):
            s, ms, _ = f.result()
            statuses[s] += 1
            if s == 200:
                latencies_ok.append(ms)
    wall = time.perf_counter() - t0
    ok = statuses.get(200, 0)
    pct = ok / len(urls) * 100
    med = statistics.median(latencies_ok) if latencies_ok else 0
    n504 = statuses.get(504, 0)
    n429 = statuses.get(429, 0)
    flag = ""
    if n504 > 0:
        flag += f" ⚠️504={n504}"
    if n429 > 0:
        flag += f" ⚠️429={n429}"
    if pct == 100 and n504 == 0 and n429 == 0:
        flag = " ✅"
    print(
        f"  conc={conc:<3} | {label:<35} | OK={ok}/{len(urls):<4} ({pct:.0f}%)  "
        f"P50={med:.0f}ms  Wall={wall:.1f}s{flag}"
    )
    return ok, len(urls), n504, n429


# ============================================================================
# PREPARAÇÃO: IDs únicos para cada teste (para não ter viés de cache)
# ============================================================================

print("=" * 85)
print("PREPARAÇÃO: buscando IDs de deputados, eventos e proposições")
print("=" * 85)

# Busca MUITOS IDs de deputados (dividir em grupos para cada teste)
try:
    with urllib.request.urlopen(f"{BASE}/deputados?itens=100&pagina=1", timeout=30) as r:
        data = json.loads(r.read().decode())
        dep_ids = [d["id"] for d in data["dados"]]
    time.sleep(1)
    with urllib.request.urlopen(f"{BASE}/deputados?itens=100&pagina=2", timeout=30) as r:
        data = json.loads(r.read().decode())
        dep_ids += [d["id"] for d in data["dados"]]
    print(f"  Deputados: {len(dep_ids)} IDs")
except Exception as e:
    print(f"  ❌ Erro deputados: {e}")
    dep_ids = []

# Busca IDs de eventos
try:
    with urllib.request.urlopen(f"{BASE}/eventos?itens=100&pagina=1", timeout=30) as r:
        data = json.loads(r.read().decode())
        evt_ids = [e["id"] for e in data.get("dados", [])]
    print(f"  Eventos: {len(evt_ids)} IDs")
except Exception as e:
    print(f"  ❌ Erro eventos: {e}")
    evt_ids = []

# IDs de proposicoes para relacionadas
rel_prop_ids = [490116, 490115, 490114, 490113, 490112, 490111, 490110, 490109, 490108, 490107]

# ============================================================================
# TESTE 1: DEPUTADOS_HISTORICO — conc=5 vs conc=10 vs conc=15
# ============================================================================
print()
print("=" * 85)
print("TESTE 1: /deputados/{id}/historico")
print("  Grupos DIFERENTES de deputados para cada nível (frio real)")
print("  Cada grupo: 15 deputados (nunca consultados antes)")
print("=" * 85)

pool_5 = dep_ids[0:15]
pool_10 = dep_ids[15:30]
pool_15 = dep_ids[30:45]
pool_20 = dep_ids[45:60]

for conc, pool in [(5, pool_5), (10, pool_10), (15, pool_15), (20, pool_20)]:
    urls = [f"{BASE}/deputados/{did}/historico" for did in pool]
    test_concurrency_1pass(f"/deputados/{{id}}/historico (conc={conc})", urls, conc, retries=1)
    time.sleep(2)

# ============================================================================
# TESTE 2: EVENTOS_PAUTA — conc=5 vs conc=10
# ============================================================================
print()
print("=" * 85)
print("TESTE 2: /eventos/{id}/pauta")
print("  Metade dos eventos para conc=5, outra metade para conc=10")
print("=" * 85)

evt_pool_5 = evt_ids[: len(evt_ids) // 2]
evt_pool_10 = evt_ids[len(evt_ids) // 2 :]

for conc, pool in [(5, evt_pool_5), (10, evt_pool_10)]:
    urls = [f"{BASE}/eventos/{eid}/pauta" for eid in pool]
    test_concurrency_1pass(f"/eventos/{{id}}/pauta (conc={conc})", urls, conc, retries=1)
    time.sleep(2)

# ============================================================================
# TESTE 3: VOTACOES (lista) — conc=5 vs conc=8 vs conc=10
# ============================================================================
print()
print("=" * 85)
print("TESTE 3: /votacoes (lista)")
print("  Páginas diferentes para cada nível de concorrência")
print("=" * 85)

for conc in [5, 8, 10]:
    urls = [f"{BASE}/votacoes?itens=100&pagina={i}" for i in range(1, 11)]
    test_concurrency_1pass(f"/votacoes (conc={conc})", urls, conc, retries=1)
    time.sleep(5)

# ============================================================================
# TESTE 4: PROPOSICOES (lista) — conc=5 vs conc=10
# ============================================================================
print()
print("=" * 85)
print("TESTE 4: /proposicoes (lista) — conc=5 vs conc=10")
print("=" * 85)

for conc in [5, 10]:
    urls = [f"{BASE}/proposicoes?itens=100&pagina={i}" for i in range(1, 11)]
    test_concurrency_1pass(f"/proposicoes (conc={conc})", urls, conc, retries=1)
    time.sleep(5)

# ============================================================================
# TESTE 5: PARTIDOS (lista) — conc=5 vs conc=10
# ============================================================================
print()
print("=" * 85)
print("TESTE 5: /partidos (lista) — conc=5 vs conc=10")
print("=" * 85)

for conc in [5, 10]:
    urls = [f"{BASE}/partidos?itens=100&pagina={i}" for i in range(1, 11)]
    test_concurrency_1pass(f"/partidos (conc={conc})", urls, conc, retries=1)
    time.sleep(5)

# ============================================================================
# TESTE 6: PROPOSICOES/RELACIONADAS — conc=5 vs conc=10
# ============================================================================
print()
print("=" * 85)
print("TESTE 6: /proposicoes/{id}/relacionadas — conc=5 vs conc=10")
print("=" * 85)

for conc in [5, 10]:
    urls = [f"{BASE}/proposicoes/{pid}/relacionadas" for pid in rel_prop_ids]
    test_concurrency_1pass(f"/proposicoes/{{id}}/relacionadas (conc={conc})", urls, conc, retries=1)
    time.sleep(5)

# ============================================================================
# RESUMO
# ============================================================================
print()
print("=" * 85)
print("RESUMO — Concorrência ideal por endpoint (frio real)")
print("=" * 85)
print()
print("Endpoint                           | conc=5  | conc=8  | conc=10 | conc=15 | conc=20")
print("                                   |         |         |         |         |")
print("Deputados_historico                |   ?     |   ?     |   ?     |   ?     |   ?")
print("Eventos_pauta                      |   ?     |   ?     |   ?     |  N/A    |  N/A")
print("Votacoes (lista)                   |   ?     |   ?     |   ?     |  N/A    |  N/A")
print("Proposicoes (lista)                |   ?     |   ?     |   ?     |  N/A    |  N/A")
print("Partidos (lista)                   |   ?     |   ?     |   ?     |  N/A    |  N/A")
print("Proposicoes/relacionadas           |   ?     |   ?     |   ?     |  N/A    |  N/A")
