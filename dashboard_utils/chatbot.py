"""
Chatbot UI utilities.
This module contains all functions related to the AI chatbot interface.
"""

import streamlit as st
from dotenv import load_dotenv
from rag.chatbot_production import HybridRAGChatbot
import os

# --- Load environment variables ---
load_dotenv()


def show_chatbot():
    """Display chatbot interface using the integrated HybridRAGChatbot"""
    st.header("AI Assistant")

    st.info(
        "Ask questions about glass products and get instant results using the TricorBraun Hybrid AI Chatbot "
        "powered by Google Gemini, MongoDB, and Pinecone."
    )

    # Sample usage cards
    st.subheader("Sample Usage Examples")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        <div class="company-card">
            <h4> Product Comparison</h4>
            <p><strong>Example:</strong> "What product in the dataset has the highest capacity in milliliters?"</p>
            <p><strong>Response:</strong> 6.5 Gallon Clear Italian Glass Carboy 53 mm Cork Neck Finish with 24,605.18 ml</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="company-card">
            <h4>Market Analysis</h4>
            <p><strong>Example:</strong> "How many products does Cary Company offer?"</p>
            <p><strong>Response:</strong>  398 products</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
        <div class="company-card">
            <h4>Pricing Insights</h4>
            <p><strong>Example:</strong> "Which shape appears most frequently in the dataset?"</p>
            <p><strong>Response:</strong> Round (452 occurrences)</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="company-card">
            <h4>Trend Analysis</h4>
            <p><strong>Example:</strong> "What is the minimum average price per unit (excluding zero) among TricorBraun products?"</p>
            <p><strong>Response:</strong> $0.08</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Chat interface
    st.subheader("Chat Interface")

    # Initialize the Hybrid RAG chatbot (once per Streamlit session)
    if "hybrid_chat" not in st.session_state:
        st.session_state.hybrid_chat = HybridRAGChatbot(
            verbose=False,
            log_file="rag/Logs/chatbot_activity.log",
        )

    # Chat input
    user_input = st.text_input(
        "Ask me anything about the glass product data:",
        placeholder="e.g., show me 10oz beer bottles",
        key="hybrid_query",
    )

    # Response placeholder for dynamic updates
    response_container = st.container()

    if st.button("Send"):
        if user_input.strip():
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.hybrid_chat.query(user_input)
                    st.session_state.hybrid_chat.export_logs("rag/Logs/query_logs.json")

                    # Display the response in a clean, styled chat card
                    with response_container:
                        st.markdown(
                            f"""
                            <div style="
                                background-color: #f9f9fb;
                                border: 1px solid #dcdcdc;
                                border-radius: 10px;
                                padding: 1rem;
                                margin-top: 1rem;
                                box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.05);
                                ">
                                <h4 style="color:#1c2e5c;">🤖 Chatbot Response</h4>
                                <p style="font-size:16px; color:#222;">{response}</p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                except Exception as e:
                    st.error(f"⚠️ Error: {str(e)}")
        else:
            st.warning("Please enter a question first.")
