from pathlib import Path

import duckdb

dl = Path("data/datalake")
conn = duckdb.connect()

silver_domains = sorted([d.name for d in (dl / "silver").iterdir() if d.is_dir()])

print(f"{'domain':<30} {'silver':>12} {'gold':>12}")
print("-" * 56)

ts, tg = 0, 0
for dom in silver_domains:
    s = conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('{dl}/silver/{dom}/*.parquet')"
    ).fetchone()[0]
    gf = dl / "gold" / dom / f"{dom}.parquet"
    if gf.exists():
        g = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{gf}')").fetchone()[0]
    else:
        g = 0
    ts += s
    tg += g
    print(f"{dom:<30} {s:>12,} {g:>12,}")

print("-" * 56)
print(f"{'TOTAL':<30} {ts:>12,} {tg:>12,}")

conn.close()
