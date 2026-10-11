import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventlog import generate, oracle, schedules, COLUMNS  # noqa: E402


def test_reproducible():
    assert generate(7).equals(generate(7))
    assert not generate(7).equals(generate(8))


def test_unique_timestamps_and_event_ids():
    df = generate(7)
    assert df["updated_at"].is_unique and df["event_id"].is_unique


def test_oracle_one_row_per_sale_and_is_latest():
    df = generate(7)
    o = oracle(df)
    assert o["sale_id"].is_unique and len(o) == df["sale_id"].nunique()
    latest = df.groupby("sale_id")["updated_at"].max().sort_index().to_numpy()
    assert (o.sort_values("sale_id")["updated_at"].to_numpy() == latest).all()


def test_every_event_is_deliverable_in_every_schedule():
    df = generate(7)
    ids = set(df["event_id"])
    import pandas as pd
    for name, seq in schedules(df).items():
        seen = set(pd.concat(seq)["event_id"])
        assert seen == ids, name


def test_log_has_hazard_sensitive_structure():
    df = generate(7)
    multi = df.groupby("sale_id").size()
    assert (multi > 1).sum() > 50      # corrections exist
    assert (multi == 1).sum() > 30     # sales that appear once exist
