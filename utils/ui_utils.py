"""
UI utilities for the packing competitor analysis dashboard.
This module contains all UI-related functions and styling.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Any
from .data_utils import (
    get_pricing_data_for_chart,
    get_capacity_analysis_data,
    get_assortment_analysis_data,
    fuzzy_product_match,
    normalize_capacity,
)


def setup_page_config():
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title="Packing Competitor Analysis Dashboard",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def get_custom_css():
    """Return custom CSS for styling"""
    return """
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
    """


def apply_custom_styling():
    """Apply custom CSS styling to the dashboard"""
    st.markdown(get_custom_css(), unsafe_allow_html=True)


def create_header():
    """Create the main dashboard header"""
    st.markdown(
        '<h1 class="main-header">📦 Packing Competitor Analysis Dashboard</h1>',
        unsafe_allow_html=True,
    )


def create_navigation_menu():
    """Create the navigation menu bar"""
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

    return st.session_state.page


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
        display_df.columns = [col for col in display_columns]

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Sell UOM Data
        display_sell_uom_data(df, selected_company)

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

    # Pricing tiers analysis with multi-line chart
    st.subheader("📈 Pricing Tiers Analysis")

    # Get pricing data for chart
    pricing_data = get_pricing_data_for_chart(companies_data)

    if pricing_data:
        pricing_df = pd.DataFrame(pricing_data)

        # Create multi-line chart for price distribution
        fig = create_price_distribution_multiline_chart(pricing_df)
        st.plotly_chart(fig, use_container_width=True)

    # Normalized price per capacity
    st.subheader("⚖️ Normalized Price per Capacity")

    # Calculate normalized prices
    df_all = get_capacity_analysis_data(companies_data)

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


def create_price_distribution_multiline_chart(pricing_df):
    """Create a multi-line chart for price distribution by company"""
    # Group by company and quantity to get average prices
    company_price_trends = (
        pricing_df.groupby(["Company", "Quantity"])["Price"].mean().reset_index()
    )

    # Create multi-line chart
    fig = px.line(
        company_price_trends,
        x="Quantity",
        y="Price",
        color="Company",
        title="Price Distribution by Company (Multi-line Chart)",
        labels={"Quantity": "Quantity Tier", "Price": "Average Price ($)"},
        markers=True,
    )

    # Update layout for better readability
    fig.update_layout(
        xaxis_title="Quantity Tier",
        yaxis_title="Average Price ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def show_assortment_kpis(companies_data):
    """Display assortment and market KPI dashboard"""
    st.header("📦 Assortment & Market KPI Dashboard")

    # Get assortment analysis data
    df_all = get_assortment_analysis_data(companies_data)

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

    # SKU count by capacity range
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

    # Average price by capacity range
    st.subheader("💰 Average Price by Capacity Range")

    capacity_price_avg = (
        df_all.groupby(["company", "capacity_range"])["price"]
        .mean()
        .reset_index(name="avg_price")
    )
    fig_price = px.bar(
        capacity_price_avg,
        x="capacity_range",
        y="avg_price",
        color="company",
        title="Average Price by Capacity Range",
        barmode="group",
        labels={"avg_price": "Average Price ($)", "capacity_range": "Capacity Range"},
    )
    st.plotly_chart(fig_price, use_container_width=True)

    # Combined capacity analysis table
    st.subheader("📊 Capacity Range Summary")

    capacity_summary = (
        df_all.groupby(["company", "capacity_range"])
        .agg({"price": ["count", "mean"], "capacity_ml": "mean"})
        .round(2)
    )

    capacity_summary.columns = ["SKU Count", "Avg Price ($)", "Avg Capacity (ml)"]
    capacity_summary = capacity_summary.reset_index()

    st.dataframe(capacity_summary, use_container_width=True)

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


def display_sell_uom_data(df, selected_company):
    """
    Display sell UOM data using expanders with search functionality.
    Each product gets its own expander showing quantity breaks and pricing tiers.
    """
    st.subheader(f"💰 {selected_company} Sell UOM Data")

    # Count total sell UOM entries
    total_sell_uom_entries = sum(
        len(product.get("sell_uom", [])) for _, product in df.iterrows()
    )
    st.info(f"Total Sell UOM entries: {total_sell_uom_entries}")

    # Search functionality
    search_term = st.text_input(
        "🔍 Search by SKU, Product Name, or Quantity:",
        placeholder="Enter SKU, product name, or quantity to filter...",
        key=f"search_uom_{selected_company}",
    )

    # Filter products based on search
    filtered_products = []
    for _, product in df.iterrows():
        if product.get("sell_uom") and len(product["sell_uom"]) > 0:
            # Check if search term matches any relevant field
            if not search_term or any(
                [
                    search_term.lower() in str(product.get("sku", "")).lower(),
                    search_term.lower() in str(product.get("name", "")).lower(),
                    any(
                        search_term.lower()
                        in str(uom_item.get("qty_range", "")).lower()
                        or search_term.lower() in str(uom_item.get("qty", "")).lower()
                        for uom_item in product["sell_uom"]
                    ),
                ]
            ):
                filtered_products.append(product)

    # Limit display to 10 products
    display_products = filtered_products[:10]

    if not display_products:
        if search_term:
            st.warning(f"No products found matching '{search_term}'")
        else:
            st.info("No sell UOM data available for this company.")
        return

    # Show total count and pagination info
    if len(filtered_products) > 10:
        st.info(
            f"Showing 10 of {len(filtered_products)} products. Use search to narrow down results."
        )

    # Display each product in an expander
    for product in display_products:
        product_name = product.get("name", "Unknown Product")
        quantity_breaks = len(product.get("sell_uom", []))

        # Create expander title
        with st.expander(
            f"📦 {product_name} → {quantity_breaks} tiers", expanded=False
        ):
            # Product basic info
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Product:** [{product_name}]({product.get('url', '#')})")
            with col2:
                st.markdown(
                    f"**SKU:** [{product.get('sku', 'N/A')}]({product.get('url', '#')})"
                )

            st.divider()

            # Display quantity breaks/pricing tiers
            if product.get("sell_uom"):
                st.markdown("**📊 Pricing Tiers:**")

                # Create table for pricing tiers
                tier_data = []
                for uom_item in product["sell_uom"]:
                    quantity_field = uom_item.get("qty_range") or uom_item.get(
                        "qty", ""
                    )
                    unit_field = uom_item.get("unit", "")
                    price_field = uom_item.get("price", "")
                    price_per_unit_field = uom_item.get("price_per_unit", "")

                    tier_data.append(
                        {
                            "Quantity": quantity_field,
                            "Unit": unit_field,
                            "Price": price_field,
                            "Price/Unit": price_per_unit_field,
                        }
                    )

                if tier_data:
                    tier_df = pd.DataFrame(tier_data)
                    st.dataframe(tier_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No pricing tier data available for this product.")
            else:
                st.info("No sell UOM data available for this product.")
