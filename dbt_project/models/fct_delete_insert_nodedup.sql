{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='sale_id') }}
select sale_id, event_id, updated_at, county, price, not_full_market_price, vat_exclusive
from {{ source('landing', 'stg_batch') }}
