
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
INDEX_NAME = "processed_products-index"
PRODUCTS_JSON_PATH = "tricorbraun_all_data_normalized.json"
BATCH_SIZE = 100

def create_embedding_text(product):
    """Generate optimized text for semantic search - FIXED VERSION"""
    parts = []
    
    # Core searchable content
    parts.append(f"Product: {product.get('product_name', '')}")
    
    if product.get('product_description'):
        parts.append(product['product_description'])
    
    # Key specs (filtered, no None values)
    specs = product.get('product_specs', {})
    important_specs = ['Capacity', 'Material', 'Color', 'Shape', 'Style', 
                       'Neck Finish', 'Substyle']
    spec_values = [f"{k}: {specs[k]}" for k in important_specs 
                   if k in specs and specs[k] and str(specs[k]) != 'None']
    if spec_values:
        parts.append("Specifications: " + ", ".join(spec_values))
    
    # FIXED: Pricing with proper None handling
    selluom = product.get('product_selluom', [])
    if selluom:
        try:
            valid_prices = []
            for tier in selluom:
                # Try price_per_unit first
                price = tier.get('price_per_unit')
                
                # Fallback to 'price' field if price_per_unit is None
                if not price:
                    price = tier.get('price')
                
                # Validate and clean the price
                if price and isinstance(price, str):
                    clean_price = price.replace('$', '').replace(',', '').strip()
                    if clean_price:
                        try:
                            valid_prices.append(float(clean_price))
                        except ValueError:
                            continue  # Skip invalid price formats
            
            if valid_prices:
                min_price = min(valid_prices)
                parts.append(f"Starting at ${min_price:.2f} per unit")
            else:
                parts.append("Request quote for pricing")
        except Exception as e:
            # Fallback for any unexpected errors
            parts.append("Request quote for pricing")
    else:
        parts.append("Request quote for pricing")
    
    # Availability context
    availability = product.get('product_availability', {}).get('in_stock', '')
    if availability and availability != 'N/A':
        parts.append(f"Availability: {availability}")
    
    # Include accessories for better recommendations
    if isinstance(product.get('product_accessories'), list):
        acc_names = [acc.get('name', '') for acc in product['product_accessories'][:3] 
                     if acc.get('name')]
        if acc_names:
            parts.append(f"Compatible accessories: {', '.join(acc_names)}")
    
    return "\n".join(parts)

def create_metadata(product):
    """Create comprehensive metadata without text duplication"""
    specs = product.get('product_specs', {})
    
    metadata = {
        # Identifiers
        'product_id': product.get('product_id'),
        'url': product.get('product_url'),
        
        # Basic info
        'name': product.get('product_name'),
        'description': product.get('product_description', '')[:500],  # Truncated
        
        # Specifications (key fields only)
        'capacity': specs.get('Capacity', ''),
        'material': specs.get('Material', ''),
        'color': specs.get('Color', ''),
        'shape': specs.get('Shape', ''),
        'style': specs.get('Style', ''),
        'neck_finish': specs.get('Neck Finish', ''),
        
        # Normalized data for filtering
        'normalized_capacity_ml': product.get('product_normalised_data', {}).get('normalized_capacity_value', 0),
        'capacity_uom': product.get('product_normalised_data', {}).get('product_capacity_uom', ''),
        
        # Availability
        'availability': product.get('product_availability', {}).get('in_stock', 'N/A'),
        'in_stock': product.get('product_availability', {}).get('in_stock', '').lower() in ['in stock', 'yes'],
        
        # Pricing (structured as JSON string)
        'pricing_data': json.dumps(product.get('product_selluom', [])),
        'has_pricing': len(product.get('product_selluom', [])) > 0,
        
        # Images
        'image_url': product.get('product_images', [{}])[0].get('image_url', ''),
        
        # Accessories (JSON string for complex data)
        # 'accessories': json.dumps(product.get('product_accessories', [])[:5]),  # Limit to 5
        
        # Additional specs as JSON for chatbot to parse
        'all_specs': json.dumps({k: v for k, v in specs.items() 
                                if v and v != 'None' and v is not None})
    }
    
    return metadata


def main():
    # Load products
    with open(PRODUCTS_JSON_PATH, "r") as f:
        products = json.load(f)
    
    # Initialize Pinecone
    pc = PineconeClient(api_key=os.environ["PINECONE_API_KEY"])
    
    if INDEX_NAME not in [idx["name"] for idx in pc.list_indexes()]:
        pc.create_index(
            name=INDEX_NAME,
            dimension=3072,  # Update if using different model
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"✅ Created Pinecone index: {INDEX_NAME}")
    
    index = pc.Index(INDEX_NAME)
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    
    # Process in batches
    for i in tqdm(range(0, len(products), BATCH_SIZE), desc="Uploading batches"):
        batch = products[i:i + BATCH_SIZE]
        
        vectors_to_upsert = []
        for product in batch:
            # Generate embedding text
            text = create_embedding_text(product)
            
            # Get embedding vector
            embedding = embeddings_model.embed_query(text)
            
            # Create metadata
            metadata = create_metadata(product)
            
            # Prepare vector for upsert
            vector_id = product.get('product_id', f"product_{i}")
            vectors_to_upsert.append({
                'id': vector_id,
                'values': embedding,
                'metadata': metadata
            })
        
        # Upsert batch directly to Pinecone (NO LangChain from_texts)
        index.upsert(vectors=vectors_to_upsert)
    
    print(f"✅ Successfully uploaded {len(products)} products to Pinecone!")
    print(f"📊 Metadata contains NO duplicate text, only structured data")

if __name__ == "__main__":
    main()