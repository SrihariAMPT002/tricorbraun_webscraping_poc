import streamlit as st
import pandas as pd
import os
import json

from .fuzzy_matching import (
    fuzzy_product_match,
    normalize_capacity_fuzzy,
    find_similar_products_with_capacity_binning,
    get_similarity_summary,
    filter_products_by_price,
)
from .utils import get_product_capacity_bins, get_product_pricing_bins


CACHE_FILE = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "demo_batch_data",
        "fuzzy_match_cache.json",
    )
)


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
    """Product matching with two tabs (Per Item, All Products) and pagination."""

    st.subheader("Product Similarity")
    tab_per_item, tab_all = st.tabs(["Per Item", "All Products"])

    with tab_per_item:
        render_per_item_matching_tab(companies_data)

    with tab_all:
        render_all_products_matching_tab(companies_data)


def render_per_item_matching_tab(companies_data):
    """Render the product matching interface for a single TricorBraun item."""
    company_names = list(companies_data.keys())
    if "TricorBraun" not in company_names:
        st.error("TricorBraun data not found in the dataset")
        return

    st.write(
        "Select a TricorBraun product and find similar products from other companies"
    )

    col1, _ = st.columns([1, 1])
    with col1:
        exclude_zero_price_item = st.checkbox(
            "Exclude Zero Price Products",
            value=True,
            help="Filter out products with price <= $0.00",
            key="exclude_zero_price_item",
        )

    col1_pi, col_divider, col2_pi = st.columns(
        [1, 0.1, 1]
    )  # Adjust the ratio for the divider width

    with col1_pi:
        st.write("**Filters**")
        tricorbraun_products = companies_data["TricorBraun"]
        filtered_tricorbraun = filter_products_by_price(
            tricorbraun_products, exclude_zero_price_item
        )
        col1_fil, col2_fil = st.columns([1, 1])
        with col1_fil:
            capacity_bins = get_product_capacity_bins("tricorbraun")
        with col2_fil:
            pricing_bins = get_product_pricing_bins("tricorbraun")
        filtered_tricorbraun = filter_products_by_bins(
            filtered_tricorbraun, capacity_bins, pricing_bins
        )
        if not filtered_tricorbraun:
            st.warning("No products match the selected filters")
            st.stop()
        st.write("**Compare With Other Companies**")
        other_companies = [name for name in company_names if name != "TricorBraun"]
        if not other_companies:
            st.warning("No other companies found for comparison")
            st.stop()
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
            st.stop()

    with col_divider:
        st.html(
            """
            <div class="divider-vertical-line"></div>
            <style>
                .divider-vertical-line {
                    border-left: 1px solid rgba(49, 51, 63, 0.2);
                    height: 320px;
                    margin: auto;
                }
            </style>
        """
        )

    selected_product_data = None
    with col2_pi:
        st.write("**TricorBraun Products**")
        selected_product = st.selectbox(
            "Select TricorBraun Product:",
            [p["name"] for p in filtered_tricorbraun],
            key="tricorbraun_product",
        )
        if selected_product:
            previous_selection = st.session_state.get("fuzzy_match_selected_product")
            if previous_selection != selected_product:
                st.session_state.fuzzy_match_selected_product = selected_product
                st.session_state.fuzzy_match_results = None
            selected_product_data = next(
                p for p in filtered_tricorbraun if p["name"] == selected_product
            )
            with st.container(border=True):
                st.write("**Selected Product Details:**")
                st.write(f"**Name:** {selected_product_data['name']}")
                st.write(
                    f"**Capacity:** {selected_product_data['capacity']} {selected_product_data['unit']}"
                )
                st.write(f"**Avg Price:** ${selected_product_data['price']:.2f}")

    results = st.session_state.get("fuzzy_match_results")

    if (
        st.button("Find Similar Products", key="find_similar", type="primary")
        and selected_product_data
    ):
        results = compute_fuzzy_match_results(
            companies_data,
            selected_product_data,
            selected_companies,
            exclude_zero_price_item,
        )
        st.session_state.fuzzy_match_results = results
        cache_fuzzy_match_results(results)

    if results is None and selected_product_data:
        cached_results = load_cached_fuzzy_match_results()
        if (
            cached_results
            and cached_results.get("selected_product_data", {}).get("name")
            == selected_product_data["name"]
        ):
            cached_companies = set(cached_results.get("selected_companies", []))
            if (
                cached_companies == set(selected_companies)
                and cached_results.get("exclude_zero_price") == exclude_zero_price_item
            ):
                results = cached_results
                st.session_state.fuzzy_match_results = results

    if results:
        render_fuzzy_match_results(results)


