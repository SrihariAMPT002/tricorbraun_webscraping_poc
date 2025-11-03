import streamlit as st
from typing import Dict, List, Optional, Tuple
import pandas as pd
import re


def build_product_record(
    *,
    company: str,
    item: Dict,
    pricing: Dict,
    normalised: Tuple[str, float, str, float],
    sell_uom_key: str,
    spec_keys: Dict[str, str],
    availability_keys: Optional[List[Tuple[str, str]]] = None,
    url_key: str = "product_url",
    description_key: str = "product_description",
    extras: Optional[Dict] = None,
) -> Dict:
    """Create a standardized product record across sources.

    Parameters
    - company: Source company name to stamp on the record
    - item: The raw product JSON object
    - pricing: Dict with keys { base_price: float, breaks: List[...]} (already extracted)
    - normalised: Tuple of (original_uom, original_capacity, normalised_uom, normalised_value)
    - sell_uom_key: Key in raw item that contains sell_uom tiers (e.g., 'product_sell_uom', 'product_selluom')
    - spec_keys: Mapping of expected fields to the exact spec key names present in the source
      Expected keys in mapping: color, material, shape, category, closure_type, product_origin (optional)
    - availability_keys: Optional list of (path1, path2) to try for stock text (first non-empty wins)
    - url_key: Key in raw item that contains the product URL
    - description_key: Key in raw item that contains the product description
    - extras: Any additional fields to merge, e.g., { 'items_per_unit': 12 }

    Returns
    - Dict with unified schema used by the dashboard
    """

    original_uom, original_capacity, normalised_uom, normalised_value = normalised

    def get_in(d: Dict, path: List[str], default=""):
        cur = d
        for p in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(p, {}) if p != path[-1] else cur.get(p, default)
        return cur if cur is not None else default

    specs = item.get("product_specs", {}) or {}

    color_key = spec_keys.get("color")
    material_key = spec_keys.get("material")
    shape_key = spec_keys.get("shape")
    category_key = spec_keys.get("category")
    closure_key = spec_keys.get("closure_type")
    neck_finish_key = spec_keys.get("neck_finish")
    origin_key = spec_keys.get("product_origin")

    stock_value = ""
    if availability_keys:
        for k1, k2 in availability_keys:
            val = get_in(item, [k1, k2]) if k2 else get_in(item, [k1])
            if val:
                stock_value = val
                break

    base_price = pricing.get("base_price", 0)
    zero_handled_pricing = base_price

    raw_shape = specs.get(shape_key, "") if shape_key else ""
    product_name = item.get("name", "") or ""
    product_description = item.get(description_key, "") or ""
    normalized_shape = normalize_shape(product_name, product_description, raw_shape)

    record = {
        "company": company,
        "url": item.get(url_key, "") or "",
        "sku": item.get("product_id", "") or "",
        "name": item.get("product_name", "") or "",
        "price": base_price,
        "quantity_breaks": pricing.get("breaks", []),
        "sell_uom": item.get(sell_uom_key, []) or [],
        "avg_price_per_unit": zero_handled_pricing,
        "normalised_capacity(ml)": round(normalised_value or 0, 2),
        "original_uom": original_uom,
        "original_capacity": original_capacity,
        "normalised_uom": normalised_uom,
        "normalised_capacity": normalised_value,
        "capacity": normalised_value,  # used for analysis
        "unit": normalised_uom,  # used for analysis
        "color": specs.get(color_key, "") if color_key else "",
        "material": specs.get(material_key, "") if material_key else "",
        "neck_finish": specs.get(neck_finish_key, "") if neck_finish_key else "",
        "shape": normalized_shape,
        "category": specs.get(category_key, "") if category_key else "",
        "closure_type": specs.get(closure_key, "") if closure_key else "",
        "market_segment": item.get("product_name", ""),  # caller can post-process
    }

    # Optional origin
    if origin_key:
        record["product_origin"] = specs.get(origin_key, "")

    # Optional stock
    if stock_value:
        record["stock"] = stock_value

    # Merge extras
    if extras:
        for k, v in extras.items():
            record[k] = v

    return record


def get_product_capacity_bins(selected_company):
    # Capacity bins filter
    capacity_bins = [
        "0-50ml",
        "50-100ml",
        "100-250ml",
        "250-500ml",
        "500-1000ml",
        "1000ml+",
    ]
    selected_capacity_bins = st.multiselect(
        "Filter by Capacity:",
        capacity_bins,
        default=[],
        key=f"capacity_bins_{selected_company}",
    )
    return selected_capacity_bins


def get_product_pricing_bins(selected_company):
    # Pricing bins filter
    pricing_bins = [
        "$0-$0.50",
        "$0.50-$1",
        "$1-$2",
        "$2-$3",
        "$3-$4",
        "$4-$5",
        "$5+",
    ]
    selected_pricing_bins = st.multiselect(
        "Filter by Avg Price per Unit:",
        pricing_bins,
        default=[],
        key=f"pricing_bins_{selected_company}",
    )

    return selected_pricing_bins


# Function to determine capacity bin
def get_capacity_bin(capacity_ml):
    if pd.isna(capacity_ml):
        return None
    if capacity_ml < 50:
        return "0-50ml"
    elif capacity_ml < 100:
        return "50-100ml"
    elif capacity_ml < 250:
        return "100-250ml"
    elif capacity_ml < 500:
        return "250-500ml"
    elif capacity_ml < 1000:
        return "500-1000ml"
    else:
        return "1000ml+"


# Function to determine pricing bin
def get_pricing_bin(price):
    if pd.isna(price) or price == 0:
        return None
    try:
        price = float(price)
        if price <= 0.50:
            return "$0-$0.50"
        elif price <= 1:
            return "$0.50-$1"
        elif price <= 2:
            return "$1-$2"
        elif price <= 3:
            return "$2-$3"
        elif price <= 4:
            return "$3-$4"
        elif price <= 5:
            return "$4-$5"
        else:
            return "$5+"
    except:
        return None


def normalize_shape(product_name: str, description: str, shape: str) -> str:
    """Normalizes product shape based on name, description, and shape fields."""

    # Prioritize shape field, then name, then description
    text_to_check = f"{shape} {product_name} {description}".lower()

    # More specific shapes first
    shape_map = {
        "Boston Round": ["boston round"],
        "Cosmo Round": ["cosmo round"],
        "Straight Sided": ["straight sided"],
        "Bordeaux": ["bordeaux"],
        "Bullet": ["bullet", "rocket"],
        "French Square": ["french square"],
        "Square": ["square", "f-style"],
        "Cylinder": ["cylinder", "cylindrical"],
        "Jar": ["jar"],
        "Bottle": ["bottle"],
        "Tube": ["tube"],
        "Tottle": ["tottle"],
        "Oval": ["oval"],
        "Oblong": ["oblong"],
        "Rectangle": ["rectangle", "rectangular"],
        "Hexagonal": ["hexagonal", "hexagon"],
        "Round": ["round", "circle", "circular"],
        "Packer": ["packer"],
    }

    for unified_shape, keywords in shape_map.items():
        for keyword in keywords:
            # Use word boundaries to avoid partial matches, e.g., 'rounding'
            if re.search(r"\b" + re.escape(keyword) + r"\b", text_to_check):
                return unified_shape

    return "Other"
