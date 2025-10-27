"""
Homepage UI utilities.
This module contains all functions related to the homepage display.
"""

import streamlit as st
import pandas as pd
from typing import Dict


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
            st.metric(label="Categories (Glass)", value=unique_categories, delta=None)

        with col4:
            in_stock_count = len(
                df[df["stock"].str.contains("In stock", case=False, na=False)]
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
            "normalised_capacity(ml)",
            "avg_price_per_unit",
            "color",
            "material",
            "shape",
            "stock",
        ]
        display_df = df[display_columns].copy()
        display_df.columns = [col for col in display_columns]

        st.dataframe(display_df, width="stretch", hide_index=True)

        # Sell UOM Data
        display_sell_uom_data(df, selected_company)

        # Comparison metrics across all companies
        st.subheader("🔀 Cross-Company Comparison")

        comparison_data = []
        for company, data in companies_data.items():
            df_comp = pd.DataFrame(data)
            in_stock_count = (
                df_comp["stock"].str.contains("In stock", case=False, na=False).sum()
            )
            out_of_stock_count = (
                df_comp["stock"]
                .str.contains("Out of stock", case=False, na=False)
                .sum()
            )
            comparison_data.append(
                {
                    "Company": company,
                    "Total SKUs": len(df_comp),
                    "Avg Price": df_comp["price"].mean(),
                    "Categories": df_comp["category"].nunique(),
                    "Market Segments": df_comp["market_segment"].nunique(),
                    "In Stock": in_stock_count,
                    "Out of Stock": out_of_stock_count,
                    "Uncertain Stock": len(df_comp)
                    - (out_of_stock_count + in_stock_count),
                }
            )

        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, width="stretch")


def display_sell_uom_data(df, selected_company):
    """
    Display pricing data using expanders with search functionality.
    Each product gets its own expander showing quantity breaks and pricing tiers.
    """
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"💰 {selected_company} Pricing Data")
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
            f"Total pricing tiers entries: {total_pricing_entries}  \n"
            f"Products with pricing tiers: {total_products_with_pricing}  (out of {total_products})  \n"
            f"Avg pricing tiers per product: {avg_pricing_per_product:.2f}"
        )

    # Search functionality
    search_term = st.text_input(
        "🔍 Search by SKU, Product Name, or Quantity:",
        placeholder="Enter SKU, product name, or quantity to filter...",
        key=f"search_uom_{selected_company}",
    )

    # Filter products based on search
    filtered_products = []
    for _, product in df.iterrows():
        if product.get("quantity_breaks") and len(product["quantity_breaks"]) > 0:
            # Check if search term matches any relevant field
            if not search_term or any(
                [
                    search_term.lower() in str(product.get("sku", "")).lower(),
                    search_term.lower() in str(product.get("name", "")).lower(),
                    any(
                        search_term.lower()
                        in str(break_item.get("quantity", "")).lower()
                        for break_item in product["quantity_breaks"]
                    ),
                ]
            ):
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
        with st.expander(
            f"📦 {product_name} → {quantity_breaks} tiers", expanded=False
        ):
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
                st.markdown("**📊 Pricing Tiers:**")

                # Create table for pricing tiers
                tier_data = []
                for break_item in product["quantity_breaks"]:
                    quantity_field = break_item.get("quantity", "")
                    unit_field = break_item.get("unit", "")
                    price_field = break_item.get("price", "")
                    price_per_unit_field = break_item.get("price_per_unit", "")

                    tier_data.append(
                        {
                            "Quantity": quantity_field,
                            "Unit": "ea" if unit_field == "" else unit_field,
                            "Price": price_field,
                            "Price/Unit": price_per_unit_field,
                        }
                    )

                if tier_data:
                    tier_df = pd.DataFrame(tier_data)
                    st.dataframe(tier_df, width="stretch", hide_index=True)
                else:
                    st.info("No pricing tier data available for this product.")
            else:
                st.info("No pricing data available for this product.")
