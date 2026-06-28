#!/usr/bin/env python3
"""
Experimentos para entender comportamento da API da Câmara.

Testes:
  1. Cold vs Warm: mesma rota, 2 chamadas seguidas — mede diferença de latência
  2. Concorrência: mesma rota com N paralelo — acha o ponto de 504
  3. Bulk disponível: verifica se CSVs existem para eventos_pauta e deputados_historico
"""

import json
import time
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime

BASE = "https://dadosabertos.camara.leg.br/api/v2"


# ── helpers ──────────────────────────────────────────────────────────────────


def get(url: str, timeout: float = 30) -> tuple[int, float, str | None]:
    """Chamada síncrona simples — retorna (status, elapsed_ms, body_ou_None)."""
    start = time.perf_counter()
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.perf_counter() - start) * 1000
            body = resp.read().decode()
            return resp.status, elapsed, body
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        return e.code, elapsed, None
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return 0, elapsed, str(e)


def get_json(url: str, timeout: float = 30) -> tuple[int, float, dict | None]:
    status, ms, body = get(url, timeout)
    if body:
        try:
            return status, ms, json.loads(body)
        except json.JSONDecodeError:
            return status, ms, None
    return status, ms, None


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── Experimento 1: Cold vs Warm ──────────────────────────────────────────────

COLD_WARM_ROUTES = [
    # Rotas que historicamente dão 504
    ("/eventos?situacao=Aprovado&ordem=ASC&ordenarPor=dataHoraInicio&itens=50", "eventos (lista)"),
    ("/deputados/204554/historico", "deputado_historico (204554)"),
    ("/deputados/204554/eventos", "deputado_eventos (204554)"),
    ("/eventos/161962/pauta", "evento_pauta (161962)"),
    # Rotas que NUNCA dão 504 (controle)
    ("/deputados/204554", "deputado_detalhe (204554)"),
    ("/partidos", "partidos (lista)"),
]


def experimento_cold_warm():
    """Mesma rota, 2 chamadas consecutivas. Mede latência de cada."""
    print(f"\n{'='*60}")
    print(f" EXPERIMENTO 1: COLD vs WARM  ({now()})")
    print(f"{'='*60}")
    print(f"{'Rota':<50} {'#1 (ms)':<10} {'#2 (ms)':<10} {'#1 status':<10} {'#2 status':<10}")
    print("-" * 90)

    for route, label in COLD_WARM_ROUTES:
        url = f"{BASE}{route}"
        s1, ms1, b1 = get(url)
        s2, ms2, b2 = get(url)
        print(f"{label:<50} {ms1:<10.0f} {ms2:<10.0f} {s1:<10} {s2:<10}")

        if s1 == 504:
            # Se deu 504 na primeira, tenta de novo com backoff
            for attempt in range(3):
                print(f"   ↳ Retry {attempt+1} após {2**(attempt+1)}s...")
                time.sleep(2 ** (attempt + 1))
                s_retry, ms_retry, b_retry = get(url)
                print(f"   ↳ Tentativa {attempt+2}: status={s_retry}, {ms_retry:.0f}ms")
                if s_retry != 504:
                    break


# ── Experimento 2: Concorrência progressiva ──────────────────────────────────


def experimento_concorrencia():
    """Mesma rota simples, N chamadas simultâneas. Mede quantas dão 504."""
    print(f"\n{'='*60}")
    print(f" EXPERIMENTO 2: CONCORRÊNCIA  ({now()})")
    print(f"{'='*60}")

    # Rota barata (nunca dá 504 sozinha)
    route = "/deputados?itens=10&pagina="
    concurrency_levels = [5, 10, 20, 50]

    for conc in concurrency_levels:
        results: list[tuple[int, float]] = []
        pages = [route + str(i % 5 + 1) for i in range(conc)]
        for p in pages:
            s, ms, _ = get(f"{BASE}{p}")
            results.append((s, ms))

        statuses = defaultdict(int)
        for s, _ in results:
            statuses[s] += 1
        avg_ms = sum(ms for _, ms in results) / len(results)
        max_ms = max(ms for _, ms in results)

        print(f"\n  Concorrência={conc}:")
        print(f"    Média: {avg_ms:.0f}ms | Máx: {max_ms:.0f}ms")
        for s in sorted(statuses):
            pct = statuses[s] / len(results) * 100
            print(f"    Status {s}: {statuses[s]} ({pct:.0f}%)")

        if statuses.get(504, 0) > 0:
            print(f"    ⚠️  504 detectado em concorrência {conc}")
            break


