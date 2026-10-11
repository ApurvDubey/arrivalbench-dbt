{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='sale_id') }}
with incoming as (
    {{ latest_per_sale(source('landing', 'stg_batch')) }}
)
select i.sale_id, i.event_id, i.updated_at, i.county, i.price,
       i.not_full_market_price, i.vat_exclusive
from incoming i
{% if is_incremental() %}
left join {{ this }} t on t.sale_id = i.sale_id
where t.sale_id is null
   or (i.updated_at, i.event_id) > (t.updated_at, t.event_id)
{% endif %}
