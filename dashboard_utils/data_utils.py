"""
Data processing utilities for the packing competitor analysis dashboard.
This module contains all data loading, processing, and analysis functions.
"""

import json
import re
import pandas as pd
import numpy as np
from rapidfuzz import fuzz
import pint
from typing import Dict, List, Any

# Initialize unit registry for capacity normalization
ureg = pint.UnitRegistry()


def load_data():
    """Load and process all company data"""
    companies = {}

    # Load Berlin Packaging data
    try:
        with open("demo_batch_data/berlin_packing_all_data_normalized.json", "r") as f:
            berlin_data = json.load(f)
            companies["Berlin Packaging"] = process_berlin_data(berlin_data)
    except FileNotFoundError:
        print("Warning: Berlin Packaging data not found. Skipping this company.")
        companies["Berlin Packaging"] = []

    # Load Cary Company data
    try:
        with open("demo_batch_data/cary_all_data_normalized.json", "r") as f:
            cary_data = json.load(f)
            companies["Cary Company"] = process_cary_data(cary_data)
    except FileNotFoundError:
        print("Warning: Cary Company data not found. Skipping this company.")
        companies["Cary Company"] = []

    # Load TricorBraun data
    try:
        with open("demo_batch_data/tricorbraun_all_data_normalized.json", "r") as f:
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
        pricing = extract_berlin_pricing(item.get("product_sell_uom", []))

        processed.append(
            {
                "company": "Berlin Packaging",
                "sku": item.get("product_id", "") or "",
                "name": item.get("product_name", "") or "",
                "price": pricing["base_price"],
                "quantity_breaks": pricing["breaks"],
                "sell_uom": item.get("product_sell_uom", []),  # Add raw sell_uom data
                "original_uom": original_uom,
                "original_capacity": original_capacity,
                "normalised_uom": normalised_uom,
                "normalised_capacity": normalised_value,
                "capacity": normalised_value,  # Use normalized capacity for analysis
                "unit": normalised_uom,  # Use normalized unit for analysis
                "color": item.get("product_specs", {}).get("Color ", "") or "",
                "material": item.get("product_specs", {}).get("Material Type ", "")
                or "",
                "shape": item.get("product_specs", {}).get("Shape ", "") or "",
                "category": item.get("product_specs", {}).get("Material Group ", "")
                or "",
                "closure_type": item.get("product_specs", {}).get("Neck Finish ", "")
                or "",
                "market_segment": categorize_product(item.get("product_name", "")),
                "stock": item.get("product_availability", {}).get("in_stock", "")
                or "N/A",
                "url": item.get("product_url", "") or "",
            }
        )
    return processed


