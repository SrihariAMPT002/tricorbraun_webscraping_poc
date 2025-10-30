from pinecone import Pinecone as PineconeClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
import json

load_dotenv()

def search_products(query, k=10, filters=None):
    """
    Enhanced search with complete data retrieval
    
    Args:
        query: Search query
        k: Number of results
        filters: Optional dict for filtering (e.g., {'in_stock': True})
    """
    # Initialize
    pc = PineconeClient()
    index = pc.Index("products-index")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    
    # Generate query embedding
    query_embedding = embeddings.embed_query(query)
    
    # Search with optional filters
    results = index.query(
        vector=query_embedding,
        top_k=k,
        include_metadata=True,
        filter=filters  # e.g., {'in_stock': True, 'has_pricing': True}
    )
    
    # Parse and structure results for chatbot
    structured_results = []
    for match in results['matches']:
        meta = match['metadata']
        
        # Parse JSON fields
        pricing = json.loads(meta.get('pricing_data', '[]'))
        accessories = json.loads(meta.get('accessories', '[]'))
        all_specs = json.loads(meta.get('all_specs', '{}'))
        
        product_info = {
            'product_id': meta.get('product_id'),
            'name': meta.get('name'),
            'url': meta.get('url'),
            'description': meta.get('description'),
            'image_url': meta.get('image_url'),
            
            # Specifications
            'capacity': meta.get('capacity'),
            'normalized_capacity_ml': meta.get('normalized_capacity_ml'),
            'material': meta.get('material'),
            'color': meta.get('color'),
            'style': meta.get('style'),
            'all_specs': all_specs,
            
            # Availability
            'availability': meta.get('availability'),
            'in_stock': meta.get('in_stock'),
            
            # Pricing
            'pricing': pricing,
            'has_pricing': meta.get('has_pricing'),
            
            # Accessories
            'accessories': accessories,
            
            # Search relevance
            'similarity_score': match['score']
        }
        
        structured_results.append(product_info)
    
    return structured_results

# Example usage
if __name__ == "__main__":
    query = "show me 10oz beer bottles"
    
    # Basic search
    results = search_products(query, k=3)
    
    # Search with filters
    results_in_stock = search_products(
        query, 
        k=5, 
        filters={'in_stock': True, 'has_pricing': True}
    )
    print(results)
    # Display for chatbot
    # for product in results:
    #     print(f"\n{'='*80}")
    #     print(f"🧴 {product['name']}")
    #     print(f"📦 Capacity: {product['capacity']} ({product['normalized_capacity_ml']} ml)")
    #     print(f"🔗 URL: {product['url']}")
    #     print(f"📸 Image: {product['image_url']}")
    #     print(f"✅ Availability: {product['availability']}")
        
    #     if product['pricing']:
    #         print(f"💰 Pricing Tiers:")
    #         for tier in product['pricing']:
    #             print(f"   - {tier['qty_range']}: {tier['price_per_unit']}")
    #     else:
    #         print(f"💰 Pricing: Request quote")
        
    #     if product['accessories']:
    #         print(f"🔧 Compatible Accessories: {len(product['accessories'])} available")
