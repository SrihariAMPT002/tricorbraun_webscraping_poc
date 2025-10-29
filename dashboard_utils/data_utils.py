"""
Data processing utilities for the packing competitor analysis dashboard.
This module contains all data loading, processing, and analysis functions.
"""

import json, re, pandas as pd, pint, plotly.express as px
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
    find_all_similar_products,
    get_similarity_summary,
    find_similar_products_with_capacity_binning,
)

# Initialize unit registry for capacity normalization
ureg = pint.UnitRegistry()


@st.cache_data
def load_data():
    """Load and process all company data"""
    companies = {}

    # Load Berlin Packaging data
    try:
        with open("demo_batch_data/berlin_new_data_normalised.json", "r") as f:
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
        with open("demo_batch_data/tricorbraun_new_data_normalized.json", "r") as f:
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
        record["market_segment"] = categorize_product(item.get("product_name", ""))
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
                "product_origin": "Country of Manufacture",
            },
            availability_keys=[("product_availability", "availability_text")],
            url_key="product_url",
        )
        record["market_segment"] = categorize_product(item.get("product_name", ""))
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
                "product_origin": "Country of Origin",
            },
            availability_keys=[("product_availability", "availability_text")],
            url_key="product_url",
            extras={"items_per_unit": items_per_unit_value},
        )
        record["market_segment"] = categorize_product(item.get("product_name", ""))
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
            else 1.0
        )
    except ValueError:
        packing_unit_count = 1.0

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


# --- Cary Company ---
def extract_cary_pricing(sell_uom, packing_details=None, product_notes=None):
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    items_per_case = 0
    items_per_pallet = 0

    if product_notes:
        joined = " ".join(product_notes).lower()
        case_match = re.search(r"(\d+)\s?(?:per\s?(?:case|box|carton))", joined)
        pallet_match = re.search(r"(\d+)\s?(?:per\s?pallet)", joined)
        if case_match:
            items_per_case = float(case_match.group(1))
        if pallet_match:
            items_per_pallet = float(pallet_match.group(1))

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
        elif unit == "pallet" and items_per_pallet > 0:
            price_per_unit = round(price_value / items_per_pallet, 4)
        elif unit in ["piece", "ea", "each", ""]:
            price_per_unit = round(price_value, 4)
        else:
            continue

        unit_prices.append(price_per_unit)
        breaks.append(
            {
                "quantity_of_packing": qty_str,
                "type_of_packing": unit,
                "price_per_packing": price_value,
                "price_per_item": price_per_unit,
            }
        )

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


def get_capacity_analysis_data(companies_data):
    """Get capacity analysis data with normalized values"""
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    df_all = pd.DataFrame(all_data)

    # Calculate normalized capacity in ml
    df_all["capacity_ml"] = df_all.apply(
        lambda x: normalize_capacity_fuzzy(x["capacity"], x["unit"]), axis=1
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
        lambda x: normalize_capacity_fuzzy(x["capacity"], x["unit"]), axis=1
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


def extract_case_prices(product):
    """Extract all case-level prices from processed data (Berlin, Cary, TricorBraun)."""
    prices = []
    sell_uom = product.get("sell_uom") or []
    company = product.get("company", "").lower()

    for tier in sell_uom:
        qty_range = str(tier.get("qty_range", "")).lower()
        unit = str(tier.get("unit", "")).lower()
        price_text = (
            str(tier.get("price", "")).replace("$", "").replace(",", "").strip()
        )
        price_unit_text = (
            str(tier.get("price_per_unit", ""))
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

        # ✅ Detect Berlin's Case Pricing
        # Berlin: sometimes only first tier has 'Case', others are just ranges
        if company == "berlin packaging":
            # If first tier or small quantity tiers (<20 or with '1 -') treat as Case
            if (
                "case" in qty_range
                or "case" in unit
                or qty_range.startswith("1")
                or "1 -" in qty_range
            ):
                if price_text.replace(".", "", 1).isdigit():
                    prices.append(float(price_text))
                elif price_unit_text.replace(".", "", 1).isdigit():
                    prices.append(float(price_unit_text))
            else:
                # fallback for subsequent price tiers (even if 'case' not explicitly present)
                if price_text.replace(".", "", 1).isdigit():
                    prices.append(float(price_text))
                elif price_unit_text.replace(".", "", 1).isdigit():
                    prices.append(float(price_unit_text))
        else:
            # ✅ Cary & TricorBraun logic
            if "case" in qty_range or "case" in unit:
                if price_text.replace(".", "", 1).isdigit():
                    prices.append(float(price_text))
                elif price_unit_text.replace(".", "", 1).isdigit():
                    prices.append(float(price_unit_text))

    if not prices:
        return None, None

    return min(prices), max(prices)


def get_case_price_bin_data(product_list):
    """Aggregate min/max Case price per company grouped by capacity bins."""
    import streamlit as st

    records = []

    for product in product_list:
        company = product.get("company", "")
        cap_ml = product.get("capacity")
        if not cap_ml or not company:
            continue

        min_price, max_price = extract_case_prices(product)
        if min_price is None:
            continue

        records.append(
            {
                "company": company,
                "capacity_ml": float(cap_ml),
                "min_price": min_price,
                "max_price": max_price,
            }
        )

    df = pd.DataFrame(records)
    if df.empty:
        st.warning("⚠️ No valid Case pricing data found.")
        return df

    df["capacity_bin"] = pd.cut(
        df["capacity_ml"],
        bins=[0, 50, 100, 250, 500, 1000, float("inf")],
        labels=[
            "0-50ml",
            "50-100ml",
            "100-250ml",
            "250-500ml",
            "500-1000ml",
            "1000ml+",
        ],
        right=False,
    )

    df_summary = (
        df.groupby(["company", "capacity_bin"])[["min_price", "max_price"]]
        .mean()
        .reset_index()
    )

    df_summary = df_summary.melt(
        id_vars=["company", "capacity_bin"],
        value_vars=["min_price", "max_price"],
        var_name="Price Type",
        value_name="Price ($)",
    )

    return df_summary


def show_case_price_tier_chart(json_data):
    import streamlit as st

    """Render bar graph of Min/Max Case prices grouped by capacity bins."""
    st.subheader("📦 Case Price Distribution by Capacity Range")

    df_summary = get_case_price_bin_data(json_data)
    if df_summary.empty:
        return

    fig = px.bar(
        df_summary,
        x="capacity_bin",
        y="Price ($)",
        color="Price Type",
        barmode="group",
        facet_col="company",
        title="Case Price Tiers by Capacity Range (ml)",
        labels={
            "capacity_bin": "Capacity Range (ml)",
            "Price ($)": "Average Case Price ($)",
        },
        text_auto=".2f",
    )

    fig.update_layout(
        bargap=0.25,
        xaxis_tickangle=-30,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend_title_text="Price Type",
        title_x=0.35,
    )

    st.plotly_chart(fig, use_container_width=True)
