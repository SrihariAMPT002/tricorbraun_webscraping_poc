import streamlit as st
from dashboard_utils.data_utils import load_data
from dashboard_utils import (
    setup_page_config,
    apply_custom_styling,
    create_header,
    create_navigation_menu,
    show_homepage,
    show_pricing_intelligence,
    show_assortment_kpis,
    show_product_fuzzy_match,
    show_chatbot,
)


# Configure page
setup_page_config()
apply_custom_styling()


def main():
    """Main dashboard application"""
    # Header
    create_header()

    # Load data
    try:
        companies_data = load_data()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    # Sidebar: Global filters
    with st.sidebar:
        st.markdown("##  Side Bar Navigation")
        st.divider()

        # Company filter (now using multiselect)
        company_options = sorted(companies_data.keys())
        if "company" not in st.session_state:
            st.session_state.company = (
                company_options  # Default: all companies selected
            )

        st.markdown("***Select companies:***")
        selected_companies = st.multiselect(
            "Companies",
            company_options,
            default=st.session_state.company,
            key="global_company",
        )
        # Guarantee state
        if not selected_companies:
            # If nothing selected, show all companies
            selected_companies = company_options
        st.session_state.company = selected_companies

        if set(selected_companies) != set(company_options):
            company_filtered_data = {
                k: companies_data.get(k, []) for k in selected_companies
            }
        else:
            company_filtered_data = companies_data

        st.divider()

        # Derive available market segments from company-filtered data
        all_segments = set()
        for data in company_filtered_data.values():
            for p in data:
                seg = p.get("market_segment") or "General"
                all_segments.add(seg)
        segment_options = ["All Segments"] + sorted(all_segments)
        if "market_segment" not in st.session_state:
            st.session_state.market_segment = "All Segments"

        st.markdown("***Select a Market Segment:***")
        selected_segment = st.selectbox(
            "Market Segment",
            segment_options,
            index=(
                segment_options.index(st.session_state.market_segment)
                if st.session_state.market_segment in segment_options
                else 0
            ),
            key="global_market_segment",
        )
        st.divider()
        # Persist selection
        st.session_state.market_segment = selected_segment

    # Apply global filters across all pages
    if (
        st.session_state.market_segment
        and st.session_state.market_segment != "All Segments"
    ):
        filtered_companies_data = {}
        for company, data in company_filtered_data.items():
            filtered = [
                p
                for p in data
                if (p.get("market_segment") or "General")
                == st.session_state.market_segment
            ]
            if filtered:
                filtered_companies_data[company] = filtered
    else:
        filtered_companies_data = company_filtered_data

    # Navigation menu
    page = create_navigation_menu()

    # Main content based on selected page
    if page == "Homepage":
        show_homepage(filtered_companies_data)
    elif page == "Pricing Analysis":
        show_pricing_intelligence(filtered_companies_data)
    elif page == "Assortment Analysis":
        show_assortment_kpis(filtered_companies_data)
    elif page == "Product Matching":
        if len(filtered_companies_data) == 1:
            st.error(
                "Only one company data selected. Please select at least two companies to compare."
            )
            st.stop()
        else:
            show_product_fuzzy_match(filtered_companies_data)
    elif page == "Chatbot":
        show_chatbot()


if __name__ == "__main__":
    main()
