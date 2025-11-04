"""
Data processing utilities for the packing competitor analysis dashboard.
This module contains all data loading, processing, and analysis functions.
"""

import json, re, pandas as pd, pint, plotly.express as px, os
import streamlit as st
from rapidfuzz import fuzz
from typing import Optional
from .utils import build_product_record
from .fuzzy_matching import (
    normalize_capacity_fuzzy,
    fuzzy_product_match,
    get_capacity_bracket,
    group_products_by_capacity,
    filter_products_by_price,
    filter_products_by_search,
    get_similarity_summary,
    find_similar_products_with_capacity_binning,
)

# Initialize unit registry for capacity normalization
ureg = pint.UnitRegistry()


@st.cache_data
def load_data():
    """Load and process all company data"""
    companies = {}

    if os.path.isfile("processed_data/processed_data_new.json"):
        with open("processed_data/processed_data_new.json", "r") as pd:
            loaded_pd = json.load(pd)
            companies["Cary Company"] = [
                c for c in loaded_pd if c["company"] == "Cary Company"
            ]
            companies["Berlin Packaging"] = [
                b for b in loaded_pd if b["company"] == "Berlin Packaging"
            ]
            companies["TricorBraun"] = [
                t for t in loaded_pd if t["company"] == "TricorBraun"
            ]
            return companies

    # Load Berlin Packaging data
    try:
        with open("demo_batch_data/berlin_packing_data.json", "r") as f:
            berlin_data = json.load(f)
            companies["Berlin Packaging"] = process_berlin_data(berlin_data)
    except FileNotFoundError:
        print("Warning: Berlin Packaging data not found. Skipping this company.")
        companies["Berlin Packaging"] = []

    # Load Cary Company data
    try:
        with open("demo_batch_data/cary_company_data.json", "r") as f:
            cary_data = json.load(f)
            companies["Cary Company"] = process_cary_data(cary_data)
    except FileNotFoundError:
        print("Warning: Cary Company data not found. Skipping this company.")
        companies["Cary Company"] = []

    # Load TricorBraun data
    try:
        with open("demo_batch_data/tricorbraun_data.json", "r") as f:
            tricor_data = json.load(f)
            companies["TricorBraun"] = process_tricor_data(tricor_data)
    except FileNotFoundError:
        print("Warning: TricorBraun data not found. Skipping this company.")
        companies["TricorBraun"] = []

    # Filter out empty companies
    companies = {k: v for k, v in companies.items() if v}

    if not companies:
        raise FileNotFoundError(
            "No data files found. Please ensure the JSON data files are in the demo_batch_data/ directory."
        )

    return companies


def process_berlin_data(data):
    """Process Berlin Packaging data into standardized format"""
    processed = []
    for item in data:
        if not item:
            continue

        # Extract capacity and unit from normalized data
        product_normalised_data = item.get("product_normalised_data", {})
        original_uom, original_capacity, normalised_uom, normalised_value = (
            get_normalised_data(product_normalised_data)
        )
        # Extract pricing
        packing_unit_capacity = item.get("product_specs", {}).get(
            "Case Qty"
        ) or item.get("product_specs", {}).get("Pallet Qty")
        pricing = extract_pricing_data(
            "berlin", item.get("product_sell_uom", []), packing_unit_capacity
        )
        record = build_product_record(
            company="Berlin Packaging",
            item=item,
            pricing=pricing,
            normalised=(
                original_uom,
                original_capacity,
                normalised_uom,
                normalised_value,
            ),
            sell_uom_key="product_sell_uom",
            spec_keys={
                "color": "Color",
                "material": "Material Type",
                "shape": "Shape",
                "category": "Material Group",
                "closure_type": "Neck Finish",
                "neck_finish": "Cap Size",
            },
            availability_keys=[
                ("product_availability", "in_stock"),
                ("product_availability", "expected_ship"),
            ],
            url_key="product_url",
            extras={
                "items_per_unit": item.get("product_specs", {}).get("Case Qty", "")
                or item.get("product_specs", {}).get("Pallet Qty", ""),
            },
        )

        # market segment override using categorization helper
        record["market_segment"] = categorize_product(
            item.get("product_name", ""), item.get("product_description", "")
        )
        # default stock text if still empty
        if not record.get("stock"):
            record["stock"] = "Special Order Item"

        processed.append(record)
    return processed


