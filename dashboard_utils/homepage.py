"""
Homepage UI utilities.
This module contains all functions related to the homepage display.
"""

import streamlit as st
import pandas as pd, numpy as np
from typing import Dict
from dashboard_utils.utils import (
    get_product_capacity_bins,
    get_product_pricing_bins,
    get_capacity_bin,
    get_pricing_bin,
)
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


def show_homepage(companies_data):
    """Display homepage with company overview"""

    # Company selection
    company_names = list(companies_data.keys())
    st.subheader("Select a Company:")
    selected_company = st.selectbox(
        "Select Company", company_names, label_visibility="collapsed"
    )
    st.info(f"Now viewing data of : ***{selected_company}***")

    if selected_company:
        company_data = companies_data[selected_company]
        df = pd.DataFrame(company_data)

        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="Total SKUs", value=len(df))
        with col2:
            avg_price = df["price"].mean()
            st.metric(label="Average Price", value=f"${avg_price:.2f}")
        with col3:
            unique_categories = df["category"].replace("", np.nan).nunique()
            st.metric(label="Categories (Glass)", value=unique_categories)
        with col4:
            in_stock_count = len(
                df[df["stock"].str.contains("In stock", case=False, na=False)]
            )
            st.metric(label="In Stock", value=f"{in_stock_count}/{len(df)}")

        display_product_table(df, selected_company)

        display_sell_uom_data(df, selected_company)

        display_cross_company_comparison(companies_data)


def display_product_table(df, selected_company):
    """Display the product table with proper formatting."""
    st.subheader(f"{selected_company} Products")

    display_columns = [
        "sku",
        "name",
        "original_uom",
        "original_capacity",
        "normalised_capacity(ml)",
        "avg_price_per_unit",
        "color",
        "material",
        "shape",
        "stock",
    ]
    display_df = df[display_columns].copy()

    # Capitalize & beautify column names
    display_df.columns = [
        col.replace("_", " ").replace("(", " (").title().replace(" )", ")")
        for col in display_columns
    ]

    render_bold_table(display_df, height=500, key=f"product_table_{selected_company}")


def display_cross_company_comparison(companies_data):
    """Display comparison metrics across all companies."""
    st.subheader("🏢 Cross-Company Comparison")

    comparison_data = []

    for company, data in companies_data.items():
        df_comp = pd.DataFrame(data)
        df_comp_nonzero = df_comp[df_comp["price"] > 0]
        in_stock_count = (
            df_comp["stock"].str.contains("In stock", case=False, na=False).sum()
        )
        out_of_stock_count = (
            df_comp["stock"].str.contains("Out of stock", case=False, na=False).sum()
        )
        comparison_data.append(
            {
                "Company": company,
                "Total SKUs": len(df_comp),
                "Avg Price": round(df_comp_nonzero["price"].mean(), 4),
                "Avg Count": len(df_comp_nonzero),
                "Categories": df_comp["category"].replace("", np.nan).nunique(),
                "Market Segments": df_comp["market_segment"].nunique(),
                "In Stock": in_stock_count,
                "Out of Stock": out_of_stock_count,
                "Uncertain Stock": len(df_comp) - (out_of_stock_count + in_stock_count),
            }
        )

    comparison_df = pd.DataFrame(comparison_data)
    comparison_df.columns = [col.title() for col in comparison_df.columns]
    render_bold_table(comparison_df, height=150, key="cross_company_table")


