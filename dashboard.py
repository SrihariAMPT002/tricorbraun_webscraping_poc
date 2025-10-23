from itertools import product
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import numpy as np
from rapidfuzz import fuzz
import pint
from typing import Dict, List, Any
import re

# Configure page
st.set_page_config(
    page_title="Packing Competitor Analysis Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize unit registry for capacity normalization
ureg = pint.UnitRegistry()

# Custom CSS for better styling
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .company-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    """Load and process all company data"""
    companies = {}

    # Load Berlin Packaging data
    try:
        with open("demo_batch_data/berlin_packing_all_data_normalized.json", "r") as f:
            berlin_data = json.load(f)
            companies["Berlin Packaging"] = process_berlin_data(berlin_data)
    except FileNotFoundError:
        st.warning("Berlin Packaging data not found. Skipping this company.")
        companies["Berlin Packaging"] = []

    # Load Cary Company data
    try:
        with open("demo_batch_data/cary_all_data.json", "r") as f:
            cary_data = json.load(f)
            companies["Cary Company"] = process_cary_data(cary_data)
    except FileNotFoundError:
        st.warning("Cary Company data not found. Skipping this company.")
        companies["Cary Company"] = []

    # Load TricorBraun data
    try:
        with open("demo_batch_data/tricorbraun_all_data_normalized.json", "r") as f:
            tricor_data = json.load(f)
            companies["TricorBraun"] = process_tricor_data(tricor_data)
    except FileNotFoundError:
        st.warning("TricorBraun data not found. Skipping this company.")
        companies["TricorBraun"] = []

    # Filter out empty companies
    companies = {k: v for k, v in companies.items() if v}

    if not companies:
        st.error(
            "No data files found. Please ensure the JSON data files are in the demo_batch_data/ directory."
        )
        st.stop()

    return companies


def process_berlin_data(data):
    """Process Berlin Packaging data into standardized format"""
    processed = []
    for item in data:
        if not item:
            continue

        # Extract capacity and unit
        product_normalised_data = item.get("product_normalized_uom", {})
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
                "original_uom": original_uom,
                "original_capacity": original_capacity,
                "normalised_uom": normalised_uom,
                "normalised_capacity": normalised_value,
                "color": item.get("product_specs", {}).get("Color ", "") or "",
                "material": item.get("product_specs", {}).get("Material Type ", "")
                or "",
                "shape": item.get("product_specs", {}).get("Shape ", "") or "",
                "category": item.get("product_specs", {}).get("Material Group ", "")
                or "",
                "closure_type": item.get("product_specs", {}).get("Neck Finish ", "")
                or "",
                "market_segment": categorize_product(item.get("product_name", "")),
                "stock": item.get("product_availability", {}).get("in_stock", "") or "",
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

        # Extract capacity and unit
        product_normalised_data = item.get("product_normalized_uom", {})
        original_uom, original_capacity, normalised_uom, normalised_value = (
            get_normalised_data(product_normalised_data)
        )
        # capacity, unit = parse_capacity(capacity_str)
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
                "original_uom": original_uom,
                "original_capacity": original_capacity,
                "normalised_uom": normalised_uom,
                "normalised_capacity": normalised_value,
                "color": item.get("product_information_specs", {}).get("Color", "")
                or "",
                "material": item.get("product_information_specs", {}).get(
                    "Material", ""
                )
                or "",
                "shape": item.get("product_information_specs", {}).get("Style", "")
                or "",
                "category": item.get("product_information_specs", {}).get(
                    "Material", ""
                )
                or "",
                "closure_type": item.get("product_information_specs", {}).get(
                    "Neck Finish", ""
                )
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

        # Extract capacity and unit
        product_normalised_data = item.get("product_normalized_uom", {})
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
                "original_uom": original_uom,
                "original_capacity": original_capacity,
                "normalised_uom": normalised_uom,
                "normalised_capacity": normalised_value,
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


# def parse_capacity(capacity_str):
#     """Parse capacity string to extract numeric value and unit"""
#     if not capacity_str:
#         return 0, "ml"

#     # Extract numeric value and unit
#     match = re.search(r"([\d.]+)\s*(oz|ml|cc|fl\.?\s*oz)", capacity_str.lower())
#     if match:
#         value = float(match.group(1))
#         unit = match.group(2).replace("fl. oz", "oz").replace("fl oz", "oz")
#         return value, unit

#     return 0, "ml"


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
    # print(unit_prices)
    base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

    return {"base_price": base_price, "breaks": breaks}


def extract_cary_pricing(sell_uom, packing_details, case_pack_notes):
    """Extract pricing from Cary Company sell_uom data"""
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    # print(case_pack_notes)
    items_per_case = ""
    items_per_pallet = ""
    if packing_details:
        items_per_case = packing_details.get("Case Pack", None)
        items_per_pallet = packing_details.get("Pallet Pack", None)

    if not items_per_case:
        items_per_case = case_pack_notes if case_pack_notes else ""

    breaks = []
    unit_prices = []

    # print(sell_uom)

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


def main():
    """Main dashboard application"""

    # Header
    st.markdown(
        '<h1 class="main-header">📦 Packing Competitor Analysis Dashboard</h1>',
        unsafe_allow_html=True,
    )

    # Load data
    companies_data = load_data()

    # Menu bar navigation
    st.markdown(
        """
    <style>
    .menu-bar {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .menu-item {
        display: inline-block;
        margin-right: 1rem;
        padding: 0.5rem 1rem;
        background-color: #ffffff;
        border-radius: 0.25rem;
        text-decoration: none;
        color: #1f77b4;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .menu-item:hover {
        background-color: #1f77b4;
        color: #ffffff;
        transform: translateY(-2px);
    }
    .menu-item.active {
        background-color: #1f77b4;
        color: #ffffff;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Create menu bar
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 2])

    with col1:
        if st.button("🏠 Homepage", key="homepage_btn", use_container_width=True):
            st.session_state.page = "Homepage"

    with col2:
        if st.button(
            "💰 Pricing Intelligence", key="pricing_btn", use_container_width=True
        ):
            st.session_state.page = "Pricing Intelligence"

    with col3:
        if st.button(
            "📦 Assortment & Market KPIs",
            key="assortment_btn",
            use_container_width=True,
        ):
            st.session_state.page = "Assortment & Market KPIs"

    with col4:
        if st.button("🤖 Chatbot", key="chatbot_btn", use_container_width=True):
            st.session_state.page = "Chatbot"

    # Initialize session state for page
    if "page" not in st.session_state:
        st.session_state.page = "Homepage"

    page = st.session_state.page

    # Main content based on selected page
    if page == "Homepage":
        show_homepage(companies_data)
    elif page == "Pricing Intelligence":
        show_pricing_intelligence(companies_data)
    elif page == "Assortment & Market KPIs":
        show_assortment_kpis(companies_data)
    elif page == "Chatbot":
        show_chatbot()


def show_homepage(companies_data):
    """Display homepage with company overview"""

    st.header("📊 Company Overview")

    # Company selection
    company_names = list(companies_data.keys())
    selected_company = st.selectbox("Select Company", company_names)

    if selected_company:
        company_data = companies_data[selected_company]
        df = pd.DataFrame(company_data)

        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(label="Total SKUs", value=len(df), delta=None)

        with col2:
            avg_price = df["price"].mean()
            st.metric(label="Average Price", value=f"${avg_price:.2f}", delta=None)

        with col3:
            unique_categories = df["category"].nunique()
            st.metric(label="Categories", value=unique_categories, delta=None)

        with col4:
            in_stock_count = len(
                df[df["stock"].str.contains("In Stock", case=False, na=False)]
            )
            st.metric(label="In Stock", value=f"{in_stock_count}/{len(df)}", delta=None)

        # Product table
        st.subheader(f"📋 {selected_company} Products")

        # Display columns
        display_columns = [
            "sku",
            "name",
            "original_uom",
            "original_capacity",
            "normalised_uom",
            "normalised_capacity",
            "color",
            "material",
            "shape",
            "category",
            "stock",
        ]
        display_df = df[display_columns].copy()
        display_df.columns = [col.title() for col in display_columns]

        st.dataframe(display_df, use_container_width=True)

        # Comparison metrics across all companies
        st.subheader("🏢 Cross-Company Comparison")

        comparison_data = []
        for company, data in companies_data.items():
            df_comp = pd.DataFrame(data)
            comparison_data.append(
                {
                    "Company": company,
                    "Total SKUs": len(df_comp),
                    "Avg Price": df_comp["price"].mean(),
                    "Categories": df_comp["category"].nunique(),
                    "Market Segments": df_comp["market_segment"].nunique(),
                }
            )

        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)


def show_pricing_intelligence(companies_data):
    """Display pricing intelligence dashboard"""

    st.header("💰 Pricing Intelligence Dashboard")

    # Combine all data for analysis
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    df_all = pd.DataFrame(all_data)

    # Pricing tiers analysis
    st.subheader("📈 Pricing Tiers Analysis")

    # Create pricing tier visualization
    pricing_data = []
    for company in companies_data.keys():
        company_df = df_all[df_all["company"] == company]
        for _, row in company_df.iterrows():
            if row["quantity_breaks"]:
                for break_item in row["quantity_breaks"]:
                    pricing_data.append(
                        {
                            "Company": company,
                            "SKU": row["sku"],
                            "Product": row["name"],
                            "Quantity": break_item["quantity"],
                            "Price": break_item["price"],
                        }
                    )

    if pricing_data:
        pricing_df = pd.DataFrame(pricing_data)

        # Pricing tiers chart
        fig = px.box(
            pricing_df, x="Company", y="Price", title="Price Distribution by Company"
        )
        st.plotly_chart(fig, use_container_width=True)

    # Normalized price per capacity
    st.subheader("⚖️ Normalized Price per Capacity")

    # Calculate normalized prices
    df_all["capacity_ml"] = df_all.apply(
        lambda x: normalize_capacity(x["capacity"], x["unit"]), axis=1
    )
    df_all["price_per_ml"] = df_all["price"] / df_all["capacity_ml"]

    # Price per capacity chart
    fig = px.scatter(
        df_all,
        x="capacity_ml",
        y="price_per_ml",
        color="company",
        title="Price per Milliliter by Capacity",
        labels={"capacity_ml": "Capacity (ml)", "price_per_ml": "Price per ml ($)"},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Average price by category
    st.subheader("📊 Average Price by Category")

    category_prices = (
        df_all.groupby(["company", "category"])["price"].mean().reset_index()
    )
    fig = px.bar(
        category_prices,
        x="category",
        y="price",
        color="company",
        title="Average Price by Category and Company",
        barmode="group",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Fuzzy matching demonstration
    st.subheader("🔍 Product Similarity Matching")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Select Company 1:**")
        company1 = st.selectbox("Company 1", list(companies_data.keys()), key="comp1")
        if company1:
            products1 = companies_data[company1]
            product1 = st.selectbox(
                "Product 1", [p["name"] for p in products1], key="prod1"
            )

    with col2:
        st.write("**Select Company 2:**")
        company2 = st.selectbox("Company 2", list(companies_data.keys()), key="comp2")
        if company2:
            products2 = companies_data[company2]
            product2 = st.selectbox(
                "Product 2", [p["name"] for p in products2], key="prod2"
            )

    if st.button("Calculate Similarity"):
        if "product1" in locals() and "product2" in locals():
            p1_data = next(p for p in products1 if p["name"] == product1)
            p2_data = next(p for p in products2 if p["name"] == product2)

            similarity_score = fuzzy_product_match(p1_data, p2_data)

            st.success(f"**Similarity Score: {similarity_score:.2%}**")

            # Display product details
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**{product1}**")
                st.write(f"Capacity: {p1_data['capacity']} {p1_data['unit']}")
                st.write(f"Price: ${p1_data['price']:.2f}")

            with col2:
                st.write(f"**{product2}**")
                st.write(f"Capacity: {p2_data['capacity']} {p2_data['unit']}")
                st.write(f"Price: ${p2_data['price']:.2f}")


def show_assortment_kpis(companies_data):
    """Display assortment and market KPI dashboard"""

    st.header("📦 Assortment & Market KPI Dashboard")

    # Combine all data
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    df_all = pd.DataFrame(all_data)

    # Assortment statistics
    st.subheader("📊 Assortment Statistics")

    col1, col2 = st.columns(2)

    with col1:
        # SKU count by color
        color_counts = (
            df_all.groupby(["company", "color"]).size().reset_index(name="count")
        )
        fig = px.bar(
            color_counts,
            x="color",
            y="count",
            color="company",
            title="SKU Count by Color",
            barmode="group",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # SKU count by material
        material_counts = (
            df_all.groupby(["company", "material"]).size().reset_index(name="count")
        )
        fig = px.bar(
            material_counts,
            x="material",
            y="count",
            color="company",
            title="SKU Count by Material",
            barmode="group",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Capacity range analysis
    st.subheader("📏 Capacity Range Analysis")

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

    capacity_counts = (
        df_all.groupby(["company", "capacity_range"]).size().reset_index(name="count")
    )
    fig = px.bar(
        capacity_counts,
        x="capacity_range",
        y="count",
        color="company",
        title="SKU Count by Capacity Range",
        barmode="group",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Market segment analysis
    st.subheader("🎯 Market Segment Analysis")

    segment_counts = (
        df_all.groupby(["company", "market_segment"]).size().reset_index(name="count")
    )
    fig = px.pie(
        segment_counts,
        values="count",
        names="market_segment",
        title="Market Segment Distribution",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Competitor comparison matrix
    st.subheader("🏢 Competitor Comparison Matrix")

    # Create comparison matrix
    comparison_matrix = (
        df_all.groupby(["company", "market_segment"]).size().unstack(fill_value=0)
    )

    fig = px.imshow(
        comparison_matrix.values,
        labels=dict(x="Market Segment", y="Company", color="SKU Count"),
        x=comparison_matrix.columns,
        y=comparison_matrix.index,
        title="SKU Count by Company and Market Segment",
        color_continuous_scale="Blues",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Assortment coverage metrics
    st.subheader("📈 Assortment Coverage Metrics")

    coverage_metrics = []
    for company in companies_data.keys():
        company_df = df_all[df_all["company"] == company]

        coverage_metrics.append(
            {
                "Company": company,
                "Total SKUs": len(company_df),
                "Unique Colors": company_df["color"].nunique(),
                "Unique Materials": company_df["material"].nunique(),
                "Unique Shapes": company_df["shape"].nunique(),
                "Market Segments": company_df["market_segment"].nunique(),
                "Capacity Ranges": company_df["capacity_range"].nunique(),
            }
        )

    coverage_df = pd.DataFrame(coverage_metrics)
    st.dataframe(coverage_df, use_container_width=True)


def show_chatbot():
    """Display chatbot placeholder interface"""

    st.header("🤖 AI Assistant")

    st.info(
        "This is a placeholder chatbot interface. In a full implementation, this would integrate with a language model to answer questions about the data."
    )

    # Sample usage cards
    st.subheader("💡 Sample Usage Examples")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        <div class="company-card">
            <h4>🔍 Product Comparison</h4>
            <p><strong>Example:</strong> "Compare prices for 500ml jars"</p>
            <p><strong>Response:</strong> Would analyze pricing across all companies for 500ml capacity products</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="company-card">
            <h4>📊 Market Analysis</h4>
            <p><strong>Example:</strong> "Show SKUs under Pharma segment"</p>
            <p><strong>Response:</strong> Would filter and display all pharmaceutical products</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
        <div class="company-card">
            <h4>💰 Pricing Insights</h4>
            <p><strong>Example:</strong> "What's the average price for amber bottles?"</p>
            <p><strong>Response:</strong> Would calculate and display pricing statistics for amber glass products</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="company-card">
            <h4>📈 Trend Analysis</h4>
            <p><strong>Example:</strong> "Which company has the most diverse assortment?"</p>
            <p><strong>Response:</strong> Would analyze and compare assortment diversity metrics</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Chat interface placeholder
    st.subheader("💬 Chat Interface")

    # Chat input
    user_input = st.text_input(
        "Ask me anything about the glass product data:",
        placeholder="e.g., Compare prices for 500ml jars",
    )

    if st.button("Send"):
        if user_input:
            st.success(
                "🤖 **AI Response:** This is a placeholder response. In a full implementation, this would process your query and provide intelligent insights about the glass product data."
            )
        else:
            st.warning("Please enter a question first.")


if __name__ == "__main__":
    main()
