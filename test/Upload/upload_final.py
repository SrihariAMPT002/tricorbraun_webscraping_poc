import os
import json
from tqdm import tqdm
import time
# ==== Imports for embeddings + vector store ====
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone as PineconeClient, ServerlessSpec
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==== CONFIG =====
INDEX_NAME = "processed-products-index"
PRODUCTS_JSON_PATH = "processed_data.json"  # CORRECTED: Using processed_data.json
BATCH_SIZE = 25

EMBEDDING_BATCH_SIZE = 100  # Process 100 embeddings per API call
PINECONE_BATCH_SIZE = 100   # Upsert 100 vectors at a time
REQUEST_DELAY = 0.65 

def create_embedding_text(product):
    """Generate optimized text for semantic search based on processed_data.json structure"""
    parts = []

    # Product name
    if product.get('name'):
        parts.append(f"Product: {product['name']}")

    # Capacity with unit
    if product.get('original_capacity') and product.get('original_uom'):
        parts.append(f"{product['original_capacity']} {product['original_uom']} capacity")

    # Color and material
    if product.get('color'):
        parts.append(f"{product['color']} color")
    if product.get('material'):
        parts.append(f"{product['material']} material")

    # Shape - important for product type
    if product.get('shape'):
        parts.append(f"{product['shape']} shape")

    # Category
    if product.get('category'):
        parts.append(f"{product['category']} category")

    # Market segment
    if product.get('market_segment'):
        parts.append(f"for {product['market_segment']} use")

    # Company
    if product.get('company'):
        parts.append(f"from {product['company']}")

    # Stock status
    if product.get('stock'):
        parts.append(f"Stock: {product['stock']}")

    return " | ".join(parts)

def extract_min_max_price(product):
    """Extract min and max price from quantity_breaks for filtering"""
    quantity_breaks = product.get('quantity_breaks', [])

    if not quantity_breaks:
        return None, None

    valid_prices = []
    for tier in quantity_breaks:
        price = tier.get('price_per_item')
        if price is not None:
            try:
                valid_prices.append(float(price))
            except (ValueError, TypeError):
                continue

    if valid_prices:
        return min(valid_prices), max(valid_prices)

    # Fallback to avg_price_per_unit
    avg_price = product.get('avg_price_per_unit')
    if avg_price is not None:
        try:
            price_float = float(avg_price)
            return price_float, price_float
        except (ValueError, TypeError):
            pass

    return None, None

def convert_capacity_to_oz(product):
    """Convert capacity to oz for consistent filtering"""
    original_uom = product.get('original_uom', '')
    original_capacity = product.get('original_capacity')

    if not original_capacity:
        return None

    try:
        capacity_val = float(original_capacity)
    except (ValueError, TypeError):
        return None

    # Convert to oz based on unit
    if original_uom == 'oz':
        return capacity_val
    elif original_uom == 'ml':
        return capacity_val / 29.5735  # ml to oz
    elif original_uom == 'gallon':
        return capacity_val * 128  # gallon to oz
    elif original_uom == 'dram':
        return capacity_val * 0.125  # dram to oz
    else:
        return None

def create_metadata(product):
    """
    Create comprehensive metadata without null values (Pinecone requirement).
    Only includes fields that are not None/empty.
    """
    # Extract price range
    min_price, max_price = extract_min_max_price(product)
    capacity_oz = convert_capacity_to_oz(product)

    metadata = {}

    # Add fields only if they exist and are not None/empty
    if product.get('company'):
        metadata['company'] = str(product['company'])

    if product.get('url'):
        metadata['url'] = str(product['url'])

    if product.get('sku'):
        metadata['sku'] = str(product['sku'])

    if product.get('name'):
        metadata['name'] = str(product['name'])

    # Specifications
    if product.get('color'):
        metadata['color'] = str(product['color'])

    if product.get('material'):
        metadata['material'] = str(product['material'])

    if product.get('shape'):
        metadata['shape'] = str(product['shape'])

    if product.get('category'):
        metadata['category'] = str(product['category'])

    if product.get('market_segment'):
        metadata['market_segment'] = str(product['market_segment'])

    if product.get('closure_type'):
        # Trim the long description after "?"
        closure = product['closure_type'].split('?')[0]
        metadata['closure_type'] = str(closure)

    # Capacity fields
    if product.get('normalised_capacity') is not None:
        metadata['normalised_capacity_ml'] = float(product['normalised_capacity'])

    if product.get('original_capacity'):
        metadata['original_capacity'] = str(product['original_capacity'])

    if product.get('original_uom'):
        metadata['capacity_uom'] = str(product['original_uom'])

    if capacity_oz is not None:
        metadata['capacity_oz'] = float(capacity_oz)

    # Stock status
    if product.get('stock'):
        metadata['stock_status'] = str(product['stock'])
        # Boolean for easy filtering
        metadata['in_stock'] = 'In Stock' in product.get('stock', '')

    # Pricing
    if min_price is not None:
        metadata['min_price'] = float(min_price)
        metadata['has_pricing'] = True
    else:
        metadata['has_pricing'] = False

    if max_price is not None:
        metadata['max_price'] = float(max_price)

    if product.get('avg_price_per_unit') is not None:
        try:
            metadata['avg_price'] = float(product['avg_price_per_unit'])
        except (ValueError, TypeError):
            pass

    # Items per unit
    if product.get('items_per_unit'):
        metadata['items_per_unit'] = str(product['items_per_unit'])

    # Store pricing data as JSON string (for chatbot to parse)
    if product.get('quantity_breaks'):
        metadata['pricing_tiers'] = json.dumps(product['quantity_breaks'])

    return metadata

