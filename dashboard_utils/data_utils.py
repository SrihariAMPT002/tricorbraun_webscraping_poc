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
from typing import Dict, List, Any, Optional
import re

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
        packing_unit_capacity = item.get("product_specs", {}).get(
            "Case Qty "
        ) or item.get("product_specs", {}).get("Pallet Qty ")
        pricing = extract_berlin_pricing(
            item.get("product_sell_uom", []), packing_unit_capacity
        )
        zero_handled_pricing = round(pricing["base_price"], 2)

        processed.append(
            {
                "company": "Berlin Packaging",
                "sku": item.get("product_id", "") or "",
                "name": item.get("product_name", "") or "",
                "price": pricing["base_price"],
                "avg_price_per_unit": zero_handled_pricing,
                "normalised_capacity(ml)": round(normalised_value, 2),
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
        product_normalised_data = item.get("product_normalized_data", {})
        original_uom, original_capacity, normalised_uom, normalised_value = (
            get_normalised_data(product_normalised_data)
        )
        packing_details = item.get("product_packing_details", {})
        product_notes = item.get("product_notes", [])
        pricing = extract_cary_pricing(
            item.get("product_sell_uom", []), packing_details, product_notes
        )
        zero_handled_pricing = round(pricing["base_price"], 2)

        processed.append(
            {
                "company": "Cary Company",
                "sku": item.get("product_id", "") or "",
                "name": item.get("product_name", "") or "",
                "price": pricing["base_price"],
                "quantity_breaks": pricing["breaks"],
                "avg_price_per_unit": zero_handled_pricing,
                "normalised_capacity(ml)": round(normalised_value, 2),
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
                "stock": item.get("product_availability", {}).get(
                    "availability_text", ""
                )
                or "N/A",
                "url": item.get("product_url", "") or "",
                "product_origin": item.get("product_specs", {}).get(
                    "Country of Manufacture", ""
                ),
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
        items_per_unit = item.get("product_specs", {}).get("items_per_unit", "") or ""
        items_per_unit_match = re.search(r"(\d+)", items_per_unit)
        items_per_unit_value = (
            int(items_per_unit_match.group(1)) if items_per_unit_match else 1
        )
        pricing = extract_tricor_pricing(item.get("product_selluom", []))
        zero_handled_pricing = round(pricing["base_price"], 2)
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
                "avg_price_per_unit": zero_handled_pricing,
                "normalised_capacity(ml)": round(normalised_value, 2),
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
                "stock": item.get("product_availability", {}).get("in_stock", "")
                or "N/A",
                "url": item.get("product_url", "") or "",
                "items_per_unit": items_per_unit_value,
                "product_origin": item.get("product_specs", {}).get(
                    "Country of Origin", ""
                ),
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


def extract_berlin_pricing(sell_uom, packing_unit_quantity: Optional[str]):
    """Extract pricing from Berlin Packaging sell_uom data."""
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    def parse_float(value):
        """Safely extract float from a string like '$1,200.50' or 'N/A'."""
        if not value:
            return 0.0
        value = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(value)
        except ValueError:
            return 0.0

    # Convert packing_unit_quantity (e.g., "12 ea.") → 12.0
    try:
        packing_unit_count = (
            float(re.sub(r"[^\d.]", "", packing_unit_quantity))
            if packing_unit_quantity
            else 1.0
        )
    except ValueError:
        packing_unit_count = 1.0

    breaks = []
    unit_prices = []

    for tier in sell_uom:
        qty_range = tier.get("qty_range")
        price_per_packing_str = tier.get("price")  # total case/pallet price
        price_per_unit_str = tier.get("price_per_unit")

        price_per_packing = parse_float(price_per_packing_str)
        price_per_unit = parse_float(price_per_unit_str)

        # Case 1: Missing price_per_unit
        if not price_per_unit_str:
            if price_per_packing > 10 and packing_unit_count > 0:
                price_per_unit = round(price_per_packing / packing_unit_count, 4)
            else:
                price_per_unit = price_per_packing

        # Case 2: Both present (explicit unit and packing prices)
        # → we just ensure consistency and parsing
        if price_per_unit == 0 and price_per_packing > 0 and packing_unit_count > 0:
            price_per_unit = round(price_per_packing / packing_unit_count, 4)

        unit_prices.append(price_per_unit)
        breaks.append(
            {
                "quantity": qty_range,
                "price": price_per_packing,  # total case/pallet price
                "price_per_unit": price_per_unit,
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0

    return {"base_price": base_price, "breaks": breaks}


def extract_cary_pricing(sell_uom, packing_details=None, product_notes=None):
    """
    Extract pricing from Cary Company sell_uom data.
    - `price` is the total price per packing (case/pallet)
    - `price_per_unit` is the derived price per single item
    """

    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    def parse_count(value):
        """Extract float count from text like '12 ea.' or '1,200 ea. (100 Cases)'."""
        if not value:
            return 0
        try:
            return float(re.sub(r"[^\d.]", "", str(value)))
        except ValueError:
            return 0

    # --- Detect items per case/pallet ---
    items_per_case = 0
    items_per_pallet = 0

    if product_notes:
        joined_notes = " ".join(product_notes).lower()
        match_case_num = re.search(
            r"(\d+)\s?(?:per\s?(?:case|box|carton))", joined_notes
        )
        if match_case_num:
            items_per_case = float(match_case_num.group(1))

        match_pallet_num = re.search(r"(\d+)\s?(?:per\s?pallet)", joined_notes)
        if match_pallet_num:
            items_per_pallet = float(match_pallet_num.group(1))

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
        price_str = tier.get("price") or ""
        try:
            price_value = float(re.sub(r"[^\d.]", "", price_str))
        except ValueError:
            continue

        price_per_unit = 0.0

        # Case or pallet pricing → divide by quantity in that pack
        if unit == "case" and items_per_case > 0:
            price_per_unit = round(price_value / items_per_case, 4)
        elif unit == "pallet" and items_per_pallet > 0:
            price_per_unit = round(price_value / items_per_pallet, 4)
        # If price is for single piece, then per-unit = same value
        elif unit in ["piece", "ea", "each", ""]:
            price_per_unit = round(price_value, 4)
        else:
            continue  # skip unknown or unhandled units

        unit_prices.append(price_per_unit)
        breaks.append(
            {
                "quantity": qty_str,
                "unit": unit,
                "price": price_value,
                "price_per_unit": price_per_unit,
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0.0

    return {"base_price": base_price, "breaks": breaks}


def extract_tricor_pricing(selluom):
    """Extract pricing from TricorBraun selluom data (handles 'Piece' units & nulls)."""
    if not selluom:
        return {"base_price": 0, "breaks": []}

    breaks = []
    unit_prices = []

    for item in selluom:
        # Extract quantity (e.g., "110 Piece" → 110)
        qty_text = item.get("qty_range") or ""
        qty_match = re.search(r"(\d+)", qty_text)
        qty = int(qty_match.group(1)) if qty_match else 1

        unit = (item.get("unit") or "").strip()
        price_text = item.get("price") or "$0"
        price_match = re.search(r"([\d.,]+)", price_text)
        price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

        # If price_per_unit exists and not null
        price_per_unit_text = item.get("price_per_unit") or ""
        price_per_unit_match = re.search(r"([\d.,]+)", price_per_unit_text)
        price_per_unit = (
            float(price_per_unit_match.group(1).replace(",", ""))
            if price_per_unit_match
            else 0.0
        )

        # If price_per_unit is missing/null and unit is "Piece", use price directly
        if unit.lower() == "piece" and not price_per_unit:
            price_per_unit = price

        # If still 0 (fallback)
        if not price_per_unit and price > 0 and qty > 0:
            price_per_unit = round(price / qty, 4)

        if price_per_unit > 0:
            unit_prices.append(price_per_unit)

        breaks.append(
            {
                "quantity": qty,
                "price": price,
                "price_per_unit": price_per_unit,
                "unit": unit or "Case",
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0.0

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
