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

        st.dataframe(display_df, width="stretch", hide_index=True)

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
        st.dataframe(comparison_df, width="stretch")


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
                    st.dataframe(tier_df, width="stretch", hide_index=True)
                else:
                    st.info("No pricing tier data available for this product.")
            else:
                st.info("No sell UOM data available for this product.")
