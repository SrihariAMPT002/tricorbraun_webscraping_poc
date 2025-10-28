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

    # Navigation menu
    page = create_navigation_menu()

    # Main content based on selected page
    if page == "Homepage":
        show_homepage(companies_data)
    elif page == "Pricing Analysis":
        show_pricing_intelligence(companies_data)
    elif page == "Assortment Analysis":
        show_assortment_kpis(companies_data)
    elif page == "Product Matching":
        show_product_fuzzy_match(companies_data)
    elif page == "Chatbot":
        show_chatbot()


if __name__ == "__main__":
    main()
