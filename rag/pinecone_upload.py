#!/usr/bin/env python3
"""
Vector embed the first 50 product JSON objects and upload to Pinecone
using Gemini Embedding model via LangChain + Google‐GenAI integration.
"""

import os
import json
from tqdm import tqdm

# ==== Imports for embeddings + vector store ====
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeStore
from pinecone import Pinecone as PineconeClient, ServerlessSpec

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ==== CONFIG =====
INDEX_NAME = "products-index"
PRODUCTS_JSON_PATH = "demo_batch_data/cary_all_data_normalized.json"
BATCH_SIZE = 50


# ==== Helper: Convert JSON → text =====
def json_to_text(product):
    specs = product.get("product_specs", {})
    selluom = product.get("product_selluom", [])
    desc = product.get("product_description", "")
    name = product.get("product_name", "")
    notes = " ".join(product.get("product_notes", []))

    specs_text = ", ".join([f"{k}: {v}" for k, v in specs.items()])
    pricing_text = ", ".join(
        [f"{tier['qty_range']} – {tier['price_per_unit']}" for tier in selluom]
    )

    text = f"""Product Name: {name}
    Description: {desc}
    Notes: {notes}
    Specs: {specs_text}
    Pricing: {pricing_text}
    Availability: {product.get('product_availability', {}).get('in_stock', '')}
    """
    return text.strip()


# ==== Main script ====
def main():
    # Load products
    with open(PRODUCTS_JSON_PATH, "r") as f:
        data = json.load(f)
    products = data[:BATCH_SIZE]

    # Initialize Pinecone
    pc = PineconeClient(api_key=os.environ["PINECONE_API_KEY"])
    if INDEX_NAME not in [idx["name"] for idx in pc.list_indexes()]:
        pc.create_index(
            name=INDEX_NAME,
            dimension=3072,  # For gemini-embedding-001
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"✅ Created Pinecone index: {INDEX_NAME}")
    index = pc.Index(INDEX_NAME)

    # Initialize Gemini embeddings wrapper
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    # Prepare documents
    texts = []
    metadatas = []
    for product in tqdm(products, desc="Preparing embeddings"):
        text = json_to_text(product)
        metadata = {
            "url": product.get("product_url"),
            "product_id": product.get("product_id"),
            "name": product.get("product_name"),
            "capacity": product.get("product_specs", {}).get("Capacity"),
        }
        texts.append(text)
        metadatas.append(metadata)

    # Upload to Pinecone
    print("🚀 Uploading to Pinecone…")
    PineconeStore.from_texts(
        texts=texts,
        embedding=embeddings,
        index_name=INDEX_NAME,
        metadatas=metadatas,
    )
    print(f"✅ Successfully uploaded {len(texts)} product embeddings to Pinecone!")


if __name__ == "__main__":
    main()
