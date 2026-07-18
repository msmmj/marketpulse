"""
Tests for extract_cdr_products.py using mocked HTTP responses, including
a pagination scenario and a failure scenario (one bank down shouldn't
break the whole run).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import responses  # noqa: E402
from extract_cdr_products import fetch_bank_products, fetch_all_banks  # noqa: E402


@responses.activate
def test_fetch_bank_products_single_page():
    responses.add(
        responses.GET,
        "https://example-bank.com.au/cds-au/v1/banking/products",
        json={
            "data": {"products": [{"productId": "abc123", "name": "Everyday Saver"}]},
            "links": {"next": None},
        },
        status=200,
    )

    df = fetch_bank_products(
        "ExampleBank", "https://example-bank.com.au/cds-au/v1/banking/products"
    )

    assert len(df) == 1
    assert df.iloc[0]["name"] == "Everyday Saver"
    assert df.iloc[0]["_bank"] == "ExampleBank"


@responses.activate
def test_fetch_bank_products_follows_pagination():
    responses.add(
        responses.GET,
        "https://example-bank.com.au/cds-au/v1/banking/products",
        json={
            "data": {"products": [{"productId": "p1", "name": "Product 1"}]},
            "links": {
                "next": "https://example-bank.com.au/cds-au/v1/banking/products?page=2"
            },
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://example-bank.com.au/cds-au/v1/banking/products?page=2",
        json={
            "data": {"products": [{"productId": "p2", "name": "Product 2"}]},
            "links": {"next": None},
        },
        status=200,
    )

    df = fetch_bank_products(
        "ExampleBank", "https://example-bank.com.au/cds-au/v1/banking/products"
    )

    assert len(df) == 2
    assert set(df["name"]) == {"Product 1", "Product 2"}


@responses.activate
def test_fetch_bank_products_handles_failure_gracefully():
    responses.add(
        responses.GET,
        "https://broken-bank.com.au/cds-au/v1/banking/products",
        status=500,
    )

    df = fetch_bank_products(
        "BrokenBank", "https://broken-bank.com.au/cds-au/v1/banking/products"
    )

    # Should return an empty DataFrame rather than raising
    assert df.empty


@responses.activate
def test_fetch_all_banks_skips_failed_bank():
    responses.add(
        responses.GET,
        "https://good-bank.com.au/products",
        json={
            "data": {"products": [{"productId": "g1", "name": "Good Product"}]},
            "links": {"next": None},
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bad-bank.com.au/products",
        status=500,
    )

    df = fetch_all_banks(
        config={
            "GoodBank": {
                "url": "https://good-bank.com.au/products",
                "x-v": "3",
                "x-min-v": "1",
            },
            "BadBank": {
                "url": "https://bad-bank.com.au/products",
                "x-v": "3",
                "x-min-v": "1",
            },
        }
    )

    assert len(df) == 1
    assert df.iloc[0]["_bank"] == "GoodBank"
