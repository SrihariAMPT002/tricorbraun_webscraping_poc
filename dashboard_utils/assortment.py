"""
Assortment & Market KPI UI utilities.
This module contains all functions related to assortment analysis and market KPIs.
"""

from dashboard_utils.fuzzy_matching import normalize_capacity_fuzzy
import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Dict


def show_sku_count_by_color(df_all):
    """Display SKU count by color bar chart"""
    color_counts = df_all.groupby(["company", "color"]).size().reset_index(name="count")
    fig = px.bar(
        color_counts,
        x="color",
        y="count",
        color="company",
        color_discrete_map={
            "Berlin Packaging": "#e01b22",
            "Cary Company": "#1c2e5c",
            "TricorBraun": "#282828",
        },
        title="SKU Count by Color",
        barmode="group",
    )
    st.plotly_chart(
        fig,
        config={"responsive": True},
    )


def show_sku_count_by_material(df_all):
    """Display SKU count by material bar chart"""
    material_counts = (
        df_all.groupby(["company", "material"]).size().reset_index(name="count")
    )
    fig = px.bar(
        material_counts,
        x="material",
        y="count",
        color="company",
        color_discrete_map={
            "Berlin Packaging": "#e01b22",
            "Cary Company": "#1c2e5c",
            "TricorBraun": "#282828",
        },
        title="SKU Count by Material",
        barmode="group",
    )
    st.plotly_chart(
        fig,
        config={"responsive": True},
    )


def show_sku_count_by_capacity_range(df_all):
    """Display SKU count by capacity range bar chart"""
    capacity_counts = (
        df_all.groupby(["company", "capacity_range"], observed=True)
        .size()
        .reset_index(name="count")
    )
    fig = px.bar(
        capacity_counts,
        x="capacity_range",
        y="count",
        color="company",
        color_discrete_map={
            "Berlin Packaging": "#e01b22",
            "Cary Company": "#1c2e5c",
            "TricorBraun": "#282828",
        },
        title="SKU Count by Capacity Range",
        barmode="group",
    )
    st.plotly_chart(
        fig,
        config={"responsive": True},
    )


def show_capacity_range_summary(df_all):
    """Display capacity range summary table"""
    capacity_summary = (
        df_all.groupby(["company", "capacity_range"], observed=True)
        .agg({"price": ["count", "mean"], "capacity_ml": "mean"})
        .round(2)
    )

    capacity_summary.columns = ["SKU Count", "Avg Price ($)", "Avg Capacity (ml)"]
    capacity_summary = (
        capacity_summary.sort_values(by="company", ascending=True)
        .sort_values(by="Avg Capacity (ml)", ascending=False)
        .reset_index()
    )

    st.dataframe(capacity_summary, width="stretch")


