"""
Pricing Analysis UI utilities.
This module contains all functions related to pricing intelligence and analysis.
"""

import streamlit as st, pandas as pd, plotly.express as px
from typing import Dict
import plotly.graph_objects as go
from .data_utils import (
    get_capacity_analysis_data,
    show_case_price_tier_chart,
)
from .fuzzy_matching import fuzzy_product_match


def show_pricing_intelligence(companies_data):
    """Display pricing intelligence dashboard"""
    st.header("💰 Pricing Analysis Dashboard")

    # Combine all data for analysis
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    df_all = pd.DataFrame(all_data)

    # Normalized price per capacity
    # Calculate normalized prices
    df_all = get_capacity_analysis_data(companies_data)

    # Average price by capacity range
    st.subheader("💰 Average Price by Capacity Range")

    # Filter out rows with price <= 0 or price is null/NaN before averaging
    df_valid_prices = df_all[
        df_all["price"].notnull() & df_all["price"].notna() & (df_all["price"] > 0)
    ]
    capacity_bin_prices = (
        df_valid_prices.groupby(["company", "capacity_range"])["price"]
        .mean()
        .reset_index(name="avg_price")
    )
    fig_bins = px.bar(
        capacity_bin_prices,
        x="capacity_range",
        y="avg_price",
        color="company",
        color_discrete_map={
            "Berlin Packaging": "#e01b22",
            "Cary Company": "#1c2e5c",
            "TricorBraun": "#282828",
        },
        title="Average Price by Capacity Range",
        barmode="group",
        labels={
            "avg_price": "Average Price ($)",
            "capacity_range": "Capacity Range",
        },
    )
    st.plotly_chart(fig_bins, width="stretch")

    # --- 📈 Min–Max Price by Capacity Bin and Company ---
    st.subheader("📈 Price Range (Min–Max) by Capacity Bin and Company")

    # Define fixed capacity bins
    capacity_bins = [
        "0-50ml",
        "50-100ml",
        "100-250ml",
        "250-500ml",
        "500-1000ml",
        "1000ml+",
    ]

    # Group to get min and max price for each company and capacity range
    # Filter out rows where avg_price_per_unit is null/NaN or zero
    df_filtered = df_all[
        df_all["avg_price_per_unit"].notna() & (df_all["avg_price_per_unit"] != 0)
    ]

    minmax_df = (
        df_filtered.groupby(["company", "capacity_range"])
        .agg(
            min_price=("avg_price_per_unit", "min"),
            max_price=("avg_price_per_unit", "max"),
        )
        .reset_index()
    )

    # Ensure consistent capacity bin ordering
    minmax_df["capacity_range"] = pd.Categorical(
        minmax_df["capacity_range"], categories=capacity_bins, ordered=True
    )

    # # Optional: show the computed table
    # st.dataframe(minmax_df.sort_values(["company", "capacity_range"]))

    # --- Create Plotly figure (Error Bar Style) ---
    fig_minmax = go.Figure()

    for company in minmax_df["company"].unique():
        company_df = minmax_df[minmax_df["company"] == company]

        fig_minmax.add_trace(
            go.Scatter(
                x=company_df["capacity_range"],
                y=(company_df["min_price"] + company_df["max_price"]) / 2,
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=company_df["max_price"]
                    - ((company_df["min_price"] + company_df["max_price"]) / 2),
                    arrayminus=((company_df["min_price"] + company_df["max_price"]) / 2)
                    - company_df["min_price"],
                    thickness=1.5,
                    width=6,
                ),
                mode="markers+lines",
                name=company,
                line=dict(width=2),
                marker=dict(size=8),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + "Company: %{text}<br>"
                    + "Min Price: %{customdata[0]:.2f}<br>"
                    + "Max Price: %{customdata[1]:.2f}<extra></extra>"
                ),
                text=[company] * len(company_df),
                customdata=company_df[["min_price", "max_price"]].values,
                marker_color={
                    "Berlin Packaging": "#e01b22",
                    "Cary Company": "#1c2e5c",
                    "TricorBraun": "#282828",
                }.get(company, "#666"),
            )
        )

    fig_minmax.update_layout(
        title="Min–Max Price Range by Capacity Bin and Company",
        xaxis_title="Capacity Range",
        yaxis_title="Price ($)",
        legend_title="Company",
        hovermode="x unified",
        template="plotly_white",
        height=500,
    )

    st.plotly_chart(fig_minmax, use_container_width=True)

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
        color_discrete_map={
            "Berlin Packaging": "#e01b22",
            "Cary Company": "#1c2e5c",
            "TricorBraun": "#282828",
        },
        title="Average Price by Category and Company",
        barmode="group",
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("### 🧮 Case Price Tiers (Min vs Max)")
    show_case_price_tier_chart(all_data)  # ✅ FIXED: call inside function

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
