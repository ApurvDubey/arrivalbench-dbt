{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='sale_id') }}
{{ latest_per_sale(source('landing', 'stg_batch')) }}