def show_market_segment_distribution(df_all):
    """Display market segment distribution pie chart"""
    segment_counts = (
        df_all.groupby(["company", "market_segment"]).size().reset_index(name="count")
    )
    fig = px.pie(
        segment_counts,
        values="count",
        names="market_segment",
        title="Market Segment Distribution",
        color_discrete_map={
            "Berlin Packaging": "#e01b22",
            "Cary Company": "#1c2e5c",
            "TricorBraun": "#282828",
        },
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    st.plotly_chart(fig, config={"responsive": True})


def show_competitor_comparison_matrix(df_all):
    """Display competitor comparison matrix heatmap"""
    comparison_matrix = (
        df_all.groupby(["company", "market_segment"]).size().unstack(fill_value=0)
    )

    fig = px.imshow(
        comparison_matrix.values,
        labels=dict(x="Market Segment", y="Company", color="SKU Count"),
        x=comparison_matrix.columns,
        y=comparison_matrix.index,
        title="SKU Count by Company and Market Segment",
        color_continuous_scale="Reds",
    )
    st.plotly_chart(fig, config={"responsive": True})


def show_assortment_coverage_metrics(df_all, companies_data):
    """Display assortment coverage metrics table"""
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
    # st.write("Unique Shapes:", company_df["shape"].unique())

    coverage_df = pd.DataFrame(coverage_metrics)
    st.dataframe(coverage_df, width="stretch")


def show_stock_availability_chart(df_all):
    """
    Display a bar chart showing stock availability by company.
    Expects df_all to have columns 'company' and 'stock' (or 'availability').
    """
    import streamlit as st
    import plotly.express as px

    if "stock" not in df_all.columns:
        st.warning("⚠️ No stock information available to show chart.")
        return

    # Group by company and count number of in-stock SKUs
    # Assuming 'stock' is a boolean or string indicating availability
    # Group all 'backordered item' under a single category label
    df_all_mod = df_all.copy()

    def classify_stock(x):
        if isinstance(x, str):
            x_lower = x.lower()
            if "backordered" in x_lower:
                return "Backordered"
            elif (
                "week" in x_lower
                or "day" in x_lower
                or "lead time" in x_lower
                or "leadtime" in x_lower
                or "lead-times" in x_lower
            ):
                return "Lead Time"
            elif x_lower.strip() == "in stock":
                return "In Stock"
            elif x_lower.strip() == "out of stock":
                return "Out of Stock"
            elif "special order item" in x_lower:
                return "Special Order Item"
        return x

    df_all_mod["stock_status"] = df_all_mod["stock"].apply(classify_stock)
    stock_labels = df_all_mod["stock_status"].unique()

    # Make stock grouping ignore case by normalizing "stock_status" just in case, but plot on the canonical labels
    stock_summary = (
        df_all_mod.groupby(["company", "stock_status"])
        .size()
        .reset_index(name="SKU Count")
    )

    fig = px.bar(
        stock_summary,
        x="company",
        y="SKU Count",
        color="stock_status",
        barmode="group",
        title="Stock Availability by Company",
        labels={
            "company": "Company",
            "SKU Count": "Number of SKUs",
            "stock": "Stock Status",
        },
        color_discrete_map={
            "In Stock": "green",
            "Out of Stock": "red",
            "Low Stock": "orange",
        },
    )
    st.dataframe(stock_summary, width="stretch")

    st.plotly_chart(fig, config={"responsive": True})


def show_sku_by_country_of_manufacture(companies_data):
    """Display SKU count by country of manufacture bar chart"""
    st.info("No SKU's by Country of Manufacture data for Berlin Packaging")
    # Count SKUs per country grouped by company
    country_company_records = []
    for company in companies_data.keys():
        if company == "Berlin Packaging":
            continue
        for product in companies_data[company]:
            country = product.get("product_origin") or "Not Specified"
            country_company_records.append({"Company": company, "Country": country})

    countries_df = pd.DataFrame(country_company_records)
    sku_by_country_company = (
        countries_df.groupby(["Company", "Country"])
        .size()
        .reset_index(name="SKU Count")
    )

    # Display as a grouped bar chart
    fig = px.bar(
        sku_by_country_company,
        x="Country",
        y="SKU Count",
        color="Company",
        color_discrete_map={
            "Berlin Packaging": "#e01b22",
            "Cary Company": "#1c2e5c",
            "TricorBraun": "#282828",
        },
        barmode="group",
        title="SKU Count by Country of Manufacture and Company",
        text="SKU Count",
    )
    st.plotly_chart(
        fig,
        config={"responsive": True},
    )

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


def show_assortment_kpis(companies_data):
    """Display assortment and market KPI dashboard"""
    st.header("Assortment & Market KPI Dashboard")

    # Get assortment analysis data
    df_all = get_assortment_analysis_data(companies_data)

    # SKU Count by Color
    with st.expander("***SKU Count by Color***", expanded=True):
        show_sku_count_by_color(df_all)

    # SKU Count by Material
    with st.expander("***SKU Count by Material***", expanded=False):
        show_sku_count_by_material(df_all)

    # Capacity Range Analysis
    with st.expander("***Capacity Range Analysis***", expanded=False):
        # st.subheader("Capacity Range Analysis")
        show_sku_count_by_capacity_range(df_all)

    # Capacity Range Summary
    with st.expander("***Capacity Range Summary***", expanded=False):
        # st.subheader("Capacity Range Summary")
        show_capacity_range_summary(df_all)

    # Market Segment Analysis
    with st.expander("***Market Segment Analysis***", expanded=False):
        # st.subheader("Market Segment Analysis")
        show_market_segment_distribution(df_all)

    # Competitor Comparison Matrix
    with st.expander("***Competitor Comparison Matrix***", expanded=False):
        # st.subheader("Competitor Comparison Matrix")
        show_competitor_comparison_matrix(df_all)

    # Assortment Coverage Metrics
    with st.expander("***Assortment Coverage Metrics***", expanded=False):
        st.subheader("Assortment Coverage Metrics")
        show_assortment_coverage_metrics(df_all, companies_data)

    # SKU's by Country of Manufacture
    with st.expander("***SKU's by Country of Manufacture***", expanded=False):
        # st.subheader("SKU's by Country of Manufacture")
        show_sku_by_country_of_manufacture(companies_data)

    with st.expander("***Stock Availability Details***", expanded=False):
        st.subheader("Stock Availability by Company")
        show_stock_availability_chart(df_all)
