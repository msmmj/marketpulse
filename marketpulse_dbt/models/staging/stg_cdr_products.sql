-- Staging model for CDR banking product data.
-- Renames to consistent snake_case and selects only the columns useful
-- for the mart layer. additionalInformation and cardArt were stringified
-- before load (they're nested JSON in the raw API response) — left out
-- here since they're not needed for the rate/product comparison analysis
-- this project is built around; can be added back later if needed.

with source as (

    select * from {{ source('raw', 'cdr_products') }}

),

renamed as (

    select
        "productId"::varchar        as product_id,
        "_bank"::varchar            as bank,
        "name"::varchar             as product_name,
        "productCategory"::varchar  as product_category,
        "description"::varchar      as description,
        "isTailored"::boolean       as is_tailored,
        "lastUpdated"::timestamp    as last_updated,
        "effectiveFrom"::timestamp  as effective_from,
        "effectiveTo"::timestamp    as effective_to,
        loaded_at::timestamp        as loaded_at

    from source

)

select * from renamed