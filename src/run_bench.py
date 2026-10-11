"""Run every strategy under every schedule through real dbt and compare to the oracle.

One DuckDB file per schedule. Per batch: replace landing table stg_batch, then
run all strategy models once (they are independent incremental targets).

Usage: python src/run_bench.py   (needs dbt-core + dbt-duckdb importable)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eventlog import BENIGN, COLUMNS, HAZARDS, generate, oracle, schedules  # noqa: E402
from pysim import STRATEGIES, equal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DBT = ROOT / "dbt_project"
WORK = ROOT / "results" / "work"
MODEL = {s: f"fct_{s}" for s in STRATEGIES}


def dbt_run(db: Path) -> None:
    env = dict(os.environ, ARRIVAL_DB=str(db),
               PYTHONPATH=os.pathsep.join(filter(None, [str(ROOT / ".deps"), os.environ.get("PYTHONPATH", "")])))
    cmd = [sys.executable, "-c", "from dbt.cli.main import cli; cli()",
           "run", "--project-dir", str(DBT), "--profiles-dir", str(DBT),
           "--log-path", str(WORK / "logs"), "--target-path", str(WORK / "target"),
           "--quiet"]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError(f"dbt failed:\n{r.stdout[-1500:]}\n{r.stderr[-800:]}")


def load_batch(db: Path, batch: pd.DataFrame) -> None:
    con = duckdb.connect(str(db))
    con.register("b", batch)
    con.execute("create or replace table main.stg_batch as select * from b")
    con.close()


def read_table(db: Path, model: str) -> pd.DataFrame:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(f"select {', '.join(COLUMNS)} from main.{model}").df()
    finally:
        con.close()


def main(seed: int = 7) -> None:
    log = generate(seed)
    target = oracle(log)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    rows = []
    for sched, seq in schedules(log).items():
        db = WORK / f"{sched}.duckdb"
        for batch in seq:
            load_batch(db, batch)
            dbt_run(db)
        for strat in STRATEGIES:
            t = read_table(db, MODEL[strat])
            rows.append({"strategy": strat, "schedule": sched, "passed": bool(equal(t, target)),
                         "rows": len(t), "target_rows": len(target)})
        print(f"done {sched}", flush=True)
    out = pd.DataFrame(rows)
    (ROOT / "results").mkdir(exist_ok=True)
    out.to_csv(ROOT / "results" / "matrix.csv", index=False)
    cols = ["single", "stream", *HAZARDS]
    piv = out.pivot(index="strategy", columns="schedule", values="passed")[cols]
    print(piv.replace({True: "P", False: "F"}).to_string())
    (ROOT / "results" / "matrix.json").write_text(json.dumps(
        {f"{r.strategy}|{r.schedule}": r.passed for r in out.itertuples()}, indent=2))


if __name__ == "__main__":
    main()
