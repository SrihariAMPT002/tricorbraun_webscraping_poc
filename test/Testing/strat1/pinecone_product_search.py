# ========================================
# PINECONE VECTOR DATABASE - PRODUCT CATALOG
# Upload and Query Implementation
# ========================================

import json
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
import re
from typing import List, Dict, Any

# Initialize clients
pc = Pinecone(api_key="your-pinecone-api-key")
openai_client = OpenAI(api_key="your-openai-api-key")

# Create or connect to index
INDEX_NAME = "product-catalog"
EMBEDDING_DIMENSION = 1536  # OpenAI text-embedding-3-small dimension

# Create index if it doesn't exist
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBEDDING_DIMENSION,
        metric='cosine',
        spec=ServerlessSpec(
            cloud='aws',
            region='us-east-1'
        )
    )

index = pc.Index(INDEX_NAME)

def create_searchable_text(product: Dict[str, Any]) -> str:
    """
    Create a rich text representation for embedding.
    Combines product name, description, and key attributes.
    """
    parts = []

    # Product name and SKU
    if product.get('name'):
        parts.append(product['name'])
    if product.get('sku'):
        parts.append(f"SKU: {product['sku']}")

    # Capacity information
    if product.get('original_capacity') and product.get('original_uom'):
        parts.append(f"{product['original_capacity']} {product['original_uom']} capacity")

    # Material and color
    if product.get('color'):
        parts.append(f"{product['color']} color")
    if product.get('material'):
        parts.append(f"{product['material']} material")

    # Shape - important for product type identification
    if product.get('shape'):
        parts.append(f"{product['shape']} shape bottle")

    # Closure type
    if product.get('closure_type'):
        closure = product['closure_type'].split('?')[0]  # Remove description
        parts.append(f"{closure} closure")

    # Market segment
    if product.get('market_segment'):
        parts.append(f"for {product['market_segment']} use")

    # Company
    if product.get('company'):
        parts.append(f"from {product['company']}")

    return " | ".join(parts)

def extract_capacity_oz(product: Dict[str, Any]) -> float:
    """
    Extract capacity in oz for metadata filtering.
    """
    if product.get('original_uom') == 'oz':
        try:
            return float(product.get('original_capacity', 0))
        except (ValueError, TypeError):
            return 0.0
    elif product.get('normalised_capacity'):
        # Convert ml to oz (1 oz = 29.5735 ml)
        try:
            return float(product['normalised_capacity']) / 29.5735
        except (ValueError, TypeError):
            return 0.0
    return 0.0

