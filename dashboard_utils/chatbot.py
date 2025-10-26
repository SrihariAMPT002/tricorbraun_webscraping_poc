"""
Chatbot UI utilities.
This module contains all functions related to the AI chatbot interface.
"""

import streamlit as st
from typing import List, Dict
from .common import get_pinecone_vectorstore


def query_products(query_text: str, k: int = 5) -> List[Dict]:
    """
    Query the Pinecone vector store for similar products

    Args:
        query_text: The search query
        k: Number of results to return

    Returns:
        List of product dictionaries with metadata and content
    """
    try:
        docsearch = get_pinecone_vectorstore()
        results = docsearch.similarity_search(query_text, k=k)

        products = []
        for r in results:
            products.append(
                {
                    "name": r.metadata.get("name", "Unknown"),
                    "url": r.metadata.get("url", "#"),
                    "content": r.page_content[:500],  # Limit content to 500 chars
                    "metadata": r.metadata,
                }
            )

        return products
    except Exception as e:
        st.error(f"Error querying products: {str(e)}")
        return []


def show_chatbot():
    """Display chatbot interface with Pinecone search"""
    st.header("🤖 AI Assistant")

    st.info(
        "🔍 Ask questions about glass products and get instant results using semantic search powered by Google Gemini embeddings."
    )

    # Sample usage cards
    st.subheader("💡 Sample Usage Examples")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        <div class="company-card">
            <h4>🔍 Product Comparison</h4>
            <p><strong>Example:</strong> "Compare prices for 500ml jars"</p>
            <p><strong>Response:</strong> Would analyze pricing across all companies for 500ml capacity products</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="company-card">
            <h4>📊 Market Analysis</h4>
            <p><strong>Example:</strong> "Show SKUs under Pharma segment"</p>
            <p><strong>Response:</strong> Would filter and display all pharmaceutical products</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
        <div class="company-card">
            <h4>💰 Pricing Insights</h4>
            <p><strong>Example:</strong> "What's the average price for amber bottles?"</p>
            <p><strong>Response:</strong> Would calculate and display pricing statistics for amber glass products</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="company-card">
            <h4>📈 Trend Analysis</h4>
            <p><strong>Example:</strong> "Which company has the most diverse assortment?"</p>
            <p><strong>Response:</strong> Would analyze and compare assortment diversity metrics</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Chat interface
    st.subheader("💬 Chat Interface")

    # Chat input
    user_input = st.text_input(
        "Ask me anything about the glass product data:",
        placeholder="e.g., show me 10oz beer bottles",
    )

    if st.button("Send"):
        if user_input:
            with st.spinner("Searching products..."):
                # Query the Pinecone vector store
                results = query_products(user_input, k=5)

                if results:
                    st.success(f"🤖 **Found {len(results)} matching products:**")

                    # Display results
                    for i, product in enumerate(results, 1):
                        with st.expander(f"🧴 {i}. {product['name']}", expanded=False):
                            st.markdown(
                                f"**Product:** [{product['name']}]({product['url']})"
                            )
                            st.markdown(f"**URL:** {product['url']}")
                            st.divider()
                            st.markdown("**Details:**")
                            st.text(product["content"])

                            # Show additional metadata if available
                            if "company" in product["metadata"]:
                                st.markdown(
                                    f"**Company:** {product['metadata']['company']}"
                                )
                            if "price" in product["metadata"]:
                                st.markdown(
                                    f"**Price:** ${product['metadata']['price']}"
                                )
                else:
                    st.warning(
                        "No products found matching your query. Try rephrasing your search."
                    )
        else:
            st.warning("Please enter a question first.")
