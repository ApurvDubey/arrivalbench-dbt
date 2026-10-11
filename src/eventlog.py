"""Seeded logical event log, oracle target state, and delivery schedules.

Event shape follows the Irish Residential Property Price Register fields that
matter for correctness: a sale can be re-reported with a corrected price or
flags, so a table of "current sales" must keep the latest version per sale_id.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COLUMNS = [
    "sale_id", "event_id", "updated_at", "county", "price",
    "not_full_market_price", "vat_exclusive",
]
COUNTIES = ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Kerry", "Meath", "Kildare"]
N_BATCHES = 5


def generate(seed: int = 7, n_sales: int = 200, max_versions: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for sale_id in range(1, n_sales + 1):
        n_versions = int(rng.choice([1, 2, 3, max_versions], p=[0.35, 0.30, 0.20, 0.15]))
        county = COUNTIES[int(rng.integers(len(COUNTIES)))]
        price = float(rng.integers(150, 900) * 1000)
        nfmp = bool(rng.random() < 0.08)
        vat = bool(rng.random() < 0.10)
        for v in range(n_versions):
            if v > 0:  # corrections change price and/or flags
                price = float(max(50000.0, price + rng.integers(-30, 31) * 1000))
                if rng.random() < 0.25:
                    nfmp = not nfmp
            rows.append({
                "sale_id": sale_id,
                "event_id": f"{sale_id}-v{v}",
                "county": county,
                "price": price,
                "not_full_market_price": nfmp,
                "vat_exclusive": vat,
            })
    df = pd.DataFrame(rows)
    # Strictly increasing, unique timestamps; versions of one sale stay in order.
    order = df.assign(_r=rng.random(len(df))).sort_values(["_r"]).index
    # Build timestamps by shuffling sales' versions into a global timeline.
    timeline = pd.date_range("2024-01-01", periods=len(df), freq="37min")
    df = df.copy()
    df["updated_at"] = pd.NaT
    # assign timeline slots randomly, then sort each sale's slots ascending
    slots = timeline.to_numpy()[rng.permutation(len(df))]
    df["_slot"] = slots
    df = df.sort_values(["sale_id", "_slot"])
    df["_v"] = df.groupby("sale_id").cumcount()
    df["event_id"] = df["sale_id"].astype(str) + "-v" + df["_v"].astype(str)
    df["updated_at"] = df["_slot"]
    df = df.drop(columns=["_slot", "_v"]).sort_values("updated_at").reset_index(drop=True)
    assert df["updated_at"].is_unique
    return df[COLUMNS]


def oracle(df: pd.DataFrame) -> pd.DataFrame:
    """Target state: latest version per sale_id by (updated_at, event_id)."""
    out = (df.sort_values(["sale_id", "updated_at", "event_id"])
             .groupby("sale_id", as_index=False).tail(1))
    return out.sort_values("sale_id").reset_index(drop=True)[COLUMNS]


def batches(df: pd.DataFrame, n: int = N_BATCHES) -> list[pd.DataFrame]:
    df = df.sort_values("updated_at").reset_index(drop=True)
    edges = np.linspace(0, len(df), n + 1, dtype=int)
    return [df.iloc[edges[i]:edges[i + 1]].reset_index(drop=True) for i in range(n)]


def schedules(df: pd.DataFrame) -> dict[str, list[pd.DataFrame]]:
    b = batches(df)
    full = df.sort_values("updated_at").reset_index(drop=True)
    return {
        "single": [full],
        "stream": list(b),
        "late": b[1:] + [b[0]],
        "ooo": list(reversed(b)),
        "dup": list(b) + [b[0]],
        "retry": [x for batch in b for x in (batch, batch)],
        "backfill": b[1:] + [full],
    }


BENIGN = ("single", "stream")
HAZARDS = ("late", "ooo", "dup", "retry", "backfill")
