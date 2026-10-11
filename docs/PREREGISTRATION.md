# Pre-registration (written before any run)

Method adapted from ArrivalBench (arXiv:2610.02363), which tests agent-built
pipelines under replayable delivery hazards. That paper's code and tasks are
not public, so this is an independent, dbt-native implementation of the idea,
not a reproduction of its numbers.

## Invariant

A logical event log L (versioned sale events, seeded, unique timestamps) has a
deterministic target state: the latest version per `sale_id`, ordered by
`(updated_at, event_id)`. A pipeline is **correct under a schedule** if, after
the final batch, its table equals that target state exactly.

## Execution contract

Each batch is delivered into a replaced landing table `stg_batch` (no
cumulative history). The dbt model runs once per batch against a persistent
table. Strategies cannot read past deliveries except through their own target.

## Schedules

| id | description | role |
|---|---|---|
| single | whole log, one batch, in order | benign control |
| stream | 5 batches in time order | benign control |
| late | batches 1..4, then batch 0 | hazard: late arrival |
| ooo | batches in reverse order | hazard: out-of-order |
| dup | stream, then batch 0 again | hazard: late duplicate delivery |
| retry | each batch executed twice in a row | hazard: crash and retry |
| backfill | batches 1..4, then the full log in one batch | hazard: backfill |

## Strategies (all incremental dbt models)

| id | what it does |
|---|---|
| append_naive | append every incoming row |
| delete_insert_nodedup | delete+insert on `sale_id`, no in-batch dedup |
| upsert_unguarded | latest-in-batch, delete+insert on `sale_id`, no recency guard |
| upsert_guarded | as above, but only replace a row if incoming is newer |
| watermark | only process rows with `updated_at` > max in target |

## Predicted outcomes (P = pass, F = fail)

| strategy | single | stream | late | ooo | dup | retry | backfill |
|---|---|---|---|---|---|---|---|
| append_naive | F | F | F | F | F | F | F |
| delete_insert_nodedup | F | F | F | F | F | F | F |
| upsert_unguarded | P | P | F | F | F | P | P |
| upsert_guarded | P | P | P | P | P | P | P |
| watermark | P | P | F | F | P | P | F |

`append_naive` and `delete_insert_nodedup` are expected to fail the benign
controls. Those are ordinary incrementality bugs and are excluded from the
temporal-failure analysis, following the paper's benign-control logic.

## Primary metric

Among strategies that pass both benign controls: the share of hazard
schedules failed (the "silent failure rate under time"). Reported per
strategy with counts, not as a pooled percentage. Zero observed failures are
reported with a rule-of-three upper bound, not as certainty.

## What would falsify this

Any cell that differs from the table above is reported as a surprise, with the
cause investigated, not silently corrected.

## Known limits

One synthetic log shape, one engine (DuckDB), five hand-written strategies.
The agent-generated arm of the original paper is not part of this study.
