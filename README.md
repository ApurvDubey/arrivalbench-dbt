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
