import streamlit as st
import pandas as pd

from .fuzzy_matching import (
    fuzzy_product_match,
    normalize_capacity_fuzzy,
    find_all_similar_products,
    find_similar_products_with_capacity_binning,
    get_similarity_summary,
    filter_products_by_price,
    filter_products_by_search,
)
from .utils import get_product_capacity_bins, get_product_pricing_bins


def filter_products_by_bins(products, capacity_bins, pricing_bins):
    """Filter products based on capacity and pricing bins"""
    filtered_products = []

    for product in products:
        # Check capacity bins
        capacity_match = True
        if capacity_bins:
            capacity_ml = normalize_capacity_fuzzy(product["capacity"], product["unit"])
            capacity_match = False

            for bin_range in capacity_bins:
                if bin_range == "0-50ml" and 0 <= capacity_ml <= 50:
                    capacity_match = True
                    break
                elif bin_range == "50-100ml" and 50 < capacity_ml <= 100:
                    capacity_match = True
                    break
                elif bin_range == "100-250ml" and 100 < capacity_ml <= 250:
                    capacity_match = True
                    break
                elif bin_range == "250-500ml" and 250 < capacity_ml <= 500:
                    capacity_match = True
                    break
                elif bin_range == "500-1000ml" and 500 < capacity_ml <= 1000:
                    capacity_match = True
                    break
                elif bin_range == "1000ml+" and capacity_ml > 1000:
                    capacity_match = True
                    break

        # Check pricing bins
        price_match = True
        if pricing_bins:
            price = product["price"]
            price_match = False

            for bin_range in pricing_bins:
                if bin_range == "$0-$0.50" and 0 <= price <= 0.50:
                    price_match = True
                    break
                elif bin_range == "$0.50-$1" and 0.50 < price <= 1:
                    price_match = True
                    break
                elif bin_range == "$1-$2" and 1 < price <= 2:
                    price_match = True
                    break
                elif bin_range == "$2-$3" and 2 < price <= 3:
                    price_match = True
                    break
                elif bin_range == "$3-$4" and 3 < price <= 4:
                    price_match = True
                    break
                elif bin_range == "$4-$5" and 4 < price <= 5:
                    price_match = True
                    break
                elif bin_range == "$5+" and price > 5:
                    price_match = True
                    break

        if capacity_match and price_match:
            filtered_products.append(product)

    return filtered_products


