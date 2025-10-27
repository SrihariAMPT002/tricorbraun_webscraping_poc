"""
Common UI utilities shared across all pages.
This module contains Pinecone setup, page configuration, styling, and navigation.
"""

import streamlit as st
from dotenv import load_dotenv
from langchain_community.vectorstores import Pinecone as LangPinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables
load_dotenv()


@st.cache_resource
def get_pinecone_vectorstore():
    """Initialize and cache the Pinecone vector store"""
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    docsearch = LangPinecone.from_existing_index("products-index", embeddings)
    return docsearch


def setup_page_config():
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title="Packing Competitor Analysis Dashboard",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def get_custom_css():
    """Return custom CSS for styling"""
    return """
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 2rem;
        }
        .metric-card {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
            border-left: 4px solid #1f77b4;
        }
        .company-card {
            background-color: #ffffff;
            padding: 1.5rem;
            border-radius: 0.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }
        .menu-bar {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .menu-item {
            display: inline-block;
            margin-right: 1rem;
            padding: 0.5rem 1rem;
            background-color: #ffffff;
            border-radius: 0.25rem;
            text-decoration: none;
            color: #1f77b4;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        .menu-item:hover {
            background-color: #1f77b4;
            color: #ffffff;
            transform: translateY(-2px);
        }
        .menu-item.active {
            background-color: #1f77b4;
            color: #ffffff;
        }
    </style>
    """


def apply_custom_styling():
    """Apply custom CSS styling to the dashboard"""
    st.markdown(get_custom_css(), unsafe_allow_html=True)


def create_header():
    """Create the main dashboard header"""
    st.markdown(
        '<h1 class="main-header">📦 Packing Competitor Analysis Dashboard</h1>',
        unsafe_allow_html=True,
    )


def create_navigation_menu():
    """Create the navigation menu in sidebar"""
    # Initialize session state for page
    if "page" not in st.session_state:
        st.session_state.page = "Homepage"

    # Create sidebar navigation
    with st.sidebar:
        st.markdown("##  Side Bar Navigation")
        st.markdown("---")

        if st.button("🏠 Homepage", key="homepage_btn", width="stretch"):
            st.session_state.page = "Homepage"
            st.rerun()

        if st.button("💰 Pricing Analysis", key="pricing_btn", width="stretch"):
            st.session_state.page = "Pricing Analysis"
            st.rerun()

        if st.button(
            "📦 Assortment Analysis",
            key="assortment_btn",
            width="stretch",
        ):
            st.session_state.page = "Assortment Analysis"
            st.rerun()

        if st.button("🤖 Chatbot", key="chatbot_btn", width="stretch"):
            st.session_state.page = "Chatbot"
            st.rerun()

    return st.session_state.page
