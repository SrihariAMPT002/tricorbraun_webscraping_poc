from pinecone import Pinecone as PineconeClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
import json
import re
import time
import os

load_dotenv()

# ==== CONFIG =====
INDEX_NAME = "processed-products-index"
REQUEST_DELAY = 0.65  # Stay under 100 RPM

def parse_query(query_text):
    """
    Parse natural language query to extract filters and search terms.
    Handles company names, capacities, prices, colors, materials, stock status.
    """
    query_lower = query_text.lower()
    filters = {}
    search_terms = []
    
    # Extract company name (Berlin Packaging, Cary Company, etc.)
    company_patterns = [
        (r"\b(cary(?:'s|s)?)\b", "Cary Company"),
        (r"\b(berlin packaging)\b", "Berlin Packaging"),
        (r"\b(tricorbraun)\b", "TricorBraun"),
    ]
    
    for pattern, company_name in company_patterns:
        if re.search(pattern, query_lower):
            filters['company'] = {'$eq': company_name}
            break
    
    # Extract capacity (oz, ml, gallons, liters)
    capacity_match = re.search(r'(\d+(?:\.\d+)?)\s*(oz|ml|ounce|gallon|liter|l\b)', query_lower)
    if capacity_match:
        capacity_value = float(capacity_match.group(1))
        capacity_unit = capacity_match.group(2)
        
        # Convert to oz for filtering (since we have capacity_oz field)
        if 'oz' in capacity_unit or 'ounce' in capacity_unit:
            target_oz = capacity_value
        elif 'ml' in capacity_unit:
            target_oz = capacity_value / 29.5735
        elif 'gallon' in capacity_unit:
            target_oz = capacity_value * 128
        elif 'liter' in capacity_unit or capacity_unit == 'l':
            target_oz = capacity_value * 33.814
        else:
            target_oz = capacity_value
        
        # Allow ±10% tolerance for capacity matching
        tolerance = target_oz * 0.1
        filters['capacity_oz'] = {
            '$gte': target_oz - tolerance,
            '$lte': target_oz + tolerance
        }
        
        # Add to search terms
        search_terms.append(f"{capacity_value} {capacity_unit}")
    
    # Extract price constraints
    price_match = re.search(r'(?:under|below|less than|<)\s*\$?(\d+(?:\.\d+)?)', query_lower)
    if price_match:
        max_price = float(price_match.group(1))
        filters['min_price'] = {'$lt': max_price}
    
    price_range_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*(?:to|-|and)\s*\$?(\d+(?:\.\d+)?)', query_lower)
    if price_range_match:
        min_price_val = float(price_range_match.group(1))
        max_price_val = float(price_range_match.group(2))
        filters['min_price'] = {'$gte': min_price_val}
        filters['max_price'] = {'$lte': max_price_val}
    
    # Extract material - use $eq instead of $regex
    materials = ['glass', 'plastic', 'pet', 'hdpe', 'ldpe', 'pp', 'pvc', 'metal', 'aluminum']
    for material in materials:
        if re.search(r'\b' + material + r'\b', query_lower):
            # Don't add as filter, rely on semantic search instead
            # Pinecone doesn't support regex or case-insensitive contains
            search_terms.append(material)
            break
    
    # Extract color - use semantic search instead of regex
    colors = ['clear', 'amber', 'blue', 'green', 'white', 'black', 'frosted', 'natural',
              'brown', 'flint', 'cobalt', 'antique']
    for color in colors:
        if re.search(r'\b' + color + r'\b', query_lower):
            # Add to search terms for semantic matching
            # For exact filtering, would need to match stored metadata exactly
            search_terms.append(color)
            
            # Only add filter if it's an exact match to common values
            # This will work for exact matches like "Clear", "Amber", etc.
            if color.lower() in ['clear', 'amber', 'blue', 'green', 'white', 'black', 'natural']:
                # Try exact match with capitalized version
                filters['color'] = {'$eq': color.capitalize()}
            break
    
    # Extract stock status
    if any(term in query_lower for term in ['in stock', 'available', 'stock']):
        filters['in_stock'] = {'$eq': True}
    
    # Extract product types/shapes for semantic search
    product_types = ['bottle', 'jar', 'jug', 'vial', 'container', 'packer', 'boston round',
                     'growler', 'wine bottle', 'beer bottle', 'beverage', 'pharmaceutical',
                     'round', 'square', 'oval', 'milk bottle', 'dropper']
    for ptype in product_types:
        if ptype in query_lower:
            search_terms.append(ptype)
    
    # If no specific search terms, use whole query
    if not search_terms:
        search_terms.append(query_text)
    
    return {
        'filters': filters,
        'search_text': ' '.join(search_terms),
        'original_query': query_text
    }

def build_pinecone_filter(filters):
    """
    Convert parsed filters into Pinecone filter format.
    Handles $and, $or, $eq, $gte, $lte, $lt operators.
    """
    if not filters:
        return None
    
    filter_conditions = []
    for key, value in filters.items():
        filter_conditions.append({key: value})
    
    if len(filter_conditions) == 0:
        return None
    elif len(filter_conditions) == 1:
        return filter_conditions[0]
    else:
        return {'$and': filter_conditions}

