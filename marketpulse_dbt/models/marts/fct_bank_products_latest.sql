-- Product mart: latest known snapshot per bank product.
-- The staging model carries every historical pipeline run (raw data is
-- append-only, by design — see NOTES.md). This mart answers the actual
-- dashboard question: "what does each bank currently offer, as of our
-- most recent successful pull for that specific product?"
--
-- Note: if a bank's API was temporarily unavailable on the most recent
-- run (this has happened with Westpac — see README known limitations),
-- that bank's products here will reflect their last successful pull,
-- not necessarily today. That's a deliberate, honest choice: showing
-- slightly-stale data beats dropping a bank's products from the mart
-- entirely just because one run had a flaky upstream call.

with staged as (

    select * from {{ ref('stg_cdr_products') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by product_id, bank
            order by loaded_at desc
        ) as rn

    from staged

)

select
    product_id,
    bank,
    product_name,
    product_category,
    description,
    is_tailored,
    last_updated,
    effective_from,
    effective_to,
    loaded_at as snapshot_loaded_at

from ranked
where rn = 1