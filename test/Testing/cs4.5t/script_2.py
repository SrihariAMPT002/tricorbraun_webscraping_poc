
# Create a summary document with key recommendations

summary = """
═══════════════════════════════════════════════════════════════════════════════
OPTIMIZING DATA QUALITY FOR COMPLEX QUERIES: KEY RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════════════════

QUERY: "Show me Cary's 32 oz natural packers under $1."

═══════════════════════════════════════════════════════════════════════════════
1. METADATA STRUCTURE (CRITICAL FOR FILTERING)
═══════════════════════════════════════════════════════════════════════════════

Your metadata must support Pinecone's filtering operators. Required fields:

ESSENTIAL METADATA FIELDS:
┌─────────────────────────────┬──────────────┬───────────────────────────────┐
│ Field Name                  │ Type         │ Purpose                       │
├─────────────────────────────┼──────────────┼───────────────────────────────┤
│ product_id / sku            │ string       │ Unique identifier             │
│ company                     │ string       │ Brand filtering (exact match) │
│ normalized_capacity_ml      │ float        │ Numeric capacity comparison   │
│ capacity_uom                │ string       │ Original unit reference       │
│ avg_price_per_unit          │ float        │ Price range filtering         │
│ has_pricing                 │ boolean      │ Exclude products w/o pricing  │
│ color                       │ string       │ Color filtering (exact match) │
│ material                    │ string       │ Material filtering            │
│ shape                       │ string       │ Shape filtering               │
│ category                    │ string       │ Product category              │
│ in_stock                    │ boolean      │ Availability filtering        │
│ availability                │ string       │ Human-readable status         │
│ url                         │ string       │ Product page link             │
│ name                        │ string       │ Display name                  │
└─────────────────────────────┴──────────────┴───────────────────────────────┘

CRITICAL: All filterable fields must be indexed in Pinecone metadata!


═══════════════════════════════════════════════════════════════════════════════
2. EMBEDDED_TEXT STRUCTURE (FOR SEMANTIC SEARCH)
═══════════════════════════════════════════════════════════════════════════════

embedded_text should contain ONLY semantic/descriptive content:

GOOD embedded_text:
─────────────────────────────────────────────────────────────────────────────
Product: 32 oz Natural HDPE Packer Bottles
Specifications: Capacity: 32 oz (946 ml), Material: HDPE, Color: Natural, 
Shape: Packer, Neck Finish: 38-400
Suitable for food storage, dairy products, sauces, and condiments. Wide-mouth 
design for easy filling. Compatible with standard 38mm closures.
Starting at $0.85 per unit
Availability: In Stock
─────────────────────────────────────────────────────────────────────────────

BAD embedded_text (too structured, loses semantic meaning):
─────────────────────────────────────────────────────────────────────────────
sku: #YAB32BULK
company: Cary's
price: 0.85
capacity_ml: 946
color: Natural
─────────────────────────────────────────────────────────────────────────────

WHY: Embeddings work best with natural language, not key-value pairs!


═══════════════════════════════════════════════════════════════════════════════
3. RECOMMENDED DATA NORMALIZATION
═══════════════════════════════════════════════════════════════════════════════

BEFORE UPLOADING TO PINECONE:

A. Normalize Capacity to ML:
   - Always convert to ml for filtering
   - Store original unit for display
   - 1 oz = 29.5735 ml
   - 1 L = 1000 ml

B. Standardize Company Names:
   - "Cary's" vs "Carys" vs "CARY'S" → all become "Cary's"
   - Maintain a mapping dictionary

C. Normalize Colors:
   - "natural", "Natural", "NATURAL" → "Natural"
   - "clear", "Clear" → "Clear"
   - Use Title Case consistently

D. Price Validation:
   - Set has_pricing = True only if price > 0
   - Use avg_price_per_unit for filtering
   - Store quantity_breaks as JSON string in metadata

E. Boolean Fields:
   - in_stock: True/False (not "In Stock"/"Out of Stock")
   - has_pricing: True/False
   - has_description: True/False


═══════════════════════════════════════════════════════════════════════════════
4. QUERY PROCESSING PIPELINE
═══════════════════════════════════════════════════════════════════════════════

User Query → Query Decomposer → Filter Builder → Vector Search → Re-ranking → LLM

STAGE 1: Extract filters using regex or LLM
   Input:  "Show me Cary's 32 oz natural packers under $1"
   Output: {
             semantic: "natural packers",
             filters: {company: "Cary's", capacity: 32 oz, price_max: 1.0}
           }

STAGE 2: Build Pinecone filter
   {
     "$and": [
       {"company": {"$eq": "Cary's"}},
       {"normalized_capacity_ml": {"$gte": 850, "$lte": 1040}},
       {"avg_price_per_unit": {"$lte": 1.0}},
       {"has_pricing": {"$eq": true}}
     ]
   }

STAGE 3: Embed ONLY semantic part
   embed("natural packers")  ← NOT the entire query!

STAGE 4: Query Pinecone
   - Vector similarity on "natural packers"
   - Filters applied at database level
   - Returns only matching products

STAGE 5: Re-rank (optional)
   - Boost in-stock items
   - Prefer lower prices
   - Consider exact capacity matches

STAGE 6: Send to Gemini
   - Clean, filtered, relevant products only
   - Reduced context window usage
   - Higher quality responses


═══════════════════════════════════════════════════════════════════════════════
5. IMPLEMENTATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

□ Update upload.py to include all required metadata fields
□ Normalize capacity to ml (normalized_capacity_ml)
□ Standardize company/brand names (case-sensitive matching)
□ Add has_pricing boolean field
□ Add in_stock boolean field
□ Ensure embedded_text is natural language (not key-value)
□ Implement QueryDecomposer class for filter extraction
□ Implement FilterBuilder class for Pinecone filters
□ Update retrieval to use metadata filtering
□ Add post-retrieval re-ranking logic
□ Test with various query types:
  - Price queries: "under $1", "between $0.50 and $2"
  - Capacity queries: "32 oz", "1 liter", "500ml"
  - Combined queries: "blue 16 oz bottles under $0.50"
  - Availability queries: "in stock amber bottles"


═══════════════════════════════════════════════════════════════════════════════
6. PERFORMANCE OPTIMIZATIONS
═══════════════════════════════════════════════════════════════════════════════

FAST PATH (Rule-based):
- Use regex for standard queries (capacity, price, color)
- No LLM call needed
- ~50ms latency

SLOW PATH (LLM-based):
- Use Gemini for complex queries
- Better accuracy for ambiguous queries
- ~500-1000ms latency

HYBRID APPROACH:
- Try rule-based first
- Fall back to LLM if confidence < threshold
- Best of both worlds


═══════════════════════════════════════════════════════════════════════════════
7. EXPECTED IMPROVEMENTS
═══════════════════════════════════════════════════════════════════════════════

WITHOUT metadata filtering:
  ❌ Retrieves ~100 products
  ❌ Many irrelevant results (wrong price, capacity, brand)
  ❌ LLM must filter in context (wastes tokens)
  ❌ Slower response time
  ❌ Lower accuracy

WITH metadata filtering:
  ✅ Retrieves ~10-20 highly relevant products
  ✅ All results match filters exactly
  ✅ LLM focuses on ranking/formatting only
  ✅ Faster response time (less context)
  ✅ Higher accuracy (95%+ vs 70-80%)


═══════════════════════════════════════════════════════════════════════════════
8. EXAMPLE METADATA FOR BERLIN PACKAGING
═══════════════════════════════════════════════════════════════════════════════

{
  "product_id": "#YAB32BULK",
  "company": "Cary's",
  "name": "32 oz Natural HDPE Packer Bottles",
  "url": "https://...",
  
  "normalized_capacity_ml": 946.0,
  "capacity": "32 oz",
  "capacity_uom": "oz",
  
  "color": "Natural",
  "material": "HDPE",
  "shape": "Packer",
  "category": "Bottles",
  "closure_type": "38-400",
  "market_segment": "Food & Beverage",
  
  "avg_price_per_unit": 0.85,
  "has_pricing": true,
  "pricing_data": "[{...}]",  // JSON string
  
  "availability": "In Stock",
  "in_stock": true,
  "stock": "In Stock",
  "items_per_unit": "Case of 200"
}


═══════════════════════════════════════════════════════════════════════════════
NEXT STEPS
═══════════════════════════════════════════════════════════════════════════════

1. Update your upload.py with the new metadata structure
2. Implement the HybridRetriever class
3. Test query decomposition with sample queries
4. Re-upload your data to Pinecone with proper metadata
5. Integrate with your Gemini chatbot
6. Monitor query performance and iterate
"""

print(summary)

# Save summary
with open('rag_optimization_guide.txt', 'w') as f:
    f.write(summary)

print("\n" + "="*80)
print("Summary saved to: rag_optimization_guide.txt")
print("="*80)