def display_sell_uom_data(df, selected_company):
    """
    Display pricing data using expanders with search functionality.
    Each product gets its own expander showing quantity breaks and pricing tiers.
    """
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"{selected_company} Pricing Data")
    with col2:
        # Count total pricing entries and products with pricing breaks
        total_products = len(df)
        total_pricing_entries = sum(
            len(product.get("quantity_breaks", [])) for _, product in df.iterrows()
        )
        total_products_with_pricing = sum(
            1
            for _, product in df.iterrows()
            if product.get("quantity_breaks") and len(product["quantity_breaks"]) > 0
        )
        avg_pricing_per_product = (
            total_pricing_entries / total_products_with_pricing
            if total_products_with_pricing > 0
            else 0
        )

        st.info(
            f"Total pricing tiers entries: ***{total_pricing_entries}***     \n"
            f"Products with pricing tiers: ***{total_products_with_pricing}***     (out of {total_products})  \n"
            f"Avg pricing tiers per product: ***{avg_pricing_per_product:.2f}***"
        )

    # Filter options
    col1, col2 = st.columns(2)

    with col1:
        selected_capacity_bins = get_product_capacity_bins(selected_company)

    with col2:
        selected_pricing_bins = get_product_pricing_bins(selected_company)

    # Search functionality
    search_term = st.text_input(
        "Search by SKU, Product Name, or Quantity:",
        placeholder="Enter SKU, product name, or quantity to filter...",
        key=f"search_uom_{selected_company}",
    )

    # Capacity and pricing bin helpers are imported from utils

    # Filter products based on capacity, pricing, and search filters
    filtered_products = []
    for _, product in df.iterrows():
        if product.get("quantity_breaks") and len(product["quantity_breaks"]) > 0:
            # Check capacity filter
            capacity_ml = product.get("normalised_capacity(ml)")
            product_capacity_bin = get_capacity_bin(capacity_ml)
            capacity_match = (
                not selected_capacity_bins
                or product_capacity_bin in selected_capacity_bins
            )

            # Check pricing filter
            avg_price = product.get("avg_price_per_unit")
            product_pricing_bin = get_pricing_bin(avg_price)
            pricing_match = (
                not selected_pricing_bins
                or product_pricing_bin in selected_pricing_bins
            )

            # Check search filter
            search_match = not search_term or any(
                [
                    search_term.lower() in str(product.get("sku", "")).lower(),
                    search_term.lower() in str(product.get("name", "")).lower(),
                    any(
                        search_term.lower()
                        in str(break_item.get("quantity_of_packing", "")).lower()
                        for break_item in product["quantity_breaks"]
                    ),
                ]
            )

            # All filters must pass
            if capacity_match and pricing_match and search_match:
                filtered_products.append(product)

    # Limit display to 10 products
    display_products = filtered_products[:10]

    if not display_products:
        if search_term:
            st.warning(
                f"No pricing data available for products matching '{search_term}'"
            )
        else:
            st.info("No pricing data available for this company.")
        return

    # Show total count and pagination info
    if len(filtered_products) > 10:
        st.info(
            f"Showing 10 of {len(filtered_products)} products. Use search to narrow down results. Products without pricing tiers are not included in the search results."
        )

    # Display each product in an expander
    for product in display_products:
        product_name = product.get("name", "Unknown Product")
        quantity_breaks = len(product.get("quantity_breaks", []))

        # Create expander title
        with st.expander(f"{product_name} → {quantity_breaks} tiers", expanded=False):
            # Product basic info
            # Refactored: Use 3 columns for basic info (Product, SKU, Avg Price), factored out repeated get
            col1, col2, col3 = st.columns([2, 1, 1])
            url = product.get("url", "#")
            sku = product.get("sku", "N/A")
            avg_price = product.get("avg_price_per_unit", "N/A")
            with col1:
                st.markdown(f"**Product:** [{product_name}]({url})")
            with col2:
                st.markdown(f"**SKU:** [{sku}]({url})")
            with col3:
                st.markdown(f"**Avg Price:** {avg_price}")

            st.divider()

            # Display quantity breaks/pricing tiers
            if product.get("quantity_breaks"):
                st.markdown("**Pricing Tiers:**")

                # Create table for pricing tiers
                tier_data = []
                for break_item in product["quantity_breaks"]:
                    quantity_field = break_item.get("quantity_of_packing", "")
                    unit_field = break_item.get("type_of_packing", "")
                    price_field = break_item.get("price_per_packing", "")
                    price_per_unit_field = break_item.get("price_per_item", "")
                    items_per_unit = break_item.get("unit_quantity", "") or product.get(
                        "items_per_unit", ""
                    )

                    tier_data.append(
                        {
                            "Quantity": quantity_field,
                            "Unit": unit_field,
                            "Unit Quantity": items_per_unit,
                            "Price": price_field,
                            "Price/Each": price_per_unit_field,
                        }
                    )

                if tier_data:
                    tier_df = pd.DataFrame(tier_data)
                    st.dataframe(tier_df, width="stretch", hide_index=True)
                else:
                    st.info("No pricing tier data available for this product.")
            else:
                st.info("No pricing data available for this product.")


def render_bold_table(df: pd.DataFrame, height: int = 300, key: str = None):
    """Render AgGrid table with bold headers and right-aligned filters."""
    df.columns = [
        col.replace("(Ml)", "(ml)").replace("(ML)", "(ml)") for col in df.columns
    ]

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        headerClass="bold-header",
        resizable=True,
        sortable=True,
        filter=True,
        wrapHeaderText=True,
        autoHeaderHeight=True,
    )

    # Columns needing right-aligned filters
    right_align_filter_cols = [
        "Normalised Capacity (ml)",
        "Avg Price Per Unit",
        "Total Skus",
        "Categories",
        "Avg Price",
        "Market Segments",
    ]

    for col in df.columns:
        if col in right_align_filter_cols:
            gb.configure_column(col, headerClass="right-filter-header")

    grid_options = gb.build()

    custom_css = {
        ".ag-header-cell-text": {
            "font-weight": "bold !important",
            "color": "black !important",
        },
        ".ag-header-cell-label": {
            "justify-content": "flex-start !important",
        },
        ".ag-header-cell.right-filter-header .ag-header-cell-label": {
            "display": "flex !important",
            "justify-content": "space-between !important",
            "flex-direction": "row !important",
        },
        ".ag-header": {
            "background-color": "#f7f7f7 !important",
            "border-bottom": "1px solid #ddd !important",
        },
        ".ag-root-wrapper": {
            "border": "1px solid #e0e0e0 !important",
            "border-radius": "6px !important",
        },
    }

    AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.NO_UPDATE,
        fit_columns_on_grid_load=True,
        enable_enterprise_modules=False,
        custom_css=custom_css,
        theme="streamlit",
        height=height,
        key=key,
    )
