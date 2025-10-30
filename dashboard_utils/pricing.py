"""
Pricing Analysis UI utilities.
This module contains all functions related to pricing intelligence and analysis.
"""

from dashboard_utils.fuzzy_matching import normalize_capacity_fuzzy
import streamlit as st, pandas as pd, plotly.express as px
import plotly.graph_objects as go


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


def get_case_price_bin_data(product_list):
    """Aggregate min/max Case price per company grouped by capacity bins."""
    records = []

    for product in product_list:
        company = product.get("company", "")
        cap_ml = product.get("capacity", "")
        quantity_breaks = product.get("quantity_breaks", [])
        if not cap_ml or not company:
            continue
        prices = []
        min_price = 0
        max_price = 0
        prices = []
        for tier in quantity_breaks:
            # Only interested in "case" pricing; skip entries without this info
            type_of_packing = tier.get("type_of_packing")
            if type_of_packing is None:
                print(product.get("sku"))
                continue
            if type_of_packing.lower() == "case":
                price = tier.get("price_per_packing")
                if price is not None:
                    try:
                        price = float(price)
                        prices.append(price)
                    except (TypeError, ValueError):
                        continue

        # Only append if we found any valid "case" prices
        if prices:
            min_price = min(prices)
            max_price = max(prices)
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
        df.groupby(["company", "capacity_bin"], observed=True)[
            ["min_price", "max_price"]
        ]
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


def show_case_price_tier_chart(product_list):
    """Render bar graph of Min/Max Case prices grouped by capacity bins."""
    df_summary = get_case_price_bin_data(product_list)
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

    return fig


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


def build_avg_price_by_capacity_range(df_all: pd.DataFrame):
    """Build bar chart for average price by capacity range per company."""
    df_valid_prices = df_all[
        df_all["price"].notnull() & df_all["price"].notna() & (df_all["price"] > 0)
    ]
    capacity_bin_prices = (
        df_valid_prices.groupby(["company", "capacity_range"], observed=True)["price"]
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
    return fig_bins


def build_minmax_price_range_by_capacity_bin(df_all: pd.DataFrame):
    """Build min–max price range error-bar chart by capacity bin per company."""
    capacity_bins = [
        "0-50ml",
        "50-100ml",
        "100-250ml",
        "250-500ml",
        "500-1000ml",
        "1000ml+",
    ]

    # Filter out rows where avg_price_per_unit is null/NaN or zero
    df_filtered = df_all[
        df_all["avg_price_per_unit"].notna() & (df_all["avg_price_per_unit"] != 0)
    ]

    minmax_df = (
        df_filtered.groupby(["company", "capacity_range"], observed=True)
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
        title="Min–Max Price Range by Capacity Bin",
        xaxis_title="Capacity Range",
        yaxis_title="Price ($)",
        legend_title="Company",
        hovermode="x unified",
        template="plotly_white",
        height=500,
    )

    return fig_minmax


def build_avg_price_by_category(df_all: pd.DataFrame):
    """Build bar chart for average price by category per company."""
    import numpy as np

    df_clean = df_all.copy()
    df_clean["category"] = df_clean["category"].replace("", np.nan)
    category_prices = (
        df_clean.groupby(["company", "category"], observed=True)["price"]
        .mean()
        .reset_index()
    )
    fig_category = px.bar(
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
    return fig_category


def show_pricing_intelligence(companies_data):
    """Display pricing intelligence dashboard"""
    st.header("Pricing Analysis Dashboard")

    # Combine all data for analysis
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    df_all = pd.DataFrame(all_data)

    # Normalized price per capacity
    # Calculate normalized prices
    df_all = get_capacity_analysis_data(companies_data)

    with st.expander("***Average Price by Capacity Range***", expanded=True):
        fig_bins = build_avg_price_by_capacity_range(df_all)
        st.plotly_chart(fig_bins, config={"responsive": True})

    with st.expander("***Min–Max Price Range by Capacity Bin***", expanded=False):
        fig_minmax = build_minmax_price_range_by_capacity_bin(df_all)
        st.plotly_chart(fig_minmax, config={"responsive": True})

    with st.expander("***Average Price by Category and Company***", expanded=False):
        fig_category = build_avg_price_by_category(df_all)
        st.plotly_chart(fig_category, config={"responsive": True})

    with st.expander("***Case Price Tiers (Min vs Max)***", expanded=False):
        fig_case_tier = show_case_price_tier_chart(all_data)
        st.plotly_chart(fig_case_tier, config={"responsive": True})
