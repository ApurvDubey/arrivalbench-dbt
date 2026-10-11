"""Pure-pandas reference semantics of each strategy.

An independent check on the dbt models: if the dbt result for a cell differs
from this simulation, one of the two has a bug. Also lets the pre-registered
predictions be sanity-checked without running dbt.
"""
from __future__ import annotations

import pandas as pd

from eventlog import COLUMNS, generate, oracle, schedules


def _latest(df: pd.DataFrame) -> pd.DataFrame:
    return (df.sort_values(["sale_id", "updated_at", "event_id"])
              .groupby("sale_id", as_index=False).tail(1))


def step(strategy: str, state: pd.DataFrame | None, batch: pd.DataFrame) -> pd.DataFrame:
    first = state is None
    cur = pd.DataFrame(columns=COLUMNS) if first else state
    if strategy == "append_naive":
        return pd.concat([cur, batch], ignore_index=True)
    if strategy == "delete_insert_nodedup":
        kept = cur[~cur["sale_id"].isin(batch["sale_id"])]
        return pd.concat([kept, batch], ignore_index=True)
    if strategy == "upsert_unguarded":
        inc = _latest(batch)
        kept = cur[~cur["sale_id"].isin(inc["sale_id"])]
        return pd.concat([kept, inc], ignore_index=True)
    if strategy == "upsert_guarded":
        inc = _latest(batch)
        if not first and len(cur):
            m = inc.merge(cur[["sale_id", "updated_at", "event_id"]],
                          on="sale_id", how="left", suffixes=("", "_t"))
            newer = m["updated_at_t"].isna() | (
                (m["updated_at"] > m["updated_at_t"])
                | ((m["updated_at"] == m["updated_at_t"]) & (m["event_id"] > m["event_id_t"])))
            inc = inc[newer.to_numpy()]
        kept = cur[~cur["sale_id"].isin(inc["sale_id"])]
        return pd.concat([kept, inc], ignore_index=True)
    if strategy == "watermark":
        src = batch
        if not first and len(cur):
            src = batch[batch["updated_at"] > cur["updated_at"].max()]
        inc = _latest(src) if len(src) else src
        kept = cur[~cur["sale_id"].isin(inc["sale_id"])]
        return pd.concat([kept, inc], ignore_index=True)
    raise ValueError(strategy)


STRATEGIES = ["append_naive", "delete_insert_nodedup", "upsert_unguarded",
              "upsert_guarded", "watermark"]


def _canon(df: pd.DataFrame) -> list[tuple]:
    """Order-insensitive, dtype-insensitive canonical rows."""
    return sorted(
        (int(r.sale_id), str(r.event_id), pd.Timestamp(r.updated_at).isoformat(),
         str(r.county), round(float(r.price), 2),
         bool(r.not_full_market_price), bool(r.vat_exclusive))
        for r in df[COLUMNS].itertuples(index=False)
    )


def equal(state: pd.DataFrame, target: pd.DataFrame) -> bool:
    return len(state) == len(target) and _canon(state) == _canon(target)


def run_matrix(seed: int = 7) -> dict[tuple[str, str], bool]:
    log = generate(seed)
    target = oracle(log)
    out = {}
    for sched, seq in schedules(log).items():
        for strat in STRATEGIES:
            state = None
            for batch in seq:
                state = step(strat, state, batch)
            out[(strat, sched)] = equal(state, target)
    return out


if __name__ == "__main__":
    m = run_matrix()
    cols = ["single", "stream", "late", "ooo", "dup", "retry", "backfill"]
    print(f"{'strategy':24s}" + "".join(f"{c:>9s}" for c in cols))
    for s in STRATEGIES:
        print(f"{s:24s}" + "".join(f"{'P' if m[(s, c)] else 'F':>9s}" for c in cols))