def show_all_similar_products(companies_data):
    """Display all similar products for TricorBraun products with 80%+ similarity"""

    st.subheader("🔍 All TricorBraun Product Similarities")
    st.write(
        "Find all similar products (80%+ match) for TricorBraun products across all companies"
    )

    # Check if TricorBraun exists
    if "TricorBraun" not in companies_data:
        st.error("TricorBraun data not found in the dataset")
        return

    # Add controls
    st.subheader("🔧 Filters & Controls")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        similarity_threshold = st.slider(
            "Similarity Threshold:",
            min_value=0.70,
            max_value=0.95,
            value=0.80,
            step=0.05,
            help="Minimum similarity score to show matches",
        )

    with col2:
        max_products_display = st.number_input(
            "Max Products to Display:",
            min_value=10,
            max_value=100,
            value=50,
            help="Maximum number of TricorBraun products to show",
        )

    with col3:
        exclude_zero_price = st.checkbox(
            "Exclude Zero Price Products",
            value=True,
            help="Filter out products with price <= $0.00",
        )

    # Run the analysis
    if st.button("🔍 Find All Similar Products", key="find_all_similar"):
        with st.spinner("Analyzing all TricorBraun products..."):
            # Get original count for summary
            original_tricorbraun_count = len(companies_data["TricorBraun"])

            all_matches = find_similar_products_with_capacity_binning(
                companies_data, similarity_threshold, exclude_zero_price
            )
            summary = get_similarity_summary(all_matches, original_tricorbraun_count)

            # Store results in session state
            st.session_state.all_similar_products_matches = all_matches
            st.session_state.all_similar_products_summary = summary
            st.session_state.all_similar_products_params = {
                "similarity_threshold": similarity_threshold,
                "exclude_zero_price": exclude_zero_price,
                "max_products_display": max_products_display,
            }

        if not all_matches:
            st.warning(
                f"No products found with {similarity_threshold:.0%} or above similarity"
            )
            return

    # Display results from session state if available
    if "all_similar_products_matches" in st.session_state:
        all_matches = st.session_state.all_similar_products_matches
        summary = st.session_state.all_similar_products_summary
        params = st.session_state.all_similar_products_params

        # Show filter information
        st.subheader("🔧 Applied Filters")
        filter_info = []
        if params["exclude_zero_price"]:
            filter_info.append("Excluding products with price ≤ $0.00")
        if not filter_info:
            filter_info.append("No filters applied")

        st.info(" | ".join(filter_info))

        # Display summary statistics
        st.subheader("📊 Summary Statistics")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total TricorBraun Products", summary["total_tricor_products"])
        with col2:
            st.metric("Filtered Products", summary["filtered_products"])
        with col3:
            st.metric("Products with Matches", summary["products_with_matches"])
        with col4:
            st.metric("Total Similar Products", summary["total_matches"])
        with col5:
            st.metric("Match Rate", f"{summary['match_rate']:.1%}")

        # Company breakdown
        st.subheader("🏢 Similar Products by Company")
        company_df_data = []
        for company, stats in summary["company_stats"].items():
            company_df_data.append(
                {
                    "Company": company,
                    "Similar Products": stats["count"],
                    "Average Similarity": f"{stats['avg_similarity']:.1%}",
                }
            )

        if company_df_data:
            company_df = pd.DataFrame(company_df_data)
            st.dataframe(company_df, use_container_width=True)

        # Display individual product matches
        st.subheader("📋 Detailed Product Matches")

        # Add search filter for matched products
        search_matched_products = st.text_input(
            "🔍 Filter Matched Products:",
            placeholder="Search within matched products by name, SKU, or price",
            help="Filter the matched products by product name, SKU, or price",
            key="search_matched_products",
        )

        # Apply search filter to matched products if provided
        filtered_matches = all_matches
        if search_matched_products:
            filtered_matches = {}
            for tricor_product_name, match_data in all_matches.items():
                tricor_product = match_data["tricorbraun_product"]
                similar_products = match_data["similar_products"]

                # Check if TricorBraun product matches search
                tricor_matches = (
                    search_matched_products.lower() in tricor_product["name"].lower()
                    or search_matched_products.lower()
                    in str(tricor_product.get("sku", "")).lower()
                    or search_matched_products.lower()
                    in f"${tricor_product['price']:.2f}"
                )

                # Check if any similar products match search
                filtered_similar = []
                for match in similar_products:
                    product = match["product"]
                    if (
                        search_matched_products.lower() in product["name"].lower()
                        or search_matched_products.lower()
                        in str(product.get("sku", "")).lower()
                        or search_matched_products.lower() in f"${product['price']:.2f}"
                    ):
                        filtered_similar.append(match)

                # Include this match if TricorBraun product matches or if any similar products match
                if tricor_matches or filtered_similar:
                    filtered_matches[tricor_product_name] = {
                        "tricorbraun_product": tricor_product,
                        "similar_products": (
                            filtered_similar if filtered_similar else similar_products
                        ),
                        "capacity_bracket": match_data.get(
                            "capacity_bracket", "Unknown"
                        ),
                    }

        # Limit the number of products displayed
        displayed_products = list(filtered_matches.items())[
            : params["max_products_display"]
        ]

        for i, (tricor_product_name, match_data) in enumerate(displayed_products, 1):
            tricor_product = match_data["tricorbraun_product"]
            similar_products = match_data["similar_products"]

            # Create expandable section for each TricorBraun product
            capacity_bracket = match_data.get("capacity_bracket", "Unknown")
            with st.expander(
                f"#{i} {tricor_product_name} - {len(similar_products)} matches ({capacity_bracket})"
            ):
                # Display TricorBraun product details
                st.write("**🏢 TricorBraun Product:**")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(f"**Name:** {tricor_product['name']}")
                    st.write(
                        f"**Capacity:** {tricor_product['capacity']} {tricor_product['unit']}"
                    )
                with col2:
                    st.write(f"**Price:** ${tricor_product['price']:.2f}")
                    st.write(f"**Material:** {tricor_product.get('material', 'N/A')}")
                with col3:
                    st.write(f"**Color:** {tricor_product.get('color', 'N/A')}")
                    st.write(f"**Shape:** {tricor_product.get('shape', 'N/A')}")

                # Display similar products
                st.write(f"**🔍 Similar Products ({len(similar_products)} matches):**")

                # Group by company
                products_by_company = {}
                for match in similar_products:
                    company = match["company"]
                    if company not in products_by_company:
                        products_by_company[company] = []
                    products_by_company[company].append(match)

                # Display products by company
                for company, matches in products_by_company.items():
                    st.write(f"**{company} ({len(matches)} products):**")

                    for j, match in enumerate(matches, 1):
                        product = match["product"]
                        similarity = match["similarity"]

                        # Color code based on similarity
                        if similarity >= 0.95:
                            color_emoji = "🟢"
                        elif similarity >= 0.90:
                            color_emoji = "🟡"
                        else:
                            color_emoji = "🔴"

                        with st.container():
                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                st.write(f"{color_emoji} **{j}.** {product['name']}")
                                st.write(f"**Similarity:** {similarity:.1%}")

                            with col2:
                                st.write(
                                    f"**Capacity:** {product['capacity']} {product['unit']}"
                                )
                                st.write(f"**Diff:** {match['capacity_diff_ml']:.1f}ml")

                            with col3:
                                st.write(f"**Price:** ${product['price']:.2f}")
                                st.write(f"**Diff:** ${match['price_diff']:.2f}")

                            with col4:
                                st.write(
                                    f"**Material:** {product.get('material', 'N/A')}"
                                )
                                st.write(f"**Color:** {product.get('color', 'N/A')}")

                        st.divider()

        # Show if there are more products
        if len(filtered_matches) > params["max_products_display"]:
            st.info(
                f"Showing first {params['max_products_display']} products. Total filtered TricorBraun products with matches: {len(filtered_matches)}"
            )
        elif search_matched_products and len(filtered_matches) != len(all_matches):
            st.info(
                f"Filtered results: {len(filtered_matches)} out of {len(all_matches)} total matches"
            )