def render_all_products_matching_tab(companies_data):
    """Render the batch matching interface for all TricorBraun products."""

    st.write(
        "Find similar products for all TricorBraun items using capacity-binned fuzzy matching (85%+)."
    )
    col1_b, col2_b = st.columns([1, 1], vertical_alignment="center")
    with col1_b:
        batch_similarity_threshold = st.slider(
            "Batch Similarity Threshold",
            min_value=0.85,
            max_value=0.95,
            value=0.85,
            step=0.05,
            help="Threshold for batch matching of all TricorBraun products",
            key="batch_similarity_threshold",
        )

    with col2_b:
        exclude_zero_price_batch = st.checkbox(
            "Exclude Zero Price Products",
            value=True,
            help="Filter out products with price <= $0.00",
            key="exclude_zero_price_batch",
        )

    batch_output_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            f"demo_batch_data/batch_similarity_{batch_similarity_threshold}",
            f"all_similar_products_{batch_similarity_threshold}.json",
        )
    )

    # --- Trigger batch matching ---
    if st.button("Find All Similar Products (Batch)", key="find_all_similar_batch"):
        with st.spinner("Finding similar products for all TricorBraun items..."):
            try:
                original_tricorbraun_count = len(companies_data.get("TricorBraun", []))
                all_matches = find_similar_products_with_capacity_binning(
                    companies_data,
                    similarity_threshold=batch_similarity_threshold,
                    exclude_zero_price=exclude_zero_price_batch,
                )
                summary = get_similarity_summary(
                    all_matches, original_tricorbraun_count
                )
                st.session_state.all_similar_batch = {
                    "matches": all_matches,
                    "summary": summary,
                    "params": {
                        "similarity_threshold": batch_similarity_threshold,
                        "exclude_zero_price": exclude_zero_price_batch,
                    },
                }

                os.makedirs(os.path.dirname(batch_output_path), exist_ok=True)
                with open(batch_output_path, "w", encoding="utf-8") as f:
                    json.dump(
                        st.session_state.all_similar_batch,
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            except Exception as e:
                st.error(f"Batch matching failed: {e}")

    # --- Load from disk if session data missing ---
    if "all_similar_batch" not in st.session_state and os.path.isfile(
        batch_output_path
    ):
        try:
            with open(batch_output_path, "r", encoding="utf-8") as f:
                st.session_state.all_similar_batch = json.load(f)
        except Exception:
            pass

    # --- Display results if available ---
    if "all_similar_batch" in st.session_state:
        display_all_similar_products(
            st.session_state.all_similar_batch, batch_output_path
        )


def display_all_similar_products(batch_data: dict, batch_output_path: str):
    """Display the matched products summary and results grouped by capacity."""

    summary = batch_data.get("summary", {})
    all_matches = batch_data.get("matches", {})

    with st.container(border=True):
        st.subheader("Summary")
        if summary:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total TricorBraun", summary.get("total_tricor_products", 0))
            with col2:
                st.metric("Filtered Products", summary.get("filtered_products", 0))
            with col3:
                st.metric("With Matches", summary.get("products_with_matches", 0))
            with col4:
                st.metric("Total Matches", summary.get("total_matches", 0))

    st.subheader("Results grouped by normalized capacity (ml)")
    capacity_groups = {}
    for tricor_name, match_data in all_matches.items():
        tricor = match_data["tricorbraun_product"]
        cap_ml = normalize_capacity_fuzzy(tricor["capacity"], tricor["unit"])
        capacity_groups.setdefault(cap_ml, []).append((tricor_name, match_data))

    sorted_caps = sorted(capacity_groups.keys())
    groups_total = len(sorted_caps)

    col_capacity, col_total_page = st.columns([1, 1])
    with col_capacity:
        groups_per_page = st.number_input(
            "Capacity groups per page", 1, 50, 5, key="batch_groups_per_page"
        )
    groups_total_pages = max(1, (groups_total + groups_per_page - 1) // groups_per_page)
    with col_total_page:
        groups_page = st.number_input(
            "Page", 1, groups_total_pages, 1, key="batch_groups_page"
        )

    gstart = (groups_page - 1) * groups_per_page
    gend = gstart + groups_per_page
    page_caps = sorted_caps[gstart:gend]

    for cap_ml in page_caps:
        group_items = capacity_groups[cap_ml]
        with st.expander(f"{cap_ml:.1f} ml • {len(group_items)} TricorBraun items"):
            for idx, (tricor_name, match_data) in enumerate(group_items, 1):
                tricor_product = match_data["tricorbraun_product"]
                similar_products = match_data["similar_products"]

                st.markdown(f"**{idx}. {tricor_name}**  ")
                cols = st.columns(3)
                with cols[0]:
                    st.write(
                        f"Capacity: {tricor_product['capacity']} {tricor_product['unit']}"
                    )
                with cols[1]:
                    st.write(f"Price: ${tricor_product['price']:.2f}")
                with cols[2]:
                    st.write(f"Material: {tricor_product.get('material', 'N/A')}")

                products_by_company = {}
                for match in similar_products:
                    products_by_company.setdefault(match["company"], []).append(match)

                for company, matches in products_by_company.items():
                    st.subheader(
                        f"**{company} ({len(matches)} products):**", divider="gray"
                    )
                    for j, match in enumerate(matches, 1):
                        product = match["product"]
                        similarity = match["similarity"]
                        with st.expander(f"#{j} {product['name']} - {similarity:.1%}"):
                            c1, c2, c3, c4 = st.columns(4)
                            with c1:
                                st.write(
                                    f"Capacity: {product['capacity']} {product['unit']}"
                                )
                                st.write(
                                    f"Δ Capacity: {match['capacity_diff_ml']:.1f} ml"
                                )
                            with c2:
                                st.write(f"Price: ${product['price']:.2f}")
                                st.write(f"Δ Price: ${match['price_diff']:.2f}")
                            with c3:
                                st.write(f"Material: {product.get('material', 'N/A')}")
                                st.write(f"Color: {product.get('color', 'N/A')}")
                            with c4:
                                st.write(f"SKU: {product.get('sku', 'N/A')}")

    st.caption(
        f"Page {groups_page} of {groups_total_pages} • {groups_total} capacity groups"
    )

    try:
        with open(batch_output_path, "rb") as f:
            st.download_button(
                label="Download All Similar Products JSON",
                data=f,
                file_name="all_similar_products.json",
                mime="application/json",
            )
    except Exception:
        pass


def compute_fuzzy_match_results(
    companies_data,
    selected_product_data,
    selected_companies,
    exclude_zero_price_item,
):
    """Compute high-similarity products for the selected TricorBraun item."""

    similar_products = []
    for company in selected_companies:
        company_products = companies_data[company]
        filtered_company_products = filter_products_by_price(
            company_products, exclude_zero_price_item
        )
        for product in filtered_company_products:
            similarity_score = fuzzy_product_match(selected_product_data, product)
            similar_products.append(
                {
                    "company": company,
                    "product": product,
                    "similarity": similarity_score,
                }
            )

    high_similarity_products = [
        item for item in similar_products if item["similarity"] >= 0.85
    ]
    high_similarity_products.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "high_similarity_products": high_similarity_products,
        "selected_product_data": selected_product_data,
        "selected_companies": selected_companies,
        "exclude_zero_price": exclude_zero_price_item,
    }


def cache_fuzzy_match_results(results):
    """Persist fuzzy match results to disk for reuse."""

    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        st.toast("Cached fuzzy match results for next run.")
    except Exception as e:
        st.warning(f"Could not write cache file: {e}")


def load_cached_fuzzy_match_results():
    """Load previously cached fuzzy match results if available."""

    if not os.path.isfile(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.warning(f"Could not load cache file: {e}")
        return None


def render_fuzzy_match_results(results):
    """Display fuzzy match results in the UI."""

    high_similarity_products = results.get("high_similarity_products", [])
    selected_product_data = results.get("selected_product_data")
    if not high_similarity_products or not selected_product_data:
        st.info("No high similarity products found.")
        return

    st.divider()
    st.subheader("High Similarity Products Found (85%+)")
    search_matched_products = st.text_input(
        "Filter Matched Products:",
        placeholder="Search within matched products by name, SKU, or price",
        key="search_matched_products_fuzzy",
    )
    filtered_similar_products = high_similarity_products
    if search_matched_products:
        query = search_matched_products.lower()
        filtered_similar_products = []
        for item in high_similarity_products:
            product = item["product"]
            if (
                query in product.get("name", "").lower()
                or query in str(product.get("sku", "")).lower()
                or query in f"${product.get('price', 0):.2f}"
            ):
                filtered_similar_products.append(item)

    total = len(filtered_similar_products)
    col_per_item, col_total_page = st.columns([1, 1])
    with col_per_item:
        per_page = st.number_input(
            "Items per page", 5, 100, 20, key="per_item_per_page"
        )
    total_pages = max(1, (total + per_page - 1) // per_page)
    with col_total_page:
        page = st.number_input("Page", 1, total_pages, 1, key="per_item_page")
    start = (page - 1) * per_page
    end = start + per_page
    page_items = filtered_similar_products[start:end]
    if not page_items:
        st.info("No products found with the current filters.")
        return

    products_by_company = {}
    for item in page_items:
        products_by_company.setdefault(item["company"], []).append(item)
    cols = st.columns(len(products_by_company)) if products_by_company else []
    for i, (company, products) in enumerate(products_by_company.items()):
        with cols[i]:
            st.write(f"**{company}**")
            st.write(f"*{len(products)} items on this page*")
            for j, item in enumerate(products, 1):
                product = item["product"]
                similarity = item["similarity"]
                with st.expander(f"#{j} {product.get('name','')} - {similarity:.1%}"):
                    st.write(f"**Name:** {product.get('name','')}")
                    st.write(
                        f"**Capacity:** {product.get('capacity')} {product.get('unit')}"
                    )
                    st.write(f"**Price:** ${product.get('price',0):.2f}")
                    st.write(f"**Similarity:** {similarity:.1%}")
                    st.write("**vs TricorBraun:**")
                    cap_diff = abs(
                        normalize_capacity_fuzzy(
                            product.get("capacity"), product.get("unit")
                        )
                        - normalize_capacity_fuzzy(
                            selected_product_data["capacity"],
                            selected_product_data["unit"],
                        )
                    )
                    price_diff = abs(
                        product.get("price", 0) - selected_product_data["price"]
                    )
                    st.write(f"Capacity diff: {cap_diff:.1f}ml")
                    st.write(f"Price diff: ${price_diff:.2f}")
    st.caption(f"Page {page} of {total_pages} • {total} total results")