def search_products(query, k=10, filters=None, auto_parse=True):
    """
    Enhanced search with complete data retrieval and optional auto-parsing.
    
    Args:
        query: Search query (string)
        k: Number of results
        filters: Optional dict for manual filtering
        auto_parse: If True, automatically parse query for filters
    """
    # Initialize
    pc = PineconeClient(api_key=os.environ.get("PINECONE_API_KEY"))
    index = pc.Index(INDEX_NAME)
    
    # Use updated model with task_type for better query embeddings
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        task_type="retrieval_query"
    )
    
    # Auto-parse query if enabled
    if auto_parse:
        parsed = parse_query(query)
        parsed_filters = build_pinecone_filter(parsed['filters'])
        search_text = parsed['search_text']
        
        print(f"\n🔍 Parsed Query:")
        print(f"   Search Terms: {search_text}")
        print(f"   Filters: {parsed['filters']}")
        
        # Merge with manual filters if provided
        if filters and parsed_filters:
            combined_filter = {
                '$and': [parsed_filters, filters]
            }
        elif parsed_filters:
            combined_filter = parsed_filters
        else:
            combined_filter = filters
    else:
        search_text = query
        combined_filter = filters
    
    # Generate query embedding with retry logic
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            query_embedding = embeddings.embed_query(search_text)
            break  # Success, exit retry loop
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff: 2, 4, 8 seconds
                    print(f"⏸️ Rate limit hit, waiting {wait_time}s (retry {retry_count}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Failed after {max_retries} retries: {str(e)}")
                    raise
            else:
                print(f"❌ Error generating embedding: {str(e)}")
                raise
    
    # Add small delay to respect rate limits
    time.sleep(REQUEST_DELAY)
    
    # Search with filters
    results = index.query(
        vector=query_embedding,
        top_k=k,
        include_metadata=True,
        filter=combined_filter
    )
    
    # Parse and structure results
    structured_results = []
    for match in results['matches']:
        meta = match['metadata']
        
        # Parse JSON fields if they exist
        pricing_tiers = []
        if meta.get('pricing_tiers'):
            try:
                pricing_tiers = json.loads(meta['pricing_tiers'])
            except:
                pass
        
        product_info = {
            'company': meta.get('company'),
            'sku': meta.get('sku'),
            'name': meta.get('name'),
            'url': meta.get('url'),
            
            # Capacity
            'capacity': f"{meta.get('original_capacity', '')} {meta.get('capacity_uom', '')}",
            'capacity_oz': meta.get('capacity_oz'),
            'normalised_capacity_ml': meta.get('normalised_capacity_ml'),
            
            # Specifications
            'color': meta.get('color'),
            'material': meta.get('material'),
            'shape': meta.get('shape'),
            'category': meta.get('category'),
            'closure_type': meta.get('closure_type'),
            'market_segment': meta.get('market_segment'),
            
            # Availability
            'stock_status': meta.get('stock_status'),
            'in_stock': meta.get('in_stock'),
            
            # Pricing
            'min_price': meta.get('min_price'),
            'max_price': meta.get('max_price'),
            'avg_price': meta.get('avg_price'),
            'has_pricing': meta.get('has_pricing'),
            'pricing_tiers': pricing_tiers,
            
            # Additional
            'items_per_unit': meta.get('items_per_unit'),
            
            # Search relevance
            'similarity_score': match['score']
        }
        
        structured_results.append(product_info)
    
    return structured_results

def display_results(results):
    """Pretty print results for terminal viewing"""
    if not results:
        print("\n❌ No results found")
        return
    
    print(f"\n{'='*80}")
    print(f"Found {len(results)} results:")
    print(f"{'='*80}")
    
    for i, product in enumerate(results, 1):
        print(f"\n{i}. 🧴 {product['name']}")
        print(f"   🏢 Company: {product['company']}")
        print(f"   🔢 SKU: {product['sku']}")
        
        if product.get('capacity_oz'):
            print(f"   📦 Capacity: {product['capacity']} ({product['capacity_oz']:.1f} oz)")
        else:
            print(f"   📦 Capacity: {product['capacity']}")
        
        print(f"   🎨 Color: {product['color']} | Material: {product['material']}")
        print(f"   🔗 URL: {product['url']}")
        
        if product['stock_status']:
            status_emoji = "✅" if product['in_stock'] else "⚠️"
            print(f"   {status_emoji} Stock: {product['stock_status']}")
        
        if product['has_pricing'] and product['min_price']:
            if product['min_price'] == product['max_price']:
                print(f"   💰 Price: ${product['min_price']:.2f} per unit")
            else:
                print(f"   💰 Price Range: ${product['min_price']:.2f} - ${product['max_price']:.2f}")
            
            if product['pricing_tiers']:
                print(f"   💵 Pricing Tiers:")
                for tier in product['pricing_tiers'][:3]:  # Show first 3 tiers
                    qty = tier.get('quantity_of_packing', 'N/A')
                    price = tier.get('price_per_item', 'N/A')
                    packing = tier.get('type_of_packing', '')
                    print(f"      - {qty} {packing}: ${price} each")
        else:
            print(f"   💰 Pricing: Request quote")
        
        print(f"   📊 Similarity Score: {product['similarity_score']:.3f}")

# Example usage
if __name__ == "__main__":
    # Example 1: Natural language query with price and capacity filters
    print("\n" + "="*80)
    print("EXAMPLE 1: Natural Language Query with Price and Capacity Filters")
    print("="*80)
    query1 = "Show me Cary's 32 oz natural packers under $1"
    results1 = search_products(query1, k=5, auto_parse=True)
    display_results(results1)
    
    # Example 2: Simple semantic search
    print("\n\n" + "="*80)
    print("EXAMPLE 2: Simple Semantic Search")
    print("="*80)
    query2 = "amber glass boston round bottles"
    results2 = search_products(query2, k=5, auto_parse=True)
    display_results(results2)
    
    # Example 3: Manual filters
    print("\n\n" + "="*80)
    print("EXAMPLE 3: Query with Manual Filters")
    print("="*80)
    query3 = "bottles for beverages"
    results3 = search_products(
        query3,
        k=5,
        filters={'in_stock': True, 'has_pricing': True},
        auto_parse=False
    )
    print(results3)
    display_results(results3)
