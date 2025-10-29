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

    # Sidebar: Global market segment filter
    with st.sidebar:
        st.markdown("##  Side Bar Navigation")
        st.divider()
        # Derive available market segments from loaded data
        all_segments = set()
        for data in companies_data.values():
            for p in data:
                seg = p.get("market_segment") or "General"
                all_segments.add(seg)
        segment_options = ["All Segments"] + sorted(all_segments)
        if "market_segment" not in st.session_state:
            st.session_state.market_segment = "All Segments"

        st.markdown("***Select a domain:***")
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

    # Apply global market segment filter across all pages
    if (
        st.session_state.market_segment
        and st.session_state.market_segment != "All Segments"
    ):
        filtered_companies_data = {}
        for company, data in companies_data.items():
            filtered = [
                p
                for p in data
                if (p.get("market_segment") or "General")
                == st.session_state.market_segment
            ]
            if filtered:
                filtered_companies_data[company] = filtered
    else:
        filtered_companies_data = companies_data

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
        show_product_fuzzy_match(filtered_companies_data)
    elif page == "Chatbot":
        show_chatbot()


if __name__ == "__main__":
    main()