def process_cary_data(data):
    """Process Cary Company data into standardized format"""
    processed = []
    for item in data:
        if not item:
            continue

        # Extract capacity and unit from normalized data
        product_normalised_data = item.get("product_normalised_data", {})
        original_uom, original_capacity, normalised_uom, normalised_value = (
            get_normalised_data(product_normalised_data)
        )
        packing_details = item.get("product_packing_details", {})

        product_notes = item.get("product_notes", [])
        case_pack_from_notes = ""
        if product_notes:
            joined_notes = " ".join(product_notes).lower()
            if (
                "Please note, this bottle is packed in a 12x1 Re-Shipper Carton (12 bottles per box)".lower()
                or "Packed in a 12x1 Re-Shipper Carton (12 per box)".lower()
                in joined_notes
            ):
                case_pack_from_notes = "12 ea."

        pricing = extract_cary_pricing(
            item.get("product_sell_uom", []), packing_details, case_pack_from_notes
        )
        processed.append(
            {
                "company": "Cary Company",
                "sku": item.get("product_id", "") or "",
                "name": item.get("product_name", "") or "",
                "price": pricing["base_price"],
                "quantity_breaks": pricing["breaks"],
                "sell_uom": item.get("product_sell_uom", []),  # Add raw sell_uom data
                "original_uom": original_uom,
                "original_capacity": original_capacity,
                "normalised_uom": normalised_uom,
                "normalised_capacity": normalised_value,
                "capacity": normalised_value,  # Use normalized capacity for analysis
                "unit": normalised_uom,  # Use normalized unit for analysis
                "color": item.get("product_specs", {}).get("Color", "") or "",
                "material": item.get("product_specs", {}).get("Material", "") or "",
                "shape": item.get("product_specs", {}).get("Style", "") or "",
                "category": item.get("product_specs", {}).get("Material", "") or "",
                "closure_type": item.get("product_specs", {}).get("Neck Finish", "")
                or "",
                "market_segment": categorize_product(item.get("product_name", "")),
                "stock": "In Stock",  # Default assumption
                "url": item.get("product_url", "") or "",
            }
        )
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
        pricing = extract_tricor_pricing(item.get("product_selluom", []))

        processed.append(
            {
                "company": "TricorBraun",
                "sku": item.get("product_id", "") or "",
                "name": item.get("product_name", "") or "",
                "price": pricing["base_price"],
                "quantity_breaks": pricing["breaks"],
                "sell_uom": item.get(
                    "product_selluom", []
                ),  # Add raw sell_uom data (note: TricorBraun uses 'selluom')
                "original_uom": original_uom,
                "original_capacity": original_capacity,
                "normalised_uom": normalised_uom,
                "normalised_capacity": normalised_value,
                "capacity": normalised_value,  # Use normalized capacity for analysis
                "unit": normalised_uom,  # Use normalized unit for analysis
                "color": item.get("product_specs", {}).get("Color", "") or "",
                "material": item.get("product_specs", {}).get("Material", "") or "",
                "shape": item.get("product_specs", {}).get("Shape", "") or "",
                "category": item.get("product_specs", {}).get("Material", "") or "",
                "closure_type": item.get("product_specs", {}).get("Neck Finish", "")
                or "",
                "market_segment": categorize_product(item.get("product_name", "")),
                "stock": item.get("product_availability", {}).get("in_stock", "") or "",
                "url": item.get("product_url", "") or "",
            }
        )
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


def extract_berlin_pricing(sell_uom):
    """Extract pricing from Berlin Packaging sell_uom data"""
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    breaks = []
    unit_prices = []

    for tier in sell_uom:
        # Extract unit price from price_per_unit field for base_price calculation
        price_per_unit_str = (
            tier.get("price_per_unit")
            if tier.get("price_per_unit") is not None
            else "$0 ea."
        )
        unit_price_str = re.sub(r"[^\d.]", "", price_per_unit_str).rstrip(".")
        unit_price = float(unit_price_str)

        # Extract total price for the quantity range (case/pallet price)
        price_str = tier.get("price", "$0")
        total_price = float(re.sub(r"[^\d.]", "", price_str))

        unit_prices.append(unit_price)

        qty_range = tier.get("qty_range", "1+")
        breaks.append(
            {
                "quantity": qty_range,
                "price": total_price,  # Use total price for case/pallet
                "price_per_unit": tier.get("price_per_unit", ""),
            }
        )

    # Calculate average unit price across all tiers
    base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

    return {"base_price": base_price, "breaks": breaks}


def extract_cary_pricing(sell_uom, packing_details, case_pack_notes):
    """Extract pricing from Cary Company sell_uom data"""
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    items_per_case = ""
    items_per_pallet = ""
    if packing_details:
        items_per_case = packing_details.get("Case Pack", None)
        items_per_pallet = packing_details.get("Pallet Pack", None)

    if not items_per_case:
        items_per_case = case_pack_notes if case_pack_notes else ""

    breaks = []
    unit_prices = []

    for tier in sell_uom:
        # Skip header row
        if tier.get("qty") == "Quantity":
            continue

        price_str = tier.get("price", "$0")
        qty_str = tier.get("qty", "1")

        try:
            price = float(re.sub(r"[^\d.]", "", price_str))
            unit_prices.append(price)
            base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

            if price > 15:
                if price == 56389.0:
                    price = price / 10000
                items = float(items_per_case.replace("ea.", ""))
                price = price / items

            unit_prices.append(price)

            breaks.append(
                {
                    "quantity": qty_str,
                    "price": price,
                    "price_per_unit": price_str,
                }
            )
        except (ValueError, TypeError):
            continue

    # Calculate average unit price across all tiers
    base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

    if base_price > 3:
        items_per_case_float = float(items_per_case.replace("ea.", ""))
        base_price = base_price / items_per_case_float

    return {"base_price": base_price, "breaks": breaks}


