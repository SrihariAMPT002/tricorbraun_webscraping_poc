
# Let me create a comprehensive solution for handling complex queries with filters

query_solution = """
HANDLING COMPLEX QUERIES WITH FILTERS IN RAG SYSTEMS
=====================================================

Query: "Show me Cary's 32 oz natural packers under $1."

This query contains:
1. SEMANTIC component: "natural packers" (needs embedding similarity)
2. STRUCTURED FILTERS: 
   - Brand/Company: "Cary's" 
   - Capacity: "32 oz"
   - Price: "under $1"

THE PROBLEM:
- Pure vector search won't handle numeric filters well
- Embedding "under $1" doesn't guarantee price filtering
- You need HYBRID approach: Vector search + Metadata filtering

═══════════════════════════════════════════════════════════════════════════════
SOLUTION: MULTI-STAGE RETRIEVAL ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════
"""

print(query_solution)

# Create a detailed architecture
architecture = """
STAGE 1: QUERY DECOMPOSITION (Pre-processing)
──────────────────────────────────────────────
Use an LLM or rule-based parser to extract:

{
  "semantic_query": "natural packers",
  "filters": {
    "brand": "Cary's",
    "capacity_oz": 32,
    "price_max": 1.0,
    "capacity_uom": "oz"
  }
}

STAGE 2: VECTOR SEARCH WITH METADATA FILTERING
───────────────────────────────────────────────
Pinecone supports metadata filtering during query time!

vector_search_params = {
  "vector": embed("natural packers"),  # Only embed semantic part
  "filter": {
    "$and": [
      {"company": {"$eq": "Cary's"}},
      {"normalized_capacity_ml": {"$gte": 900, "$lte": 960}},  # ~32 oz ±10%
      {"avg_price_per_unit": {"$lte": 1.0}},
      {"has_pricing": {"$eq": True}}
    ]
  },
  "top_k": 20,
  "include_metadata": True
}

WHY THIS WORKS:
✓ Vector search finds semantically relevant products ("natural packers")
✓ Metadata filters applied at database level (fast, precise)
✓ Only relevant products retrieved, reducing noise
✓ Chatbot receives high-quality, pre-filtered results


STAGE 3: POST-RETRIEVAL RANKING (Optional)
───────────────────────────────────────────
Apply business logic to re-rank results:

1. Exact capacity match > approximate capacity
2. In-stock > out-of-stock
3. Lower price > higher price (within threshold)
4. Cosine similarity score as tiebreaker
"""

print(architecture)