def show_product_fuzzy_match(companies_data):
    """Enhanced fuzzy matching component with TricorBraun on left and multiselect for other companies"""

    st.subheader("🔍 Product Similarity Matching")
    st.write(
        "Select a TricorBraun product and find similar products from other companies"
    )

    # Add filtering controls
    st.subheader("🔧 Filters")
    col1, col2 = st.columns([1, 1])

    with col1:
        exclude_zero_price = st.checkbox(
            "Exclude Zero Price Products",
            value=True,
            help="Filter out products with price <= $0.00",
        )

    with col2:
        pass  # Search filter moved to results section

    # Get company names
    company_names = list(companies_data.keys())

    # Ensure TricorBraun exists
    if "TricorBraun" not in company_names:
        st.error("TricorBraun data not found in the dataset")
        return

    # Create two columns
    col1, col2 = st.columns([1, 1])

    with col1:
        st.write("**🏢 TricorBraun Products**")

        # Get TricorBraun products
        tricorbraun_products = companies_data["TricorBraun"]

        # Apply price filter
        filtered_tricorbraun = filter_products_by_price(
            tricorbraun_products, exclude_zero_price
        )

        # Add filtering options for TricorBraun products
        # st.write("**Filters:**")
        col1_fil, col2_fil = st.columns([1, 1])
        with col1_fil:
            capacity_bins = get_product_capacity_bins("tricorbraun")
        with col2_fil:
            pricing_bins = get_product_pricing_bins("tricorbraun")

        # Filter TricorBraun products by bins
        filtered_tricorbraun = filter_products_by_bins(
            filtered_tricorbraun, capacity_bins, pricing_bins
        )

        if not filtered_tricorbraun:
            st.warning("No products match the selected filters")
            return

        # Product selection
        selected_product = st.selectbox(
            "Select TricorBraun Product:",
            [p["name"] for p in filtered_tricorbraun],
            key="tricorbraun_product",
        )

        if selected_product:
            # Get selected product data
            selected_product_data = next(
                p for p in filtered_tricorbraun if p["name"] == selected_product
            )

            # Display selected product details
            st.write("**Selected Product Details:**")
            st.write(f"**Name:** {selected_product_data['name']}")
            st.write(
                f"**Capacity:** {selected_product_data['capacity']} {selected_product_data['unit']}"
            )
            st.write(f"**Price:** ${selected_product_data['price']:.2f}")

    with col2:
        st.write("**🏢 Compare With Other Companies**")

        # Get other companies (excluding TricorBraun)
        other_companies = [name for name in company_names if name != "TricorBraun"]

        if not other_companies:
            st.warning("No other companies found for comparison")
            return

        # Multiselect for other companies
        selected_companies = st.multiselect(
            "Select Companies to Compare:",
            other_companies,
            default=(
                other_companies[:2] if len(other_companies) >= 2 else other_companies
            ),
            key="compare_companies",
        )

        if not selected_companies:
            st.info("Please select at least one company to compare")
            return

    # Find similar products
    if st.button("🔍 Find Similar Products", key="find_similar"):
        if "selected_product_data" in locals():
            similar_products = []

            # Calculate similarity scores for all products from selected companies
            for company in selected_companies:
                company_products = companies_data[company]

                # Apply price filter to comparison products
                filtered_company_products = filter_products_by_price(
                    company_products, exclude_zero_price
                )

                for product in filtered_company_products:
                    similarity_score = fuzzy_product_match(
                        selected_product_data, product
                    )
                    similar_products.append(
                        {
                            "company": company,
                            "product": product,
                            "similarity": similarity_score,
                        }
                    )

            # Filter products with 85% or above similarity
            high_similarity_products = [
                item for item in similar_products if item["similarity"] >= 0.85
            ]

            # Sort by similarity score (highest first)
            high_similarity_products.sort(key=lambda x: x["similarity"], reverse=True)

            # Store results in session state
            st.session_state.fuzzy_match_results = {
                "high_similarity_products": high_similarity_products,
                "selected_product_data": selected_product_data,
                "selected_companies": selected_companies,
                "exclude_zero_price": exclude_zero_price,
            }

    # Display results from session state if available
    if "fuzzy_match_results" in st.session_state:
        results = st.session_state.fuzzy_match_results
        high_similarity_products = results["high_similarity_products"]
        selected_product_data = results["selected_product_data"]
        selected_companies = results["selected_companies"]
        exclude_zero_price = results["exclude_zero_price"]

        # Display results
        st.subheader("📊 High Similarity Products Found (85%+)")

        # Add search filter for matched products
        search_matched_products = st.text_input(
            "🔍 Filter Matched Products:",
            placeholder="Search within matched products by name, SKU, or price",
            help="Filter the matched products by product name, SKU, or price",
            key="search_matched_products_fuzzy",
        )

        # Apply search filter to matched products if provided
        filtered_similar_products = high_similarity_products
        if search_matched_products:
            filtered_similar_products = []
            for item in high_similarity_products:
                product = item["product"]
                if (
                    search_matched_products.lower() in product["name"].lower()
                    or search_matched_products.lower()
                    in str(product.get("sku", "")).lower()
                    or search_matched_products.lower() in f"${product['price']:.2f}"
                ):
                    filtered_similar_products.append(item)

        if not filtered_similar_products:
            st.info(
                "No products found with 85% or above similarity"
                + (
                    f" matching '{search_matched_products}'"
                    if search_matched_products
                    else ""
                )
            )
            return

        # Group products by company
        products_by_company = {}
        for item in filtered_similar_products:
            company = item["company"]
            if company not in products_by_company:
                products_by_company[company] = []
            products_by_company[company].append(item)

        # Display products in separate columns for each company
        if products_by_company:
            # Create columns dynamically based on number of companies
            num_companies = len(products_by_company)
            cols = st.columns(num_companies)

            for i, (company, products) in enumerate(products_by_company.items()):
                with cols[i]:
                    st.write(f"**🏢 {company}**")
                    st.write(f"*{len(products)} high similarity products*")

                    for j, item in enumerate(products, 1):
                        product = item["product"]
                        similarity = item["similarity"]

                        # Color code based on similarity score
                        if similarity >= 0.95:
                            color = "🟢"
                        elif similarity >= 0.9:
                            color = "🟡"
                        else:
                            color = "🔴"

                        with st.expander(
                            f"{color} #{j} {product['name']} - {similarity:.1%}"
                        ):
                            st.write(f"**Name:** {product['name']}")
                            st.write(
                                f"**Capacity:** {product['capacity']} {product['unit']}"
                            )
                            st.write(f"**Price:** ${product['price']:.2f}")
                            st.write(f"**Similarity:** {similarity:.1%}")

                            # Show comparison with selected product
                            st.write("**vs TricorBraun:**")
                            cap_diff = abs(
                                normalize_capacity_fuzzy(
                                    product["capacity"], product["unit"]
                                )
                                - normalize_capacity_fuzzy(
                                    selected_product_data["capacity"],
                                    selected_product_data["unit"],
                                )
                            )
                            price_diff = abs(
                                product["price"] - selected_product_data["price"]
                            )

                            st.write(f"Capacity diff: {cap_diff:.1f}ml")
                            st.write(f"Price diff: ${price_diff:.2f}")

        # Summary statistics for high similarity products
        st.subheader("📈 Summary Statistics (85%+ Similarity)")

        if filtered_similar_products:
            avg_similarity = sum(
                item["similarity"] for item in filtered_similar_products
            ) / len(filtered_similar_products)
            max_similarity = max(
                item["similarity"] for item in filtered_similar_products
            )
            min_similarity = min(
                item["similarity"] for item in filtered_similar_products
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average Similarity", f"{avg_similarity:.1%}")
            with col2:
                st.metric("Highest Similarity", f"{max_similarity:.1%}")
            with col3:
                st.metric("Lowest Similarity", f"{min_similarity:.1%}")

            # Company breakdown for high similarity products
            st.write("**High Similarity Products by Company:**")
            company_stats = {}
            for item in filtered_similar_products:
                company = item["company"]
                if company not in company_stats:
                    company_stats[company] = []
                company_stats[company].append(item["similarity"])

            for company, scores in company_stats.items():
                avg_score = sum(scores) / len(scores)
                st.write(
                    f"• **{company}:** {avg_score:.1%} average ({len(scores)} products)"
                )

            # Show total count
            total_text = f"**Total high similarity products found:** {len(filtered_similar_products)}"
            if search_matched_products and len(filtered_similar_products) != len(
                high_similarity_products
            ):
                total_text += f" (filtered from {len(high_similarity_products)} total)"
            st.write(total_text)