def extract_tricor_pricing(selluom):
    """Extract pricing from TricorBraun selluom data"""
    if not selluom:
        return {"base_price": 0, "breaks": []}

    breaks = []
    base_price = 0

    for item in selluom:
        # Extract quantity from qty_range (e.g., "1 Case" -> 1)
        qty_text = item.get("qty_range", "1 Case")
        qty_match = re.search(r"(\d+)", qty_text)
        qty = int(qty_match.group(1)) if qty_match else 1

        # Extract price and convert to float
        price_text = item.get("price", "$0")
        price_match = re.search(r"\$?([\d,]+\.?\d*)", price_text)
        price = float(price_match.group(1).replace(",", "")) if price_match else 0

        # Extract price per unit
        price_per_unit_text = (
            item.get("price_per_unit")
            if item.get("price_per_unit") is not None
            else "$0"
        )
        price_per_unit_match = re.search(r"\$?([\d,]+\.?\d*)", price_per_unit_text)
        price_per_unit = (
            float(price_per_unit_match.group(1).replace(",", ""))
            if price_per_unit_match
            else 0
        )

        # Use the first item as base price
        if not base_price:
            base_price = price_per_unit

        breaks.append(
            {
                "quantity": qty,
                "price": price,
                "price_per_unit": price_per_unit,
                "unit": item.get("unit", "Case"),
            }
        )

    return {"base_price": base_price, "breaks": breaks}


def categorize_product(product_name):
    """Categorize product into market segment based on name"""
    if not product_name:
        return "General"

    name_lower = product_name.lower()

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


def normalize_capacity(value, unit):
    """Normalize capacity to milliliters"""
    try:
        return (value * ureg(unit)).to("milliliter").magnitude
    except:
        return value


def fuzzy_product_match(p1, p2):
    """Calculate fuzzy match score between two products"""
    name_score = fuzz.token_sort_ratio(p1["name"], p2["name"]) / 100

    cap1 = normalize_capacity(p1["capacity"], p1["unit"])
    cap2 = normalize_capacity(p2["capacity"], p2["unit"])
    cap_score = 1 - min(abs(cap1 - cap2) / max(cap1, cap2, 1), 1)

    price_score = 1 - min(
        abs(p1["price"] - p2["price"]) / max(p1["price"], p2["price"], 1), 1
    )

    return 0.5 * name_score + 0.3 * cap_score + 0.2 * price_score


def get_pricing_data_for_chart(companies_data):
    """Extract pricing data for multi-line chart visualization"""
    pricing_data = []

    for company in companies_data.keys():
        company_data = companies_data[company]
        for product in company_data:
            if product["quantity_breaks"]:
                for break_item in product["quantity_breaks"]:
                    pricing_data.append(
                        {
                            "Company": company,
                            "SKU": product["sku"],
                            "Product": product["name"],
                            "Quantity": break_item["quantity"],
                            "Price": break_item["price"],
                        }
                    )

    return pricing_data


def get_capacity_analysis_data(companies_data):
    """Get capacity analysis data with normalized values"""
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    df_all = pd.DataFrame(all_data)

    # Calculate normalized capacity in ml
    df_all["capacity_ml"] = df_all.apply(
        lambda x: normalize_capacity(x["capacity"], x["unit"]), axis=1
    )
    df_all["price_per_100ml"] = df_all["price"] / df_all["capacity_ml"] * 100

    # Create capacity ranges
    df_all["capacity_range"] = pd.cut(
        df_all["capacity_ml"],
        bins=[0, 50, 100, 250, 500, 1000, float("inf")],
        labels=[
            "0-50ml",
            "50-100ml",
            "100-250ml",
            "250-500ml",
            "500-1000ml",
            "1000ml+",
        ],
    )

    return df_all


def get_assortment_analysis_data(companies_data):
    """Get assortment analysis data"""
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    df_all = pd.DataFrame(all_data)

    # Create capacity ranges
    df_all["capacity_ml"] = df_all.apply(
        lambda x: normalize_capacity(x["capacity"], x["unit"]), axis=1
    )
    df_all["capacity_range"] = pd.cut(
        df_all["capacity_ml"],
        bins=[0, 50, 100, 250, 500, 1000, float("inf")],
        labels=[
            "0-50ml",
            "50-100ml",
            "100-250ml",
            "250-500ml",
            "500-1000ml",
            "1000ml+",
        ],
    )

    return df_all
