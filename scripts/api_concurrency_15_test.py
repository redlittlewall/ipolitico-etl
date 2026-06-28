#!/usr/bin/env python3
"""
Teste focado: concorrência 15 + endpoints não testados (partidos, proposicoes, votacoes).
Cada cenário roda 3x para mediana.
"""

import statistics
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://dadosabertos.camara.leg.br/api/v2"
TIMEOUT = 60


def fetch(url: str) -> tuple[int, float, str]:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            r.read()[:200]
            return r.status, (time.perf_counter() - t0) * 1000, ""
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - t0) * 1000, str(e)[:100]
    except Exception as e:
        return 0, (time.perf_counter() - t0) * 1000, str(e)[:100]


def median(vals):
    return statistics.median(vals) if vals else 0


def test_concurrency(concurrency: int, urls: list, label: str, runs: int = 3):
    results = []
    for run in range(runs):
        statuses = defaultdict(int)
        latencies = []
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            fut = {pool.submit(fetch, url): url for url in urls}
            for f in as_completed(fut):
                s, ms, _ = f.result()
                statuses[s] += 1
                if s == 200:
                    latencies.append(ms)
        wall = time.perf_counter() - t0
        ok = statuses.get(200, 0)
        pct = ok / len(urls) * 100
        results.append((ok, pct, median(latencies), wall, dict(statuses)))
        if run < runs - 1:
            time.sleep(3)

    # Median run
    results.sort(key=lambda r: -r[1])
    best = results[0]
    print(
        f"  Concurrency={concurrency:<3} | OK={best[0]}/{len(urls):<4} ({best[1]:.0f}%)  "
        f"P50={best[2]:.0f}ms  Wall={best[3]:.1f}s  Statuses: {best[4]}"
    )
    return best


print("=" * 80)
print("TESTE 1: CONCORRÊNCIA 15 vs 18 vs 20 (endpoint leve /deputados)")
print("=" * 80)

leves = [f"{BASE}/deputados?itens=10&pagina={i % 5 + 1}" for i in range(50)]
for conc in [15, 18, 20]:
    test_concurrency(conc, leves, "/deputados", runs=2)
    time.sleep(5)

print()
print("=" * 80)
print("TESTE 2: ENDPOINTS COM HISTÓRICO DE 504 (partidos, proposicoes, votacoes)")
print("=" * 80)

proposicoes_urls = [f"{BASE}/proposicoes?itens=10&pagina={i}" for i in range(1, 11)]
partidos_urls = [f"{BASE}/partidos?itens=10&pagina={i}" for i in range(1, 11)]
votacoes_urls = [f"{BASE}/votacoes?itens=10&pagina={i}" for i in range(1, 11)]

for label, urls in [
    ("/proposicoes", proposicoes_urls),
    ("/partidos", partidos_urls),
    ("/votacoes", votacoes_urls),
]:
    print(f"\n  --- {label} (concurrency=10) ---")
    test_concurrency(10, urls, label, runs=2)
    time.sleep(3)
    print(f"  --- {label} (concurrency=15) ---")
    test_concurrency(15, urls, label, runs=2)
    time.sleep(5)

print()
print("=" * 80)
print("TESTE 3: PROPOSICOES/{id}/RELACIONADAS (504 no log)")
print("=" * 80)

# IDs de proposicoes que sabemos existir
prop_ids = [490116, 490115, 490114, 490113, 490112, 490111, 490110, 490109, 490108, 490107]
rel_urls = [f"{BASE}/proposicoes/{pid}/relacionadas" for pid in prop_ids]
test_concurrency(10, rel_urls * 5, "/proposicoes/{id}/relacionadas", runs=2)

print()
print("=" * 80)
print("TESTE 4: SÓ DEPUTADOS PESADOS (concurrency=15)")
print("=" * 80)

pesados = [
    178957,
    74186,
    220656,
    178861,
    178992,
    220660,
    141405,
    131159,
    131745,
    74421,
    74212,
    74638,
    74418,
    74254,
    73805,
    73712,
    139379,
    132141,
    74010,
    178984,
]
pesados_urls = [f"{BASE}/deputados/{did}/historico" for did in pesados]
test_concurrency(15, pesados_urls, "deputados_historico (pesados)", runs=3)

print()
print("=" * 80)
print("RESUMO")
print("=" * 80)
print("Concorrência 15: ser tested above")
print("Concorrência 18: tested above")
print("Endpoints 504: ser results above")
