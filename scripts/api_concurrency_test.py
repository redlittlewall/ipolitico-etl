#!/usr/bin/env python3
"""
Test real concurrency limits of the Camara API.

Runs 4 scenarios measuring success rates at various concurrency levels.
Each scenario runs 3 times per level and reports the median.
"""

from __future__ import annotations

import random
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://dadosabertos.camara.leg.br/api/v2"

# Known deputy IDs (roughly first 6 months of 2025 legislative session)
DEPUTADO_IDS: list[int] = [
    204554,
    204560,
    204556,
    204561,
    204557,
    204562,
    204558,
    204563,
    204559,
    220594,
    220595,
    220596,
    220597,
    220598,
    220599,
    220600,
    220601,
    220602,
    220603,
    220604,
    220605,
    220606,
    220607,
    220608,
    220609,
    220610,
    220611,
    220612,
    220614,
    220615,
    220616,
    220617,
    220618,
    220619,
    220620,
    220621,
    220622,
    220623,
    220624,
    220625,
    220626,
    220627,
    220628,
    220629,
    220630,
    220631,
    220632,
    220633,
    220634,
    220635,
]

TIMEOUT = 60
RUNS = 3
COOLDOWN = 5  # seconds between levels


def _request(url: str) -> tuple[int, float]:
    """Make one GET request, return (status_code, elapsed_seconds)."""
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "ipolitico-test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            elapsed = time.monotonic() - start
            return resp.status, elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.monotonic() - start
        return e.code, elapsed
    except (urllib.error.URLError, TimeoutError, OSError):
        elapsed = time.monotonic() - start
        return 0, elapsed  # 0 = connection/network error


def _run_level(urls: list[str], concurrency: int, label: str) -> dict:
    """Launch `concurrency` requests in parallel, return stats."""
    ok = 0
    err = 0
    times: list[float] = []
    statuses: dict[int, int] = {}
    err_types: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        fut_to_url = {pool.submit(_request, u): u for u in urls}
        for fut in as_completed(fut_to_url):
            status, elapsed = fut.result()
            times.append(elapsed)
            statuses[status] = statuses.get(status, 0) + 1
            if status == 200:
                ok += 1
            else:
                err += 1
                if status == 0:
                    err_types["network"] = err_types.get("network", 0) + 1
                elif status == 504:
                    err_types["504"] = err_types.get("504", 0) + 1
                elif status == 429:
                    err_types["429"] = err_types.get("429", 0) + 1
                elif status == 502:
                    err_types["502"] = err_types.get("502", 0) + 1
                else:
                    err_types[str(status)] = err_types.get(str(status), 0) + 1

    return {
        "concurrency": concurrency,
        "label": label,
        "ok": ok,
        "err": err,
        "total": ok + err,
        "pct_ok": 100.0 * ok / (ok + err) if (ok + err) else 0.0,
        "p50": statistics.median(times) if times else 0.0,
        "p95": sorted(times)[int(len(times) * 0.95)] if times else 0.0,
        "statuses": statuses,
        "err_types": err_types,
    }


def _print_results(results: list[dict]) -> None:
    """Print a table of results."""
    print(
        f"{'Conc':>4}  {'OK%':>5}  {'OK':>4}/{'Tot':<4}  "
        f"{'P50(s)':>7}  {'P95(s)':>7}  {'Statuses':<50}"
    )
    print("-" * 90)
    for r in results:
        status_str = ", ".join(f"{s}:{c}" for s, c in sorted(r["statuses"].items()))
        p50 = f"{r['p50']:.2f}" if r["p50"] else "-"
        p95 = f"{r['p95']:.2f}" if r["p95"] else "-"
        print(
            f"{r['concurrency']:>4}  "
            f"{r['pct_ok']:>5.1f}  "
            f"{r['ok']:>4}/{r['total']:<4}  "
            f"{p50:>7}  {p95:>7}  "
            f"{status_str:<50}"
        )


