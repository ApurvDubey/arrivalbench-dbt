# ArrivalBench-dbt

Do common dbt incremental-model patterns stay correct when data arrives late,
out of order, duplicated, retried or backfilled?

Status: work in progress. Predictions are pre-registered in
`docs/PREREGISTRATION.md` and committed before any dbt run.

Inspired by ArrivalBench (arXiv:2610.02363), which grades agent-built DuckDB
pipelines under replayable delivery hazards. That paper's code and tasks are
not public. This repo is an independent, dbt-native take on the same idea; it
does not reproduce their numbers.

## How it works

1. A seeded logical event log of versioned property sales defines a single
   correct target table (latest version per sale).
2. Seven delivery schedules (two benign, five hazards) deliver the same events
   in different batches and orders.
3. Five incremental dbt strategies process each batch into their own table.
4. After the last batch, each table is compared with the target.

`src/pysim.py` is an independent pandas implementation of the same strategies,
used to cross-check the dbt results.

## Run

    pip install -r requirements.txt
    python src/pysim.py        # reference simulation
    python src/run_bench.py    # real dbt (dbt-duckdb)
    pytest

## Results (seed 7, 200 sales, 5 batches, DuckDB)

Real dbt run, compared against the pre-registered matrix (P = pass, F = fail):

| strategy | single | stream | late | ooo | dup | retry | backfill |
|---|---|---|---|---|---|---|---|
| append_naive | F | F | F | F | F | F | F |
| delete_insert_nodedup | F | F | F | F | F | F | F |
| upsert_unguarded | P | P | F | F | F | P | P |
| upsert_guarded | P | P | P | P | P | P | P |
| watermark | P | P | F | F | P | P | F |

All 35 cells matched the predictions; there were no surprises. The pandas
reference simulation (`src/pysim.py`) agrees with dbt on every cell.

What this shows: an upsert with no recency guard looks correct on in-order
data and silently overwrites newer rows with older ones when data arrives late,
out of order or as a late duplicate. A watermark filter is idempotent but
drops late and backfilled events. Only the guarded upsert was correct under
every schedule.

## Limits

- Five hand-written strategies, one seeded log, one engine (DuckDB).
- The predictions follow from how each strategy works, so a match is a check
  that the harness is sound, not a discovery.
- No agent-generated arm (the original paper's main subject).
- Not yet run on the real Property Price Register data.
