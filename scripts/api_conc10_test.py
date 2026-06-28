#!/usr/bin/env python3
"""
Teste: concorrência=10 vs endpoints que historicamente dão 504.

Simula o comportamento real da pipeline com CAMARA_HTTP_CONCURRENCY=10.
Cada endpoint é testado separadamente, igual a pipeline faria.
"""

import json
import statistics
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://dadosabertos.camara.leg.br/api/v2"
TIMEOUT = 60
CONCURRENCY = 10


def fetch(url: str) -> tuple[int, float, str]:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return r.status, (time.perf_counter() - t0) * 1000, ""
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - t0) * 1000, str(e)[:100]
    except Exception as e:
        return 0, (time.perf_counter() - t0) * 1000, str(e)[:100]


def test_endpoint(label: str, urls: list, conc: int = CONCURRENCY, runs: int = 1):
    all_statuses = defaultdict(int)
    all_latencies = []
    total_504 = 0
    total_429 = 0

    for run in range(runs):
        statuses = defaultdict(int)
        latencies = []
        t0 = time.perf_counter()

        with ThreadPoolExecutor(max_workers=conc) as pool:
            fut = {pool.submit(fetch, url): url for url in urls}
            for f in as_completed(fut):
                s, ms, _ = f.result()
                statuses[s] += 1
                if s == 200:
                    latencies.append(ms)
                if s == 504:
                    total_504 += 1
                if s == 429:
                    total_429 += 1

        wall = time.perf_counter() - t0
        for k, v in statuses.items():
            all_statuses[k] += v
        all_latencies.extend(latencies)

        if runs > 1:
            time.sleep(3)

    ok_total = all_statuses.get(200, 0)
    total = len(urls) * runs
    pct = ok_total / total * 100
    med = statistics.median(all_latencies) if all_latencies else 0

    flag = ""
    if total_504 > 0:
        flag += f" ⚠️504={total_504}"
    if total_429 > 0:
        flag += f" ⚠️429={total_429}"
    if pct == 100 and total_504 == 0 and total_429 == 0:
        flag = " ✅"

    print(
        f"  conc={conc:<3} | {label:<35} | OK={ok_total}/{total:<4} ({pct:.0f}%)  "
        f"P50={med:.0f}ms  Wall={wall:.1f}s  Statuses: {dict(all_statuses)}{flag}"
    )
    return ok_total, total, total_504, total_429


print("=" * 85)
print("TESTE: CONCORRÊNCIA=10 vs ENDPOINTS COM HISTÓRICO DE 504")
print(f"Data: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Cada teste roda com {CONCURRENCY} requisições simultâneas (ThreadPoolExecutor)")
print("=" * 85)

# ── 1. PARTIDOS ──
print("\n[1/6] PARTIDOS (lista) — 64 ocorrências de 504 no log histórico")
partidos_urls = [f"{BASE}/partidos?itens=100&pagina={i}" for i in range(1, 11)]
test_endpoint("/partidos", partidos_urls)
time.sleep(3)

# ── 2. PROPOSICOES ──
print("\n[2/6] PROPOSICOES (lista) — 46 ocorrências de 504 no log")
proposicoes_urls = [f"{BASE}/proposicoes?itens=100&pagina={i}" for i in range(1, 11)]
test_endpoint("/proposicoes", proposicoes_urls)
time.sleep(3)

# ── 3. VOTACOES (lista) ──
print("\n[3/6] VOTACOES (lista) — 29 ocorrências de 504 no log")
votacoes_urls = [f"{BASE}/votacoes?itens=100&pagina={i}" for i in range(1, 11)]
test_endpoint("/votacoes", votacoes_urls)
time.sleep(3)

# ── 4. DEPUTADOS_HISTORICO (misturado) ──
print("\n[4/6] DEPUTADOS_HISTORICO (mix de rápidos + lentos)")
print("     Inclui 10 deputados pesados (longa história) e 15 atuais")
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
    204554,
    204560,
    220665,
    220672,
    220669,
    220676,
    160510,
    220681,
    220682,
    220686,
]
historico_urls = [f"{BASE}/deputados/{did}/historico" for did in pesados]
test_endpoint("/deputados/{id}/historico", historico_urls)
time.sleep(3)

# ── 5. EVENTOS_PAUTA ──
print("\n[5/6] EVENTOS_PAUTA — endpoint que mais deu 504 (maioria dos 8.641)")
# Busca lista de eventos primeiro
try:
    with urllib.request.urlopen(f"{BASE}/eventos?itens=100&pagina=1", timeout=30) as r:
        data = json.loads(r.read().decode())
        eventos_ids = [e["id"] for e in data.get("dados", [])]
    print(f"     {len(eventos_ids)} eventos encontrados na lista")
    pauta_urls = [f"{BASE}/eventos/{eid}/pauta" for eid in eventos_ids]
    test_endpoint("/eventos/{id}/pauta", pauta_urls)
except Exception as e:
    print(f"     ❌ Erro ao buscar eventos: {e}")
time.sleep(3)

# ── 6. PROPOSICOES/RELACIONADAS ──
print("\n[6/6] PROPOSICOES/{id}/RELACIONADAS — 50 ocorrências de 504 no log")
prop_ids = [490116, 490115, 490114, 490113, 490112, 490111, 490110, 490109, 490108, 490107]
rel_urls = [f"{BASE}/proposicoes/{pid}/relacionadas" for pid in prop_ids]
test_endpoint("/proposicoes/{id}/relacionadas", rel_urls * 5)

print("\n" + "=" * 85)
print("RESUMO")
print("=" * 85)
print("Concorrência testada: 10")
print("Resultado: ver acima")
print()
print("CONCLUSÃO:")
print("  - Se 100% OK em todos endpoints → não precisa de pré-aquecimento")
print("  - Se ainda há 504s → pré-aquecimento é necessário")
