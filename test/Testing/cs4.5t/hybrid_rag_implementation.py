
"""
COMPLETE IMPLEMENTATION FOR HYBRID RAG RETRIEVAL
================================================
"""

import re
from typing import Dict, List, Any, Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeStore
from pinecone import Pinecone as PineconeClient
import json

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: QUERY DECOMPOSITION
# ═══════════════════════════════════════════════════════════════════════════════

class QueryDecomposer:
    """Extract structured filters and semantic query from natural language"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client  # Gemini 2.5 Flash

    def decompose_with_llm(self, query: str) -> Dict:
        """Use LLM to extract filters (most robust)"""

        prompt = f"""
        Extract structured information from this product search query.

        Query: "{query}"

        Return JSON with:
        {{
          "semantic_query": "the descriptive/semantic part",
          "filters": {{
            "brand": "brand name or null",
            "company": "company name or null",
            "capacity_value": numeric value or null,
            "capacity_uom": "oz/ml/l" or null,
            "price_min": numeric or null,
            "price_max": numeric or null,
            "color": "color name or null",
            "material": "material or null",
            "shape": "shape or null",
            "in_stock_only": true/false
          }}
        }}

        Rules:
        - semantic_query should contain product type, style, description
        - Extract ALL numeric values
        - Normalize units (oz, ounce, fl oz → "oz")
        - "under X" means price_max = X
        - "over X" means price_min = X
        """

        # Call your Gemini API here
        response = self.llm_client.generate(prompt)
        return json.loads(response)

    def decompose_with_rules(self, query: str) -> Dict:
        """Rule-based extraction (faster, no API call)"""

        filters = {}
        semantic_parts = []

        # Extract capacity (e.g., "32 oz", "500ml", "1 liter")
        capacity_pattern = r'(\d+(?:\.\d+)?)\s*(oz|ounce|fl oz|ml|milliliter|l|liter)s?'
        capacity_match = re.search(capacity_pattern, query, re.IGNORECASE)
        if capacity_match:
            filters['capacity_value'] = float(capacity_match.group(1))
            filters['capacity_uom'] = self._normalize_uom(capacity_match.group(2))
            query = re.sub(capacity_pattern, '', query, flags=re.IGNORECASE)

        # Extract price constraints
        # "under $1", "below $1", "less than $1"
        price_under = re.search(r'(?:under|below|less than|<)\s*\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if price_under:
            filters['price_max'] = float(price_under.group(1))
            query = re.sub(r'(?:under|below|less than|<)\s*\$?\d+(?:\.\d+)?', '', query, flags=re.IGNORECASE)

        # "over $5", "above $5", "more than $5"
        price_over = re.search(r'(?:over|above|more than|>)\s*\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        if price_over:
            filters['price_min'] = float(price_over.group(1))
            query = re.sub(r'(?:over|above|more than|>)\s*\$?\d+(?:\.\d+)?', '', query, flags=re.IGNORECASE)

        # Extract brand/company names (you'd maintain a list)
        known_brands = ['Cary\'s', 'Berlin Packaging', 'TricorBraun', 'O-I', 'Ardagh']
        for brand in known_brands:
            if brand.lower() in query.lower():
                filters['company'] = brand
                query = re.sub(re.escape(brand), '', query, flags=re.IGNORECASE)

        # Extract color
        colors = ['clear', 'amber', 'blue', 'green', 'natural', 'white', 'black']
        for color in colors:
            if re.search(r'\b' + color + r'\b', query, re.IGNORECASE):
                filters['color'] = color.title()
                # Don't remove - might be semantic

        # In stock
        if re.search(r'in stock|available', query, re.IGNORECASE):
            filters['in_stock_only'] = True
            query = re.sub(r'in stock|available', '', query, flags=re.IGNORECASE)

        # Clean up remaining query as semantic
        semantic_query = ' '.join(query.split()).strip()

        return {
            'semantic_query': semantic_query,
            'filters': {k: v for k, v in filters.items() if v is not None}
        }

    def _normalize_uom(self, uom: str) -> str:
        """Normalize unit of measure"""
        uom_lower = uom.lower()
        if uom_lower in ['oz', 'ounce', 'fl oz']:
            return 'oz'
        elif uom_lower in ['ml', 'milliliter']:
            return 'ml'
        elif uom_lower in ['l', 'liter']:
            return 'l'
        return uom_lower


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: BUILD PINECONE FILTER
# ═══════════════════════════════════════════════════════════════════════════════

class FilterBuilder:
    """Convert extracted filters to Pinecone metadata filter"""

    @staticmethod
    def capacity_to_ml(value: float, uom: str) -> float:
        """Convert capacity to ml for filtering"""
        conversions = {
            'oz': 29.5735,
            'ml': 1.0,
            'l': 1000.0
        }
        return value * conversions.get(uom, 1.0)

    @staticmethod
    def build_filter(filters: Dict) -> Dict:
        """Build Pinecone metadata filter from extracted filters"""

        conditions = []

        # Company/Brand filter
        if 'company' in filters:
            conditions.append({
                "company": {"$eq": filters['company']}
            })

        # Capacity filter (with tolerance)
        if 'capacity_value' in filters and 'capacity_uom' in filters:
            target_ml = FilterBuilder.capacity_to_ml(
                filters['capacity_value'], 
                filters['capacity_uom']
            )
            # Allow ±10% tolerance
            conditions.append({
                "normalized_capacity_ml": {
                    "$gte": target_ml * 0.9,
                    "$lte": target_ml * 1.1
                }
            })

        # Price filters
        if 'price_max' in filters:
            conditions.append({
                "avg_price_per_unit": {"$lte": filters['price_max']}
            })

        if 'price_min' in filters:
            conditions.append({
                "avg_price_per_unit": {"$gte": filters['price_min']}
            })

        # Ensure product has pricing data
        if 'price_max' in filters or 'price_min' in filters:
            conditions.append({
                "has_pricing": {"$eq": True}
            })

        # Color filter
        if 'color' in filters:
            conditions.append({
                "color": {"$eq": filters['color']}
            })

        # Material filter
        if 'material' in filters:
            conditions.append({
                "material": {"$eq": filters['material']}
            })

        # Stock filter
        if filters.get('in_stock_only'):
            conditions.append({
                "in_stock": {"$eq": True}
            })

        # Combine all conditions with AND
        if len(conditions) == 0:
            return {}
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: RETRIEVAL ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class HybridRetriever:
    """Orchestrates query decomposition, filtering, and retrieval"""

    def __init__(self, index_name: str, embedding_model: str = "models/embedding-001"):
        self.embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)
        self.pinecone_client = PineconeClient()
        self.index = self.pinecone_client.Index(index_name)
        self.decomposer = QueryDecomposer()
        self.filter_builder = FilterBuilder()

    def retrieve(self, query: str, top_k: int = 20) -> List[Dict]:
        """
        Main retrieval method

        Args:
            query: Natural language query
            top_k: Number of results to retrieve

        Returns:
            List of products with metadata and scores
        """

        # Step 1: Decompose query
        decomposed = self.decomposer.decompose_with_rules(query)
        print(f"Decomposed query: {json.dumps(decomposed, indent=2)}")

        semantic_query = decomposed['semantic_query']
        filters = decomposed.get('filters', {})

        # Step 2: Build Pinecone filter
        pinecone_filter = self.filter_builder.build_filter(filters)
        print(f"Pinecone filter: {json.dumps(pinecone_filter, indent=2)}")

        # Step 3: Embed semantic query ONLY
        if semantic_query and semantic_query.strip():
            query_embedding = self.embeddings.embed_query(semantic_query)
        else:
            # If no semantic component, use generic embedding
            query_embedding = self.embeddings.embed_query("product")

        # Step 4: Query Pinecone with filter
        results = self.index.query(
            vector=query_embedding,
            filter=pinecone_filter if pinecone_filter else None,
            top_k=top_k,
            include_metadata=True
        )

        # Step 5: Format results
        products = []
        for match in results.get('matches', []):
            products.append({
                'id': match['id'],
                'score': match['score'],
                'metadata': match['metadata']
            })

        print(f"\nRetrieved {len(products)} products")

        return products

    def retrieve_with_reranking(self, query: str, top_k: int = 20) -> List[Dict]:
        """Retrieve with post-retrieval reranking"""

        products = self.retrieve(query, top_k=top_k * 2)  # Get more candidates

        # Apply business logic reranking
        def rank_score(product):
            score = product['score']  # Base cosine similarity
            metadata = product['metadata']

            # Boost in-stock items
            if metadata.get('in_stock'):
                score += 0.1

            # Boost lower prices (normalize to 0-0.1 range)
            price = metadata.get('avg_price_per_unit', float('inf'))
            if price < float('inf'):
                score += (1.0 / (1.0 + price)) * 0.05

            return score

        # Sort by enhanced score
        products.sort(key=rank_score, reverse=True)

        return products[:top_k]


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Initialize retriever
    retriever = HybridRetriever(
        index_name="processed_products-index"
    )

    # User query
    user_query = "Show me Cary's 32 oz natural packers under $1."

    # Retrieve relevant products
    products = retriever.retrieve_with_reranking(user_query, top_k=10)

    # Format for LLM context
    context = []
    for i, product in enumerate(products, 1):
        meta = product['metadata']
        context.append(f"""
Product {i}:
- Name: {meta.get('name', 'N/A')}
- Capacity: {meta.get('capacity', 'N/A')}
- Price: ${meta.get('avg_price_per_unit', 'N/A')}
- Color: {meta.get('color', 'N/A')}
- Availability: {meta.get('availability', 'N/A')}
- URL: {meta.get('url', 'N/A')}
        """.strip())

    context_text = "\n\n".join(context)

    # Send to Gemini 2.5 Flash
    prompt = f"""
User Query: {user_query}

Based on these products, provide a helpful response:

{context_text}

Instructions:
- List products that match the criteria
- Include key details (price, capacity, availability)
- If no exact matches, suggest alternatives
- Format as a friendly, informative response
"""

    print("\n" + "="*80)
    print("FINAL PROMPT TO GEMINI:")
    print("="*80)
    print(prompt)

    # response = gemini_client.generate(prompt)
    # return response

if __name__ == "__main__":
    main()