def process_cary_data(data):
    """Process Cary Company data into standardized format"""
    processed = []
    for item in data:
        if not item:
            continue

        # Extract capacity and unit from normalized data
        product_normalised_data = item.get("product_normalized_data", {})
        original_uom, original_capacity, normalised_uom, normalised_value = (
            get_normalised_data(product_normalised_data)
        )
        packing_details = item.get("product_packing_details", {})
        product_notes = item.get("product_notes", [])
        pricing = extract_pricing_data(
            "cary", item.get("product_sell_uom", []), packing_details, product_notes
        )
        record = build_product_record(
            company="Cary Company",
            item=item,
            pricing=pricing,
            normalised=(
                original_uom,
                original_capacity,
                normalised_uom,
                normalised_value,
            ),
            sell_uom_key="product_sell_uom",
            spec_keys={
                "color": "Color",
                "material": "Material",
                "shape": "Style",
                "category": "Material",
                "closure_type": "Neck Finish",
                "neck_finish": "Neck Finish",
                "product_origin": "Country of Manufacture",
            },
            availability_keys=[("product_availability", "availability_text")],
            url_key="product_url",
            extras={
                "product_industry": item.get("product_specs", {}).get("Industries", ""),
                "product_description": item.get("product_description", ""),
            },
        )
        record["market_segment"] = categorize_product(
            item.get("product_name", ""),
            item.get("product_specs", {}).get("Industries", ""),
            item.get("product_description", ""),
        )
        if not record.get("stock"):
            record["stock"] = "N/A"
        processed.append(record)
    return processed


def process_tricor_data(data):
    """Process TricorBraun data into standardized format"""
    processed = []
    for item in data:
        if not item:
            continue

        # Extract capacity and unit from normalized data
        product_normalised_data = item.get("product_normalised_data", {})
        original_uom, original_capacity, normalised_uom, normalised_value = (
            get_normalised_data(product_normalised_data)
        )

        # Extract pricing
        items_per_unit = item.get("product_specs", {}).get("items_per_unit", "") or ""
        items_per_unit_match = re.search(r"(\d+)", items_per_unit)
        items_per_unit_value = (
            int(items_per_unit_match.group(1)) if items_per_unit_match else 1
        )
        pricing = extract_pricing_data("tricor", item.get("product_selluom", []))
        record = build_product_record(
            company="TricorBraun",
            item=item,
            pricing=pricing,
            normalised=(
                original_uom,
                original_capacity,
                normalised_uom,
                normalised_value,
            ),
            sell_uom_key="product_selluom",
            spec_keys={
                "color": "Color",
                "material": "Material",
                "shape": "Shape",
                "category": "Material",
                "closure_type": "Neck Finish",
                "neck_finish": "Neck Finish",
                "product_origin": "Country of Origin",
            },
            availability_keys=[("product_availability", "availability_text")],
            url_key="product_url",
            extras={"items_per_unit": items_per_unit_value},
        )
        record["market_segment"] = categorize_product(
            item.get("product_name", ""),
            item.get("product_description", ""),
        )
        processed.append(record)
    return processed


def get_normalised_data(product_normalised_data):
    """Extract normalized capacity and unit data"""
    if product_normalised_data:
        product_original_uom = product_normalised_data.get("product_capacity_uom")
        product_original_capacity = product_normalised_data.get(
            "product_capacity_value"
        )

        product_normalised_uom = product_normalised_data.get("normalized_capacity_uom")
        product_normalised_value = product_normalised_data.get(
            "normalized_capacity_value"
        )

        return (
            product_original_uom,
            product_original_capacity,
            product_normalised_uom,
            product_normalised_value,
        )

    return "N/A", 0, "N/A", 0


