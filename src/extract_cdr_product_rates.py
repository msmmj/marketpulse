"""
Extract actual interest rate data from Australian banks' CDR Product
Detail APIs. The /products list endpoint (extract_cdr_products.py)
only returns product metadata (name, category, description) — the
real lending/deposit rate numbers live behind a SEPARATE detail
endpoint per product: GET /products/{productId}.

This means one extra HTTP call per product (~140-200 calls across all
banks combined), which is slower and more prone to individual failures
than the list endpoint — handled the same way as before: one bad call
shouldn't kill the whole run.

CDR rate schema notes (from the official Consumer Data Standards):
- lendingRates: list of rate objects, each with a lendingRateType
  (VARIABLE, FIXED, etc.), and either a top-level "rate" field or a
  "tiers" array of rate tiers (e.g. different rates by balance range).
- depositRates: same shape, with depositRateType instead.
- SIMPLIFICATION: where a rate object only has tiers (no top-level
  rate), we take the first tier's rate as a representative value,
  rather than modelling the full tier structure. Documented here
  deliberately — a real production system would model tiers properly,
  but for this project's comparison-level analysis, one representative
  rate per product is a reasonable, honest simplification.
"""

import re
import time
import requests
import pandas as pd

from extract_cdr_products import BANK_CONFIG

# Cache of negotiated (x-v, x-min-v) per bank for the PRODUCT DETAIL
# endpoint specifically. This is intentionally separate from BANK_CONFIG,
# which holds the versions negotiated for the /products LIST endpoint —
# discovered the hard way that CDR banks can support a different version
# range per endpoint (ANZ's list endpoint: v4-5, its detail endpoint: v6-7).
# Populated automatically at runtime rather than hardcoded, so this
# doesn't need re-diagnosing by hand if a bank changes its supported
# version again in future.
_negotiated_detail_versions: dict[str, tuple[str, str]] = {}


def _parse_supported_version_range(
    error_body: str, headers: dict | None = None
) -> tuple[str, str] | None:
    """Parse the supported version range out of a CDR UnsupportedVersion
    error, trying multiple known phrasings since banks word this
    differently (discovered the hard way — ANZ says 'min = X, max = Y',
    Westpac says 'Versions available: X and Y', and CBA/Suncorp don't
    include a parseable range in the body at all, but do echo the
    supported version in the response's own 'x-v' header).

    Returns (min, max) as strings, or None if nothing usable is found.
    """
    match = re.search(r"min\s*=\s*(\d+),?\s*max\s*=\s*(\d+)", error_body, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)

    match = re.search(r"available:?\s*(\d+)\s*and\s*(\d+)", error_body, re.IGNORECASE)
    if match:
        a, b = int(match.group(1)), int(match.group(2))
        return str(min(a, b)), str(max(a, b))

    if headers and headers.get("x-v"):
        header_version = headers["x-v"]
        return header_version, header_version

    return None


def _extract_representative_rate(rate_obj: dict) -> float | None:
    """Pull a single representative rate value from a CDR rate object,
    handling the top-level-rate vs. tiers-only cases described above.
    """
    if rate_obj.get("rate") is not None:
        try:
            return float(rate_obj["rate"])
        except (TypeError, ValueError):
            return None

    tiers = rate_obj.get("tiers") or []
    if tiers:
        first_tier = tiers[0]
        try:
            return float(first_tier.get("rate"))
        except (TypeError, ValueError):
            return None

    return None


def fetch_product_detail(
    bank_name: str, base_url: str, product_id: str, x_v: str, x_min_v: str
) -> list[dict]:
    """Fetch rate detail for a single product. Returns a list of rate
    rows (a product can have multiple rate entries — e.g. a home loan
    with both a variable and fixed rate option). Returns an empty list
    on any failure rather than raising, matching the pattern used for
    the list endpoint.

    Automatically negotiates the correct API version for THIS endpoint
    (product detail) the first time it's called for a given bank: if
    the initial request gets a 406 UnsupportedVersion error, it parses
    the bank's own stated supported range out of the error body, retries
    once with that range, and caches the working version so subsequent
    products from the same bank don't need to renegotiate.
    """
    if bank_name in _negotiated_detail_versions:
        x_v, x_min_v = _negotiated_detail_versions[bank_name]

    url = f"{base_url}/{product_id}"
    headers = {"Accept": "application/json", "x-v": x_v, "x-min-v": x_min_v}

    try:
        resp = requests.get(url, headers=headers, timeout=20)

        if resp.status_code == 406 and bank_name not in _negotiated_detail_versions:
            version_range = _parse_supported_version_range(resp.text, resp.headers)
            if version_range:
                new_min_v, new_max_v = version_range
                _negotiated_detail_versions[bank_name] = (new_max_v, new_min_v)
                print(
                    f"[INFO] {bank_name} detail endpoint negotiated to "
                    f"x-v={new_max_v}, x-min-v={new_min_v}"
                )
                headers = {
                    "Accept": "application/json",
                    "x-v": new_max_v,
                    "x-min-v": new_min_v,
                }
                resp = requests.get(url, headers=headers, timeout=20)

        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as e:
        print(f"[WARN] {bank_name} product {product_id} detail failed: {e}")
        return []

    data = payload.get("data", {})
    rows = []

    for lending_rate in data.get("lendingRates", []) or []:
        rows.append(
            {
                "product_id": product_id,
                "bank": bank_name,
                "rate_component": "LENDING",
                "rate_type": lending_rate.get("lendingRateType"),
                "rate": _extract_representative_rate(lending_rate),
                "comparison_rate": lending_rate.get("comparisonRate"),
            }
        )

    for deposit_rate in data.get("depositRates", []) or []:
        rows.append(
            {
                "product_id": product_id,
                "bank": bank_name,
                "rate_component": "DEPOSIT",
                "rate_type": deposit_rate.get("depositRateType"),
                "rate": _extract_representative_rate(deposit_rate),
                "comparison_rate": None,
            }
        )

    return rows


def fetch_all_product_rates(
    products_df: pd.DataFrame, config: dict = BANK_CONFIG
) -> pd.DataFrame:
    """Given a DataFrame of products (must have product_id and bank
    columns, e.g. from extract_cdr_products.fetch_all_banks()), fetch
    rate detail for every product and return a flat DataFrame of rates.

    This makes one HTTP call PER PRODUCT — noticeably slower than the
    list endpoint. A short delay between calls is added to be polite
    to each bank's API rather than hammering it with rapid requests.
    """
    all_rows = []

    for _, product in products_df.iterrows():
        bank_name = product["_bank"] if "_bank" in product else product["bank"]
        product_id = (
            product["productId"] if "productId" in product else product["product_id"]
        )

        if bank_name not in config:
            continue

        base_url = config[bank_name]["url"]
        x_v = config[bank_name]["x-v"]
        x_min_v = config[bank_name]["x-min-v"]

        rows = fetch_product_detail(bank_name, base_url, product_id, x_v, x_min_v)
        all_rows.extend(rows)

        time.sleep(0.2)  # be polite between calls

    return pd.DataFrame(all_rows)


if __name__ == "__main__":
    # Standalone test: fetch products first, then their rates.
    from extract_cdr_products import fetch_all_banks

    products = fetch_all_banks()
    print(f"Fetched {len(products)} products, now fetching rate detail...")

    rates = fetch_all_product_rates(products)
    print(rates.head(20))
    print(f"\nTotal rate rows retrieved: {len(rates)}")