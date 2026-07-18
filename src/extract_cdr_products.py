"""
Extract product reference data from Australian banks' Consumer Data Right
(CDR) Product Reference APIs. These endpoints expose no customer data and
require no authentication or accreditation — they're public by design.

Docs: https://consumerdatastandardsaustralia.github.io/standards/

IMPORTANT:
- Each bank requires an `x-v` header specifying the API version, and each
  bank supports a DIFFERENT version range. Version numbers below were
  discovered by reading each bank's 406 error response, which per the CDR
  spec reports the supported version range on a mismatch.
- `x-min-v` tells the bank the lowest version you're willing to accept,
  letting it auto-negotiate down instead of rejecting outright.
- Responses are paginated via a `links.next` field — this script follows
  pagination automatically.
"""
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Each bank supports a different x-v range, discovered via their 406 error
# responses (the CDR spec requires banks to report their supported version
# range on a version mismatch — see the "detail" field of a failed response).
# x-min-v tells the bank the lowest version you're willing to accept, letting
# it auto-negotiate down instead of rejecting outright when x-v doesn't match.
#
# NOTE: AMP is deliberately excluded. Its endpoint returns a 406 version
# negotiation error regardless of the x-v value sent (tried 1, 2, and 3),
# even when the value matches what AMP's own response headers report as
# supported — this points to a bug in AMP's CDR implementation, not a
# request error on our side. Documented and parked rather than chased
# further; the remaining 4 banks provide sufficient coverage for the
# analysis this project is built around.
BANK_CONFIG = {
    "ANZ": {
        "url": "https://api.anz/cds-au/v1/banking/products",
        "x-v": "5",
        "x-min-v": "4",
    },
    "Westpac": {
        "url": "https://digital-api.westpac.com.au/cds-au/v1/banking/products",
        "x-v": "5",
        "x-min-v": "4",
    },
    "CBA": {
        "url": "https://api.commbank.com.au/public/cds-au/v1/banking/products",
        "x-v": "5",
        "x-min-v": "1",
    },
    "Suncorp": {
        "url": "https://id-ob.suncorpbank.com.au/cds-au/v1/banking/products",
        "x-v": "5",
        "x-min-v": "1",
    },
}

# Kept for backward compatibility with fetch_bank_products' default signature
BANK_ENDPOINTS = {name: cfg["url"] for name, cfg in BANK_CONFIG.items()}


def fetch_bank_products(
    bank_name: str, url: str, x_v: str = "3", x_min_v: str = "1"
) -> pd.DataFrame:
    """Fetch all products (following pagination) for a single bank.
    Returns an empty DataFrame and logs a warning if the bank's endpoint
    fails — one unreliable upstream shouldn't kill the whole extraction run.
    """
    headers = {
        "Accept": "application/json",
        "x-v": x_v,
        "x-min-v": x_min_v,
    }
    all_products = []
    next_url = url

    while next_url:
        try:
            resp = requests.get(next_url, headers=headers, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as e:
            print(f"[WARN] {bank_name} failed: {e}")
            break

        products = payload.get("data", {}).get("products", [])
        for p in products:
            p["_bank"] = bank_name
        all_products.extend(products)

        next_url = payload.get("links", {}).get("next")
        if next_url:
            time.sleep(0.5)  # be polite between paginated calls

    return pd.DataFrame(all_products)


def fetch_all_banks(config: dict = BANK_CONFIG) -> pd.DataFrame:
    """Fetch products from every bank in the config dict and combine
    into a single DataFrame, tagging each row with which bank it came from.
    Each bank uses its own negotiated x-v / x-min-v version.
    """
    frames = []
    for bank_name, cfg in config.items():
        print(f"Fetching {bank_name}...")
        df = fetch_bank_products(
            bank_name, cfg["url"], x_v=cfg["x-v"], x_min_v=cfg["x-min-v"]
        )
        if not df.empty:
            frames.append(df)
        else:
            print(f"[WARN] No products retrieved for {bank_name}")

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    df = fetch_all_banks()
    if not df.empty:
        print(df[["_bank", "name", "productId"]].head(20))
        print(f"\nTotal products retrieved: {len(df)}")
    else:
        print("No products retrieved from any bank — check endpoints/headers.")