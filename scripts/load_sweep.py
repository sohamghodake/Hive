"""Sweep the run-pipeline load test over workers × concurrency.

Each worker is a separate load_test.py process — its own engine and pool, like a
separate API worker — and they run at the same time. Through PgBouncer by
default; --direct adds the same load straight to Postgres for comparison.
Uses the stub LLM, so it costs no tokens.

    docker compose run --rm --no-deps -v "$PWD:/app" --user "$(id -u):$(id -g)" -e HOME=/tmp \\
        api python scripts/load_sweep.py --direct
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals._util import pct, save  # noqa: E402

DIRECT_URL = os.getenv(
    "MIGRATION_DATABASE_URL", "postgresql+asyncpg://hive:hivepass@postgres:5432/hive"
)


async def one_config(workers: int, concurrency: int, runs: int, direct: bool) -> dict:
    env = dict(os.environ)
    if direct:
        env["DATABASE_URL"] = DIRECT_URL
    script = str(Path(__file__).with_name("load_test.py"))
    procs = [
        await asyncio.create_subprocess_exec(
            sys.executable, script, "--runs", str(runs), "--concurrency", str(concurrency), "--json",
            env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        for _ in range(workers)
    ]
    outs = []
    for p in procs:
        stdout, stderr = await p.communicate()
        lines = [ln for ln in stdout.decode().splitlines() if ln.startswith("{")]
        if not lines:  # the worker itself crashed, e.g. could not connect at all
            outs.append({"completed": 0, "runs": runs, "wall_s": 0, "latencies": [], "peak_backends": 0,
                         "errors": [stderr.decode().strip().splitlines()[-1][:160] if stderr else "no output"]})
        else:
            outs.append(json.loads(lines[-1]))

    latencies = [x for o in outs for x in o["latencies"]]
    wall = max(o["wall_s"] for o in outs) or 1
    completed = sum(o["completed"] for o in outs)
    return {
        "path": "direct" if direct else "pgbouncer",
        "workers": workers, "concurrency": concurrency, "runs": workers * runs,
        "completed": completed,
        "runs_per_s": round(completed / wall, 1),
        "p50_s": round(pct(latencies, 50), 2) if latencies else None,
        "p95_s": round(pct(latencies, 95), 2) if latencies else None,
        "peak_backends": max(o["peak_backends"] for o in outs),
        "errors": sorted({e for o in outs for e in o.get("errors", [])})[:2],
    }


async def main(direct: bool) -> None:
    grid = [(w, c) for w in (1, 2, 4) for c in (10, 50, 100)]
    rows = []
    for workers, concurrency in grid:
        rows.append(await one_config(workers, concurrency, max(50, 2 * concurrency), direct=False))
        print(json.dumps(rows[-1]), flush=True)
    if direct:
        for workers in (1, 2, 4):
            rows.append(await one_config(workers, 50, 100, direct=True))
            print(json.dumps(rows[-1]), flush=True)

    path = save("load_sweep.json", {"stub_llm_latency_s": 0.4, "rows": rows})
    print("\n| path | workers | concurrency | runs | completed | runs/s | p50 s | p95 s | peak PG backends |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['path']} | {r['workers']} | {r['concurrency']} | {r['runs']} | {r['completed']} | "
              f"{r['runs_per_s']} | {r['p50_s']} | {r['p95_s']} | {r['peak_backends']} |")
    for r in rows:
        if r["errors"]:
            print(f"  {r['path']} {r['workers']}x{r['concurrency']}: {r['errors'][0]}")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--direct", action="store_true", help="also run 1/2/4 workers straight to Postgres")
    asyncio.run(main(ap.parse_args().direct))
