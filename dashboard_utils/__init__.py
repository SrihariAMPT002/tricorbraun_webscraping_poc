"""
Dashboard utilities package.
Exports all UI functions for easy import.
"""

from .common import (
    setup_page_config,
    apply_custom_styling,
    create_header,
    create_navigation_menu,
    get_pinecone_vectorstore,
)

from .homepage import (
    show_homepage,
    display_sell_uom_data,
)

from .pricing import (
    show_pricing_intelligence,
    create_price_distribution_multiline_chart,
)

from .assortment import (
    show_assortment_kpis,
)

from .product_fuzzy_match import (
    show_product_fuzzy_match,
)

from .chatbot import (
    show_chatbot,
    query_products,
)

__all__ = [
    # Common utilities
    "setup_page_config",
    "apply_custom_styling",
    "create_header",
    "create_navigation_menu",
    "get_pinecone_vectorstore",
    # Homepage
    "show_homepage",
    "display_sell_uom_data",
    # Pricing
    "show_pricing_intelligence",
    "create_price_distribution_multiline_chart",
    # Assortment
    "show_assortment_kpis",
    # Product Matching
    "show_product_fuzzy_match",
    # Chatbot
    "show_chatbot",
    "query_products",
]
