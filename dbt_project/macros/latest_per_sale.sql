{% macro latest_per_sale(rel) %}
select sale_id, event_id, updated_at, county, price, not_full_market_price, vat_exclusive
from {{ rel }}
qualify row_number() over (partition by sale_id order by updated_at desc, event_id desc) = 1
{% endmacro %}
