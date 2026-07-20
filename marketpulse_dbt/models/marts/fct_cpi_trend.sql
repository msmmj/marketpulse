-- Finance mart: CPI trend over time.
-- raw.abs_cpi is append-only (same pattern as raw.cdr_products) — every
-- pipeline run adds another full snapshot of the same ~14 months, since
-- ABS doesn't retroactively change published figures often. This mart
-- dedupes to the latest snapshot per time_period, same pattern used in
-- fct_bank_products_latest, before adding the month-over-month trend.

with staged as (

    select * from {{ ref('stg_abs_cpi') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by time_period
            order by loaded_at desc
        ) as rn

    from staged

),

deduped as (

    select
        time_period,
        cpi_pct_change_yoy,
        loaded_at
    from ranked
    where rn = 1

),

ordered as (

    select
        time_period,
        cpi_pct_change_yoy,
        loaded_at,
        lag(cpi_pct_change_yoy) over (order by time_period) as prev_month_cpi_pct_change_yoy

    from deduped
    order by time_period

)

select
    *,
    round(cpi_pct_change_yoy - prev_month_cpi_pct_change_yoy, 2) as month_over_month_shift

from ordered