-- Staging model for ABS CPI data.
-- Light cleaning only: rename to consistent snake_case, cast types,
-- drop redundant/junk columns (there are ~15 columns in raw, most are
-- constant across every row and add no value — e.g. STRUCTURE_ID,
-- DECIMALS, which were all a single repeated value when we inspected
-- the raw pull in week 1).

with source as (

    select * from {{ source('raw', 'abs_cpi') }}

),

renamed as (

    select
        "TIME_PERIOD"::varchar          as time_period,
        "OBS_VALUE"::numeric            as cpi_pct_change_yoy,
        "Measure"                       as measure_label,
        "Region"                        as region,
        "Adjustment Type"               as adjustment_type,
        "Frequency"                     as frequency,
        loaded_at::timestamp            as loaded_at

    from source

)

select * from renamed