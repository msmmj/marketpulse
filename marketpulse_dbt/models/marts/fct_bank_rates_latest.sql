-- Rates mart: latest known rate snapshot per product/rate-type,
-- joined against the product mart for name/category context.
-- This is the table the dashboard queries for rate comparisons.

with rates_staged as (

    select * from {{ ref('stg_cdr_product_rates') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by product_id, bank, rate_component, rate_type
            order by loaded_at desc
        ) as rn

    from rates_staged

),

latest_rates as (

    select
        product_id,
        bank,
        rate_component,
        rate_type,
        rate,
        comparison_rate,
        loaded_at as snapshot_loaded_at
    from ranked
    where rn = 1

),

products as (

    select * from {{ ref('fct_bank_products_latest') }}

)

select
    r.product_id,
    r.bank,
    p.product_name,
    p.product_category,
    r.rate_component,
    r.rate_type,
    r.rate,
    r.comparison_rate,
    r.snapshot_loaded_at

from latest_rates r
left join products p
    on r.product_id = p.product_id
    and r.bank = p.bank