def prepare_metadata(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare metadata for Pinecone. 
    Only includes filterable fields with proper types.
    """
    metadata = {
        # Text fields
        'company': product.get('company', '').strip(),
        'sku': product.get('sku', '').strip(),
        'name': product.get('name', '').strip(),
        'color': product.get('color', '').strip(),
        'material': product.get('material', '').strip(),
        'shape': product.get('shape', '').strip(),
        'category': product.get('category', '').strip(),
        'market_segment': product.get('market_segment', '').strip(),
        'stock': product.get('stock', '').strip(),
        'url': product.get('url', '').strip(),

        # Numerical fields - critical for filtering
        'price': float(product.get('price', 0) or 0),
        'avg_price_per_unit': float(product.get('avg_price_per_unit', 0) or 0),
        'normalised_capacity': float(product.get('normalised_capacity', 0) or 0),
        'capacity_oz': extract_capacity_oz(product),

        # Additional useful numerical fields
        'items_per_unit': product.get('items_per_unit', ''),
    }

    # Remove empty strings and None values
    metadata = {k: v for k, v in metadata.items() if v not in ['', None]}

    return metadata

def get_embedding(text: str) -> List[float]:
    """
    Generate embedding using OpenAI.
    """
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def upload_products_to_pinecone(json_file_path: str, batch_size: int = 100):
    """
    Upload products from JSON file to Pinecone with embeddings.
    """
    with open(json_file_path, 'r') as f:
        products = json.load(f)

    vectors_to_upsert = []

    for idx, product in enumerate(products):
        try:
            # Create searchable text
            searchable_text = create_searchable_text(product)

            # Generate embedding
            embedding = get_embedding(searchable_text)

            # Prepare metadata
            metadata = prepare_metadata(product)

            # Create vector tuple
            vector_id = f"product_{idx}_{product.get('sku', idx)}"
            vectors_to_upsert.append((vector_id, embedding, metadata))

            # Batch upsert
            if len(vectors_to_upsert) >= batch_size:
                index.upsert(vectors=vectors_to_upsert)
                print(f"Uploaded {len(vectors_to_upsert)} vectors (progress: {idx+1}/{len(products)})")
                vectors_to_upsert = []

        except Exception as e:
            print(f"Error processing product {idx}: {str(e)}")
            continue

    # Upload remaining vectors
    if vectors_to_upsert:
        index.upsert(vectors=vectors_to_upsert)
        print(f"Uploaded final {len(vectors_to_upsert)} vectors")

    print(f"\nTotal vectors in index: {index.describe_index_stats()}")

# ========================================
# PART 2: QUERY PROCESSING
# ========================================

def parse_query(query_text: str) -> Dict[str, Any]:
    """
    Parse natural language query to extract filters and search terms.
    """
    query_lower = query_text.lower()

    filters = {}
    search_terms = []

    # Extract company name
    company_patterns = [
        r"(cary(?:'s|s)?)",
        r"(berlin packaging)",
        r"(tricorbraun)",
    ]
    for pattern in company_patterns:
        match = re.search(pattern, query_lower)
        if match:
            company_name = match.group(1)
            if 'cary' in company_name:
                filters['company'] = 'Cary Company'
            elif 'berlin' in company_name:
                filters['company'] = 'Berlin Packaging'
            elif 'tricor' in company_name:
                filters['company'] = 'TricorBraun'
            break

    # Extract capacity (oz or ml)
    capacity_match = re.search(r'(\d+(?:\.\d+)?)\s*(oz|ml|ounce|gallon|liter)', query_lower)
    if capacity_match:
        capacity_value = float(capacity_match.group(1))
        capacity_unit = capacity_match.group(2)

        if 'oz' in capacity_unit or 'ounce' in capacity_unit:
            filters['capacity_oz'] = capacity_value
        elif 'ml' in capacity_unit:
            filters['normalised_capacity'] = capacity_value
        elif 'gallon' in capacity_unit:
            filters['capacity_oz'] = capacity_value * 128  # 1 gallon = 128 oz

    # Extract price constraints
    price_match = re.search(r'(?:under|below|less than|<)\s*\$?(\d+(?:\.\d+)?)', query_lower)
    if price_match:
        filters['max_price'] = float(price_match.group(1))

    price_range_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*(?:to|-)\s*\$?(\d+(?:\.\d+)?)', query_lower)
    if price_range_match:
        filters['min_price'] = float(price_range_match.group(1))
        filters['max_price'] = float(price_range_match.group(2))

    # Extract product type / shape keywords
    product_types = ['packer', 'boston round', 'bottle', 'jar', 'vial', 'jug', 'growler', 'wine bottle']
    for ptype in product_types:
        if ptype in query_lower:
            search_terms.append(ptype)

    # Extract color/material descriptors
    descriptors = ['natural', 'amber', 'clear', 'blue', 'green', 'frosted', 'glass', 'plastic']
    for desc in descriptors:
        if desc in query_lower:
            search_terms.append(desc)

    # If no search terms identified, use the whole query
    if not search_terms:
        search_terms = [query_text]

    return {
        'filters': filters,
        'search_terms': ' '.join(search_terms),
        'original_query': query_text
    }

def build_pinecone_filter(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build Pinecone metadata filter from parsed filters.
    """
    filter_conditions = []

    # Company filter
    if 'company' in filters:
        filter_conditions.append({'company': {'$eq': filters['company']}})

    # Capacity filter (exact match for oz)
    if 'capacity_oz' in filters:
        # Allow small tolerance for floating point comparison
        target_oz = filters['capacity_oz']
        filter_conditions.append({
            'capacity_oz': {
                '$gte': target_oz - 0.5,
                '$lte': target_oz + 0.5
            }
        })

    if 'normalised_capacity' in filters:
        target_ml = filters['normalised_capacity']
        filter_conditions.append({
            'normalised_capacity': {
                '$gte': target_ml - 10,
                '$lte': target_ml + 10
            }
        })

    # Price filters
    if 'max_price' in filters:
        filter_conditions.append({'avg_price_per_unit': {'$lt': filters['max_price']}})

    if 'min_price' in filters:
        filter_conditions.append({'avg_price_per_unit': {'$gte': filters['min_price']}})

    # Combine all conditions with AND
    if len(filter_conditions) == 0:
        return {}
    elif len(filter_conditions) == 1:
        return filter_conditions[0]
    else:
        return {'$and': filter_conditions}

def query_products(query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Query Pinecone with hybrid approach: semantic search + metadata filtering.
    """
    # Parse the query
    parsed = parse_query(query_text)
    print(f"\nParsed Query:")
    print(f"  Filters: {parsed['filters']}")
    print(f"  Search Terms: {parsed['search_terms']}")

    # Generate embedding for semantic search
    query_embedding = get_embedding(parsed['search_terms'])

    # Build Pinecone filter
    pinecone_filter = build_pinecone_filter(parsed['filters'])
    print(f"  Pinecone Filter: {pinecone_filter}")

    # Query Pinecone
    results = index.query(
        vector=query_embedding,
        filter=pinecone_filter if pinecone_filter else None,
        top_k=top_k,
        include_metadata=True
    )

    # Format results
    products = []
    for match in results.matches:
        product_info = {
            'score': match.score,
            'name': match.metadata.get('name'),
            'sku': match.metadata.get('sku'),
            'company': match.metadata.get('company'),
            'price': match.metadata.get('avg_price_per_unit'),
            'capacity': f"{match.metadata.get('capacity_oz', 0):.1f} oz",
            'color': match.metadata.get('color'),
            'shape': match.metadata.get('shape'),
            'stock': match.metadata.get('stock'),
            'url': match.metadata.get('url'),
        }
        products.append(product_info)

    return products

# ========================================
# PART 3: EXAMPLE USAGE
# ========================================

if __name__ == "__main__":
    # UPLOAD DATA (run once)
    print("=== UPLOADING DATA ===")
    upload_products_to_pinecone('processed_data.json')

    # QUERY EXAMPLES
    print("\n=== QUERYING DATA ===")

    # Example 1: Your original query
    query1 = "Show me Cary's 32 oz natural packers under $1"
    print(f"\nQuery: {query1}")
    results1 = query_products(query1, top_k=5)

    print(f"\nFound {len(results1)} results:")
    for i, product in enumerate(results1, 1):
        print(f"\n{i}. {product['name']}")
        print(f"   Company: {product['company']}")
        print(f"   SKU: {product['sku']}")
        print(f"   Price: ${product['price']:.2f}")
        print(f"   Capacity: {product['capacity']}")
        print(f"   Color: {product['color']}")
        print(f"   Similarity Score: {product['score']:.3f}")

    # Example 2: Different query
    query2 = "amber glass bottles 16 oz under $2"
    print(f"\n\nQuery: {query2}")
    results2 = query_products(query2, top_k=5)

    print(f"\nFound {len(results2)} results:")
    for i, product in enumerate(results2, 1):
        print(f"\n{i}. {product['name']}")
        print(f"   Price: ${product['price']:.2f}")
        print(f"   Stock: {product['stock']}")

    # Example 3: Just semantic search without strict filters
    query3 = "round boston bottles for beverages"
    print(f"\n\nQuery: {query3}")
    results3 = query_products(query3, top_k=5)

    print(f"\nFound {len(results3)} results:")
    for i, product in enumerate(results3, 1):
        print(f"\n{i}. {product['name']}")
        print(f"   Shape: {product['shape']}")
        print(f"   Capacity: {product['capacity']}")
        print(f"   Similarity Score: {product['score']:.3f}")
