#!/usr/bin/env python3
"""
Vector embed the first 50 product JSON objects and upload to Pinecone
using Gemini Embedding model via LangChain + Google‐GenAI integration.
"""

import os
import json
from tqdm import tqdm
from dotenv import load_dotenv

# ==== Imports for embeddings + vector store ====
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

# ==== CONFIG =====
INDEX_NAME = "products-index"
PRODUCTS_JSON_PATH = "demo_batch_data/berlin_packing_all_data_normalized.json"
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
    load_dotenv()

    # Load products
    with open(PRODUCTS_JSON_PATH, "r") as f:
        data = json.load(f)
    products = data[:BATCH_SIZE]

    # Initialize Pinecone client
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

    # Create index if it doesn't exist
    if INDEX_NAME not in [idx["name"] for idx in pc.list_indexes()]:
        pc.create_index(
            name=INDEX_NAME,
            dimension=3072,  # gemini-embedding-001 vector size
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"✅ Created Pinecone index: {INDEX_NAME}")

    # Initialize Gemini embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    # Prepare documents
    texts, metadatas = [], []
    for product in tqdm(products, desc="Preparing embeddings"):
        text = json_to_text(product)
        metadata = {
            "url": product.get("product_url"),
            "product_id": product.get("product_id"),
            "name": product.get("product_name"),
            "capacity": product.get("product_specs", {}).get("Capacity "),
        }
        texts.append(text)
        metadatas.append(metadata)

    # Upload embeddings to Pinecone
    print("🚀 Uploading to Pinecone…")
    vectorstore = PineconeVectorStore.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        index_name=INDEX_NAME,
        pinecone_api_key=os.environ["PINECONE_API_KEY"],
    )

    print(f"✅ Successfully uploaded {len(texts)} product embeddings to Pinecone!")


if __name__ == "__main__":
    main()
