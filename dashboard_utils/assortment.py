"""
Assortment & Market KPI UI utilities.
This module contains all functions related to assortment analysis and market KPIs.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Dict
from .data_utils import get_assortment_analysis_data


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
        st.plotly_chart(fig, width="stretch")

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
        st.plotly_chart(fig, width="stretch")

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
    st.plotly_chart(fig, width="stretch")

    # Combined capacity analysis table
    st.subheader("📊 Capacity Range Summary")

    capacity_summary = (
        df_all.groupby(["company", "capacity_range"])
        .agg({"price": ["count", "mean"], "capacity_ml": "mean"})
        .round(2)
    )

    capacity_summary.columns = ["SKU Count", "Avg Price ($)", "Avg Capacity (ml)"]
    capacity_summary = capacity_summary.reset_index()

    st.dataframe(capacity_summary, width="stretch")

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
    st.plotly_chart(fig, width="stretch")

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
    st.plotly_chart(fig, width="stretch")

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
    st.dataframe(coverage_df, width="stretch")
