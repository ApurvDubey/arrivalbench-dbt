{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='sale_id') }}
with src as (
    select * from {{ source('landing', 'stg_batch') }}
    {% if is_incremental() %}
    where updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
)
{{ latest_per_sale('src') }}