def test1_lightweight() -> None:
    """
    Test 1: CONCURRENCY LIMIT (lightweight endpoint).

    Hit /deputados?itens=10 at increasing concurrency levels.
    """
    print("\n" + "=" * 90)
    print("TEST 1: Lightweight endpoint /deputados at increasing concurrency")
    print("=" * 90)

    levels = [5, 10, 20, 50, 100, 200, 500]
    url = f"{BASE}/deputados?itens=10&pagina=1"

    for level in levels:
        results = []
        for run in range(RUNS):
            urls = [url for _ in range(level)]
            r = _run_level(urls, min(level, 50), f"run{run+1}")
            results.append(r)
            time.sleep(COOLDOWN)
        # Pick the median result by pct_ok
        results.sort(key=lambda x: x["pct_ok"])
        median = results[len(results) // 2]
        print(
            f"\n  Concurrency={level:>3} | "
            f"OK={median['ok']:>3}/{median['total']:<3} "
            f"({median['pct_ok']:.1f}%)  "
            f"P50={median['p50']:.2f}s  "
            f"P95={median['p95']:.2f}s  "
            f"Statuses: {median['statuses']}"
        )


def test2_heavy() -> None:
    """
    Test 2: HEAVY endpoint (deputados/{id}/historico) under concurrency.

    Levels: 5, 10, 20, 50 (stop if >50% failures in median run).
    """
    print("\n" + "=" * 90)
    print("TEST 2: Heavy endpoint /deputados/{id}/historico at increasing concurrency")
    print("=" * 90)

    levels = [5, 10, 20, 50]

    for level in levels:
        results = []
        for run in range(RUNS):
            sample = random.sample(DEPUTADO_IDS, level)
            urls = [f"{BASE}/deputados/{did}/historico" for did in sample]
            r = _run_level(urls, min(level, 50), f"run{run+1}")
            results.append(r)
            time.sleep(COOLDOWN)
        results.sort(key=lambda x: x["pct_ok"])
        median = results[len(results) // 2]
        print(
            f"\n  Concurrency={level:>3} | "
            f"OK={median['ok']:>3}/{median['total']:<3} "
            f"({median['pct_ok']:.1f}%)  "
            f"P50={median['p50']:.2f}s  "
            f"P95={median['p95']:.2f}s  "
            f"Statuses: {median['statuses']}"
        )
        if median["pct_ok"] < 50:
            print(f"  >>> Stopping: >50% failures at concurrency {level}")
            break


def test3_mixed() -> None:
    """
    Test 3: MIXED endpoints (50% lightweight, 50% heavy).

    Simulates real pipeline load.
    """
    print("\n" + "=" * 90)
    print("TEST 3: Mixed endpoints (50% lightweight, 50% heavy)")
    print("=" * 90)

    levels = [5, 10, 20, 30]
    light_url = f"{BASE}/deputados?itens=10&pagina=1"

    for level in levels:
        results = []
        for run in range(RUNS):
            heavy_count = level // 2
            light_count = level - heavy_count
            sample = random.sample(DEPUTADO_IDS, heavy_count)
            urls = [f"{BASE}/deputados/{did}/historico" for did in sample]
            urls += [light_url for _ in range(light_count)]

            start = time.monotonic()
            r = _run_level(urls, min(level, 50), f"run{run+1}")
            r["wall_time"] = time.monotonic() - start
            results.append(r)
            time.sleep(COOLDOWN)

        results.sort(key=lambda x: x["pct_ok"])
        median = results[len(results) // 2]
        print(
            f"\n  Concurrency={level:>3} | "
            f"OK={median['ok']:>3}/{median['total']:<3} "
            f"({median['pct_ok']:.1f}%)  "
            f"Wall={median.get('wall_time', 0):.1f}s  "
            f"P50={median['p50']:.2f}s  "
            f"P95={median['p95']:.2f}s  "
            f"Statuses: {median['statuses']}"
        )


def test4_saturation() -> None:
    """
    Test 4: Does saturating ONE endpoint affect OTHERS?

    While 20 concurrent heavy requests run, send a lightweight "probe"
    every second. If probes fail, limit is global; if only heavy fails,
    limit is per-endpoint.
    """
    print("\n" + "=" * 90)
    print("TEST 4: Saturation cross-impact (heavy + lightweight probe)")
    print("=" * 90)

    light_url = f"{BASE}/deputados?itens=1&pagina=1"
    heavy_count = 20
    probe_interval = 1  # seconds between probes

    for run in range(RUNS):
        print(f"\n  Run {run+1}/{RUNS}")
        sample = random.sample(DEPUTADO_IDS, heavy_count)
        heavy_urls = [f"{BASE}/deputados/{did}/historico" for did in sample]
        probe_results: list[dict] = []
        heavy_results: list[dict] = []

        def _probe_loop() -> None:
            """Send probes while heavy requests run."""
            probes_sent = 0
            while len(heavy_results) < heavy_count:
                status, elapsed = _request(light_url)
                probe_results.append({"ok": status == 200, "status": status, "elapsed": elapsed})
                probes_sent += 1
                if probes_sent >= heavy_count * 2:  # safety cap
                    break
                time.sleep(probe_interval)

        # Start probe loop in separate thread
        from threading import Thread

        probe_thread = Thread(target=_probe_loop, daemon=True)
        probe_thread.start()

        # Fire heavy requests
        with ThreadPoolExecutor(max_workers=heavy_count) as pool:
            fut_map = {pool.submit(_request, u): u for u in heavy_urls}
            for fut in as_completed(fut_map):
                status, elapsed = fut.result()
                heavy_results.append({"ok": status == 200, "status": status, "elapsed": elapsed})

        probe_thread.join(timeout=10)

        # Report
        heavy_ok = sum(1 for r in heavy_results if r["ok"])
        heavy_total = len(heavy_results)
        probe_ok = sum(1 for r in probe_results if r["ok"])
        probe_total = len(probe_results)

        print(
            f"    Heavy:  OK={heavy_ok:>2}/{heavy_total:<2} " f"({100.0*heavy_ok/heavy_total:.0f}%)"
        )
        print(
            f"    Probe:  OK={probe_ok:>2}/{probe_total:<2} " f"({100.0*probe_ok/probe_total:.0f}%)"
        )
        if probe_total > 0:
            statuses_flat = ", ".join(
                f"{s}:{sum(1 for r in probe_results if r['status']==s)}"
                for s in sorted({r["status"] for r in probe_results})
            )
            print(f"    Probe statuses: {statuses_flat}")
        if probe_ok < probe_total and heavy_ok < heavy_total:
            print("    >>> CONCLUSION: Limit is GLOBAL (both endpoints affected)")
        elif probe_ok == probe_total and heavy_ok < heavy_total:
            print("    >>> CONCLUSION: Limit is PER-ENDPOINT (only historico affected)")
        else:
            print("    >>> CONCLUSION: No clear saturation detected at this level")

        time.sleep(COOLDOWN * 2)


def main() -> None:
    """Run all 4 tests sequentially."""
    print("Concurrency Limit Test for Camara API")
    print(f"Base URL: {BASE}")
    print(f"Runs per level: {RUNS}")
    print(f"Cooldown between levels: {COOLDOWN}s")
    print(f"Request timeout: {TIMEOUT}s")

    test1_lightweight()
    test2_heavy()
    test3_mixed()
    test4_saturation()

    print("\n" + "=" * 90)
    print("ALL TESTS COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
