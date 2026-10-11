{{ config(materialized='incremental', incremental_strategy='append') }}
select sale_id, event_id, updated_at, county, price, not_full_market_price, vat_exclusive
from {{ source('landing', 'stg_batch') }}
