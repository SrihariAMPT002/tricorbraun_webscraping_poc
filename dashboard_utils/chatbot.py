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
        with st.container(border=True):
            st.subheader("AI-powered Querying")
            st.write(
                '**Example:** "What product in the dataset has the highest capacity in milliliters?"'
            )
            st.write(
                "**Response:** 6.5 Gallon Clear Italian Glass Carboy 53 mm Cork Neck Finish with 24,605.18 ml"
            )

        with st.container(border=True):
            st.subheader("Market Analysis")
            st.write('**Example:** "How many products does Cary Company offer?"')
            st.write("**Response:**  398 products")

    with col2:
        with st.container(border=True):
            st.subheader("Pricing Insights")
            st.write(
                '**Example:** "Which shape appears most frequently in the dataset?"'
            )
            st.write("**Response:** Round (452 occurrences)")

        with st.container(border=True):
            st.subheader("Trend Analysis")
            st.write(
                '**Example:** "What is the minimum average price per unit (excluding zero) among TricorBraun products?"'
            )
            st.write("**Response:** $0.08")

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

    if st.button("Send"):
        if user_input.strip():
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.hybrid_chat.query(user_input)
                    st.session_state.hybrid_chat.export_logs("rag/Logs/query_logs.json")

                    # Remove asterisks from the response text for display
                    clean_response = response.replace("*", "")

                    # Display the response using proper markdown
                    with st.container(border=True):
                        st.markdown(f"**Chatbot Response:**\n\n{clean_response}")

                except Exception as e:
                    st.error(f"⚠️ Error: {str(e)}")
        else:
            st.warning("Please enter a question first.")