def main():
    # Load products from processed_data.json
    print(f"📂 Loading products from {PRODUCTS_JSON_PATH}...")
    with open(PRODUCTS_JSON_PATH, "r") as f:
        products = json.load(f)

    print(f"✅ Loaded {len(products)} products")

    # Initialize Pinecone
    pc = PineconeClient(api_key=os.environ["PINECONE_API_KEY"])

    # Check if index exists, create if not
    existing_indexes = [idx["name"] for idx in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"🔨 Creating Pinecone index: {INDEX_NAME}")
        pc.create_index(
            name=INDEX_NAME,
            dimension=3072,  # gemini-embedding-001 dimension
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"✅ Created index: {INDEX_NAME}")
    else:
        print(f"✅ Index {INDEX_NAME} already exists")

    index = pc.Index(INDEX_NAME)
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    # Process in batches
    print(f"\n🚀 Starting upload in batches of {BATCH_SIZE}...")
    print(f"📊 Total products: {len(products)}")
    print(f"📦 Embedding batch size: {EMBEDDING_BATCH_SIZE} texts per API call")
    print(f"⏱️ Estimated time: ~{(len(products) / EMBEDDING_BATCH_SIZE) * REQUEST_DELAY / 60:.1f} minutes\n")
    
    # for i in tqdm(range(0, len(products), BATCH_SIZE), desc="Uploading batches"):
    #     batch = products[i:i + BATCH_SIZE]
    #     vectors_to_upsert = []

    #     for idx, product in enumerate(batch):
    #         try:
    #             # Generate embedding text
    #             text = create_embedding_text(product)

    #             # Get embedding vector
    #             embedding = embeddings_model.embed_query(text)

    #             # Create metadata (no null values!)
    #             metadata = create_metadata(product)

    #             # Prepare vector for upsert with unique ID
    #             vector_id = f"{product.get('sku', f'product_{i+idx}')}"
    #             vectors_to_upsert.append({
    #                 'id': vector_id,
    #                 'values': embedding,
    #                 'metadata': metadata
    #             })
    #         except Exception as e:
    #             print(f"\n⚠️ Error processing product {i+idx}: {str(e)}")
    #             continue

    #     # Upsert batch to Pinecone
    #     if vectors_to_upsert:
    #         index.upsert(vectors=vectors_to_upsert)

    #new one
    all_vectors = []
    
    for i in tqdm(range(0, len(products), EMBEDDING_BATCH_SIZE), desc="Generating embeddings"):
        batch = products[i:i + EMBEDDING_BATCH_SIZE]
        
        try:
            # Create texts for batch
            texts = [create_embedding_text(product) for product in batch]
            
            # BATCH EMBEDDING: Process multiple texts in one API call
            embeddings = embeddings_model.embed_documents(texts)
            
            # Create vectors with metadata
            for idx, (product, embedding) in enumerate(zip(batch, embeddings)):
                metadata = create_metadata(product)
                vector_id = f"{product.get('sku', f'product_{i+idx}')}"
                
                all_vectors.append({
                    'id': vector_id,
                    'values': embedding,
                    'metadata': metadata
                })
            
            # Rate limiting: respect 100 RPM
            time.sleep(REQUEST_DELAY)
            
        except Exception as e:
            print(f"\n⚠️ Error processing batch at index {i}: {str(e)}")
            if "429" in str(e):
                print("⏸️ Rate limit hit, waiting 60 seconds...")
                time.sleep(60)
                # Retry the batch
                try:
                    texts = [create_embedding_text(product) for product in batch]
                    embeddings = embeddings_model.embed_documents(texts)
                    
                    for idx, (product, embedding) in enumerate(zip(batch, embeddings)):
                        metadata = create_metadata(product)
                        vector_id = f"{product.get('sku', f'product_{i+idx}')}"
                        
                        all_vectors.append({
                            'id': vector_id,
                            'values': embedding,
                            'metadata': metadata
                        })
                except Exception as retry_error:
                    print(f"❌ Retry failed: {str(retry_error)}")
                    continue
    
    # Upsert to Pinecone in batches
    print(f"\n📤 Uploading {len(all_vectors)} vectors to Pinecone...")
    for i in tqdm(range(0, len(all_vectors), PINECONE_BATCH_SIZE), desc="Upserting to Pinecone"):
        batch = all_vectors[i:i + PINECONE_BATCH_SIZE]
        index.upsert(vectors=batch)
        time.sleep(0.1)  # Small delay between upserts
    
    print(f"\n✅ Successfully uploaded all {len(all_vectors)} products to Pinecone!")
    print(f"📊 Index stats: {index.describe_index_stats()}")

if __name__ == "__main__":
    main()