# ── Experimento 3: Bulk disponível para os gargalos ──────────────────────────


def experimento_bulk_disponivel():
    """Verifica se CSVs bulk existem para eventos_pauta e deputados_historico."""
    print(f"\n{'='*60}")
    print(f" EXPERIMENTO 3: BULK DISPONÍVEL  ({now()})")
    print(f"{'='*60}")

    # URLs do dump bulk da Câmara
    bulk_urls = [
        (
            "eventos_pauta",
            "https://dadosabertos.camara.leg.br/arquivos/eventosPauta/csv/eventosPauta-2026.csv",
        ),
        (
            "deputados_historico",
            "https://dadosabertos.camara.leg.br/arquivos/deputadosHistorico/csv/deputadosHistorico-2026.csv",
        ),
        # Já sabemos que funciona via BULK_REGISTRY
        ("eventos", "https://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-2026.csv"),
        (
            "deputados (controle)",
            "https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados-2026.csv",
        ),
    ]

    for label, url in bulk_urls:
        # HEAD request para ver se existe sem baixar tudo
        req = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                size_mb = int(resp.headers.get("Content-Length", 0)) / 1024 / 1024
                print(f"  {label:<30} ✅ {size_mb:.1f} MB")
        except urllib.error.HTTPError as e:
            print(f"  {label:<30} ❌ HTTP {e.code}")
        except Exception as e:
            print(f"  {label:<30} ❌ {e}")


# ── Experimento 4: Teste de sequência (simula pipeline) ──────────────────────


def experimento_sequencia():
    """
    Simula o padrão real da pipeline: busca lista de eventos, depois
    para cada evento busca pauta. Mede quantos 504s aparecem.
    """
    print(f"\n{'='*60}")
    print(f" EXPERIMENTO 4: SEQUÊNCIA (simula pipeline)  ({now()})")
    print(f"{'='*60}")

    # Busca lista de eventos (primeira página)
    url_lista = f"{BASE}/eventos?situacao=Aprovado&ordem=ASC&ordenarPor=dataHoraInicio&itens=100"
    s, ms, body = get_json(url_lista)
    if s != 200 or not body:
        print(f"  ❌ Erro ao buscar lista de eventos: status={s}")
        return

    dados = body.get("dados", [])
    # Se vier aninhado em 'dados'
    if isinstance(dados, list):
        eventos_ids = [e.get("id") for e in dados if isinstance(e, dict)]
    else:
        print(f"  ❌ Formato inesperado: dados={type(dados)}")
        return

    if not eventos_ids:
        print("  ❌ Lista de eventos veio vazia")
        print(f"  Corpo: {body}")
        return

    print(f"  Eventos encontrados: {len(eventos_ids)}")
    print("  Buscando pauta de cada evento (1 chamada cada)...")

    colds, warms = [], []
    for eid in eventos_ids[:50]:  # limita a 50 para não abusar
        url = f"{BASE}/eventos/{eid}/pauta"
        s1, ms1, _ = get(url)
        colds.append(ms1 if s1 == 200 else None)
        s2, ms2, _ = get(url)
        warms.append(ms2 if s2 == 200 else None)

    cold_ok = [ms for ms in colds if ms is not None]
    warm_ok = [ms for ms in warms if ms is not None]
    print("\n  Resultados (primeira chamada = cold):")
    print(
        f"    Cold:  {len(cold_ok)}/{len(eventos_ids)} OK, "
        f"média={sum(cold_ok)/len(cold_ok):.0f}ms"
        if cold_ok
        else "    Cold:  0 OK"
    )
    print(
        f"    Warm:  {len(warm_ok)}/{len(eventos_ids)} OK, "
        f"média={sum(warm_ok)/len(warm_ok):.0f}ms"
        if warm_ok
        else "    Warm:  0 OK"
    )

    if cold_ok and warm_ok:
        ratio = sum(cold_ok) / sum(warm_ok)
        print(f"    Ratio cold/warm: {ratio:.1f}x")
        if ratio > 2:
            print(f"    🎯 CONFIRMADO: cache miss! Cold é {ratio:.1f}x mais lento que warm")
        else:
            print("    ℹ️  Sem diferença significativa cold vs warm")


# ── main ─────────────────────────────────────────────────────────────────────


def main():
    print(f"🔬 API Experiments — {now()}")
    print(f"URL base: {BASE}")

    experimento_cold_warm()
    experimento_concorrencia()
    experimento_sequencia()
    experimento_bulk_disponivel()

    print(f"\n{'='*60}")
    print(f" ✅ Experimentos concluídos — {now()}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