# --- Shared Utilities ---
def parse_float(value):
    if not value:
        return 0.0
    value = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_count(value):
    if not value:
        return 0
    try:
        return float(re.sub(r"[^\d.]", "", str(value)))
    except ValueError:
        return 0


# --- Berlin Packaging ---
def extract_berlin_pricing(sell_uom, packing_unit_quantity: Optional[str]):
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    try:
        packing_unit_count = (
            float(re.sub(r"[^\d.]", "", packing_unit_quantity))
            if packing_unit_quantity
            else None
        )
    except ValueError:
        packing_unit_count = None

    breaks = []
    unit_prices = []
    current_unit = None
    current_unit_qty = None

    for tier in sell_uom:
        qty_range = tier.get("qty_range")
        price_per_packing_str = tier.get("price")
        price_per_unit_str = tier.get("price_per_unit")
        is_header = str(tier.get("header", "false")).lower() == "true"

        if is_header:
            match = re.match(
                r"(\w+)\s*\(Qty\s*([\d,]+)\)", qty_range or "", re.IGNORECASE
            )
            if match:
                current_unit = match.group(1).title()
                current_unit_qty = float(match.group(2).replace(",", ""))
                if not packing_unit_count:
                    packing_unit_count = current_unit_qty
            else:
                current_unit = (qty_range or "").title()
                current_unit_qty = 1.0
            continue

        price_per_packing = parse_float(price_per_packing_str)
        price_per_unit = parse_float(price_per_unit_str)

        if not price_per_unit_str:
            if price_per_packing > 10 and packing_unit_count > 0:
                price_per_unit = round(price_per_packing / packing_unit_count, 4)
            else:
                price_per_unit = price_per_packing

        if price_per_unit == 0 and price_per_packing > 0 and packing_unit_count > 0:
            price_per_unit = round(price_per_packing / packing_unit_count, 4)

        unit_prices.append(price_per_unit)
        breaks.append(
            {
                "quantity_of_packing": qty_range,
                "type_of_packing": current_unit,
                "price_per_packing": price_per_packing,
                "price_per_item": price_per_unit,
                "unit_quantity": current_unit_qty,
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0
    return {"base_price": base_price, "breaks": breaks}


def extract_cary_pricing(sell_uom, packing_details=None, product_notes=None):
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    items_per_case = 0
    items_per_pallet = 0

    # Extract counts from product_notes
    if product_notes:
        joined = " ".join(product_notes).lower()
        case_match = re.search(r"(\d+)\s?(?:per\s?(?:case|box|carton))", joined)
        pallet_match = re.search(r"(\d+)\s?(?:per\s?pallet)", joined)
        if case_match:
            items_per_case = float(case_match.group(1))
        if pallet_match:
            items_per_pallet = float(pallet_match.group(1))

    # Fallback to packing_details
    def parse_count(value):
        if not value:
            return 0
        m = re.search(r"\d+", str(value))
        return float(m.group()) if m else 0

    def parse_float(value):
        if not value:
            return 0.0
        return float(re.sub(r"[^\d.]", "", str(value)))

    if not items_per_case and packing_details:
        items_per_case = parse_count(packing_details.get("Case Pack"))
    if not items_per_pallet and packing_details:
        items_per_pallet = parse_count(packing_details.get("Pallet Pack"))

    breaks = []
    unit_prices = []

    for tier in sell_uom:
        qty_str = tier.get("qty", "")
        if qty_str.lower() == "quantity":
            continue

        unit = (tier.get("unit") or "").strip().lower().rstrip(".")
        price_value = parse_float(tier.get("price"))
        price_per_unit = 0.0

        if unit == "case" and items_per_case > 0:
            price_per_unit = round(price_value / items_per_case, 4)
            unit_prices.append(price_per_unit)
            breaks.append(
                {
                    "quantity_of_packing": qty_str,
                    "type_of_packing": "case",
                    "price_per_packing": price_value,
                    "price_per_item": price_per_unit,
                }
            )
        elif unit == "pallet" and items_per_pallet > 0:
            price_per_unit = round(price_value / items_per_pallet, 4)
            unit_prices.append(price_per_unit)
            breaks.append(
                {
                    "quantity_of_packing": qty_str,
                    "type_of_packing": "pallet",
                    "price_per_packing": price_value,
                    "price_per_item": price_per_unit,
                }
            )
        elif unit in ["ea", "each", "piece", ""]:
            price_per_unit = round(price_value, 4)
            # Only return derived case or pallet entry
            if items_per_case > 0:
                breaks.append(
                    {
                        "quantity_of_packing": qty_str,
                        "type_of_packing": "case",
                        "unit_quantity": items_per_case,
                        "price_per_packing": round(price_per_unit * items_per_case, 4),
                        "price_per_item": price_per_unit,
                    }
                )
            elif items_per_pallet > 0:
                breaks.append(
                    {
                        "quantity_of_packing": qty_str,
                        "type_of_packing": "pallet",
                        "unit_quantity": items_per_pallet,
                        "price_per_packing": round(
                            price_per_unit * items_per_pallet, 4
                        ),
                        "price_per_item": price_per_unit,
                    }
                )
            unit_prices.append(price_per_unit)

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0
    return {"base_price": base_price, "breaks": breaks}


# --- TricorBraun ---
def extract_tricor_pricing(selluom):
    if not selluom:
        return {"base_price": 0, "breaks": []}

    breaks = []
    unit_prices = []

    for item in selluom:
        qty_text = item.get("qty_range") or ""
        qty_match = re.search(r"(\d+)", qty_text)
        qty = int(qty_match.group(1)) if qty_match else 1

        unit = (item.get("unit") or "").strip()
        price = parse_float(item.get("price"))
        price_per_unit = parse_float(item.get("price_per_unit"))

        if unit.lower() == "piece" and not price_per_unit:
            price_per_unit = price
        if not price_per_unit and price > 0 and qty > 0:
            price_per_unit = round(price / qty, 4)

        if price_per_unit > 0:
            unit_prices.append(price_per_unit)

        breaks.append(
            {
                "quantity_of_packing": qty,
                "type_of_packing": unit,
                "price_per_packing": price,
                "price_per_item": price_per_unit,
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0
    return {"base_price": base_price, "breaks": breaks}


# --- Dispatcher ---
def extract_pricing_data(company_name, *args, **kwargs):
    name = company_name.lower()
    if "berlin" in name:
        return extract_berlin_pricing(*args, **kwargs)
    elif "cary" in name:
        return extract_cary_pricing(*args, **kwargs)
    elif "tricor" in name:
        return extract_tricor_pricing(*args, **kwargs)
    return {"base_price": 0, "breaks": []}


def categorize_product(product_name, product_description, product_indusrty=""):
    """Categorize product into market segment based on name"""
    if not product_name:
        return "General"

    name_lower = (
        product_name.lower() + product_indusrty.lower()
        or "" + product_description.lower()
        or ""
    )

    if any(word in name_lower for word in ["pharma", "medical", "dropper", "vial"]):
        return "Pharmaceutical"
    elif any(
        word in name_lower for word in ["beer", "wine", "liquor", "spirit", "alcohol"]
    ):
        return "Beverage"
    elif any(word in name_lower for word in ["sauce", "condiment", "dressing", "food"]):
        return "Food & Condiments"
    elif any(
        word in name_lower for word in ["cosmetic", "beauty", "skincare", "perfume"]
    ):
        return "Cosmetics"
    else:
        return "General"
