import streamlit as st
import pandas as pd

from .data_utils import fuzzy_product_match, normalize_capacity_fuzzy
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


def show_product_fuzzy_match(companies_data):
    """Enhanced fuzzy matching component with TricorBraun on left and multiselect for other companies"""

    st.subheader("🔍 Product Similarity Matching")
    st.write(
        "Select a TricorBraun product and find similar products from other companies"
    )

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

        # Add filtering options for TricorBraun products
        # st.write("**Filters:**")
        col1_fil, col2_fil = st.columns([1, 1])
        with col1_fil:
            capacity_bins = get_product_capacity_bins("tricorbraun")
        with col2_fil:
            pricing_bins = get_product_pricing_bins("tricorbraun")

        # Filter TricorBraun products
        filtered_tricorbraun = filter_products_by_bins(
            tricorbraun_products, capacity_bins, pricing_bins
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

                for product in company_products:
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

            # Display results
            st.subheader("📊 High Similarity Products Found (85%+)")

            if not high_similarity_products:
                st.info("No products found with 85% or above similarity")
                return

            # Group products by company
            products_by_company = {}
            for item in high_similarity_products:
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

            if high_similarity_products:
                avg_similarity = sum(
                    item["similarity"] for item in high_similarity_products
                ) / len(high_similarity_products)
                max_similarity = max(
                    item["similarity"] for item in high_similarity_products
                )
                min_similarity = min(
                    item["similarity"] for item in high_similarity_products
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
                for item in high_similarity_products:
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
                st.write(
                    f"**Total high similarity products found:** {len(high_similarity_products)}"
                )
