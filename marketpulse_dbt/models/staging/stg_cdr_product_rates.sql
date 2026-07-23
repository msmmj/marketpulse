-- Staging model for CDR product rate data.
-- Light cleaning: rename columns, cast rate/comparison_rate to numeric
-- percentages are stored as decimals in the source (e.g. 0.0679 = 6.79%),
-- kept as-is here — conversion to a display percentage happens in the
-- dashboard layer, not baked into the data itself.

with source as (

    select * from {{ source('raw', 'cdr_product_rates') }}

),

renamed as (

    select
        product_id,
        bank,
        rate_component,
        rate_type,
        rate::numeric as rate,
        comparison_rate::numeric as comparison_rate,
        loaded_at::timestamp as loaded_at

    from source
    where rate is not null

)

select * from renamed