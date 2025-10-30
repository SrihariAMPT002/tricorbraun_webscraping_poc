import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pinecone import Pinecone as PineconeClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
import json
from typing import List, Dict, Any, Optional, Callable
import logging
from datetime import datetime

load_dotenv()

class HybridRAGChatbot:
    """
    Hybrid RAG Chatbot with verbose mode for detailed execution tracking
    """
    
    def __init__(self, verbose: bool = False, logger: Optional[logging.Logger] = None):
        """
        Initialize the chatbot with optional verbose mode
        
        Args:
            verbose (bool): Enable detailed logging of operations
            logger (Optional[logging.Logger]): Custom logger instance
        """
        self.verbose = verbose
        self.logger = logger or self._setup_logger()
        
        self._log("🚀 Initializing Hybrid RAG Chatbot...", level="info")
        
        # Initialize MongoDB
        self._log("📊 Connecting to MongoDB...", level="info")
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI not found in environment variables")
        
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[os.getenv("MONGO_DB", "product_catalog")]
        self.collection = self.db[os.getenv("MONGO_COLLECTION", "processed_data")]
        self._log(f"✅ Connected to MongoDB: {os.getenv('MONGO_DB', 'product_catalog')}", level="info")
        
        # Initialize Pinecone
        self._log("🔍 Connecting to Pinecone...", level="info")
        pc = PineconeClient(api_key=os.getenv("PINECONE_API_KEY"))
        self.pinecone_index = pc.Index(os.getenv("PINECONE_INDEX", "processed-products-index"))
        self._log(f"✅ Connected to Pinecone index: {os.getenv('PINECONE_INDEX', 'processed-products-index')}", level="info")
        
        # Initialize embeddings and LLM
        self._log("🧠 Initializing Gemini models...", level="info")
        self.embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            convert_system_message_to_human=True
        )
        self._log("✅ Gemini models initialized successfully", level="info")
        self._log("🎉 Chatbot initialization complete!\n", level="info")
    
    def _setup_logger(self) -> logging.Logger:
        """Setup default logger for verbose output"""
        logger = logging.getLogger("HybridRAGChatbot")
        logger.setLevel(logging.DEBUG if self.verbose else logging.WARNING)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _log(self, message: str, level: str = "debug", data: Any = None):
        """
        Internal logging method that respects verbose flag
        
        Args:
            message (str): Log message
            level (str): Log level (debug, info, warning, error)
            data (Any): Optional data to log
        """
        if not self.verbose:
            return
        
        log_method = getattr(self.logger, level.lower(), self.logger.debug)
        log_method(message)
        
        if data is not None:
            log_method(f"  Data: {json.dumps(data, indent=2)}")
    
    def set_verbose(self, verbose: bool):
        """
        Toggle verbose mode on/off during runtime
        
        Args:
            verbose (bool): Enable or disable verbose logging
        """
        self.verbose = verbose
        self.logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
        self._log(f"Verbose mode {'enabled' if verbose else 'disabled'}", level="info")
    
    def analyze_query_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Use Gemini to analyze user intent and extract structured parameters
        """
        self._log("\n" + "="*80, level="info")
        self._log("🔍 STEP 1: Query Intent Analysis", level="info")
        self._log("="*80, level="info")
        self._log(f"📝 User Query: '{user_query}'", level="info")
        
        analysis_prompt = f"""
Analyze this user query and extract structured information:

Query: "{user_query}"

Extract and return JSON with these fields:
- intent: "product_search" | "pricing_query" | "availability_check" | "comparison" | "general_question"
- filters: {{
    "capacity": "value with unit if mentioned",
    "capacity_range": {{"min": number, "max": number}},
    "color": "color if mentioned",
    "material": "material if mentioned",
    "shape": "shape if mentioned",
    "company": "company name if mentioned",
    "price_range": {{"min": number, "max": number}},
    "stock_required": boolean
  }}
- quantity: number if user asks about bulk pricing
- comparison_items: list of products if comparing

Only include fields that are explicitly mentioned or clearly implied.
Return valid JSON only, no markdown.
"""
        
        self._log("🤖 Sending query to Gemini for intent analysis...", level="info")
        response = self.llm.invoke(analysis_prompt)
        
        try:
            intent_data = json.loads(response.content.strip().strip('``````'))
            self._log("✅ Intent analysis successful", level="info")
            self._log("📊 Extracted Intent:", level="info", data=intent_data)
            return intent_data
        except Exception as e:
            self._log(f"⚠️ Failed to parse intent JSON: {str(e)}", level="warning")
            self._log("📋 Falling back to general question intent", level="info")
            return {"intent": "general_question", "filters": {}}
    
    def semantic_search(self, query: str, top_k: int = 5, filters: Dict = None) -> List[Dict]:
        """
        Perform semantic search using Pinecone with optional metadata filters
        """
        self._log("\n" + "="*80, level="info")
        self._log("🔍 STEP 2: Semantic Search (Pinecone)", level="info")
        self._log("="*80, level="info")
        self._log(f"🎯 Searching for top {top_k} relevant products", level="info")
        
        # Generate query embedding
        self._log("🧮 Generating query embedding...", level="info")
        start_time = datetime.now()
        query_embedding = self.embeddings_model.embed_query(query)
        embedding_time = (datetime.now() - start_time).total_seconds()
        self._log(f"✅ Embedding generated in {embedding_time:.2f}s (dimension: {len(query_embedding)})", level="info")
        
        # Build Pinecone filter from extracted filters
        pinecone_filter = {}
        if filters:
            self._log("🔧 Building Pinecone metadata filters...", level="info")
            if filters.get("color"):
                pinecone_filter["color"] = {"$eq": filters["color"]}
            if filters.get("material"):
                pinecone_filter["material"] = {"$eq": filters["material"]}
            if filters.get("company"):
                pinecone_filter["company"] = {"$eq": filters["company"]}
            if filters.get("stock_required"):
                pinecone_filter["in_stock"] = True
            if filters.get("price_range"):
                price_range = filters["price_range"]
                if price_range.get("min"):
                    pinecone_filter["min_price"] = {"$gte": price_range["min"]}
                if price_range.get("max"):
                    pinecone_filter["max_price"] = {"$lte": price_range["max"]}
            
            self._log("📋 Applied filters:", level="info", data=pinecone_filter)
        
        # Search Pinecone
        search_params = {
            "vector": query_embedding,
            "top_k": top_k,
            "include_metadata": True
        }
        if pinecone_filter:
            search_params["filter"] = pinecone_filter
        
        self._log("🔎 Querying Pinecone vector database...", level="info")
        start_time = datetime.now()
        results = self.pinecone_index.query(**search_params)
        search_time = (datetime.now() - start_time).total_seconds()
        
        matches = results['matches']
        self._log(f"✅ Found {len(matches)} matching products in {search_time:.2f}s", level="info")
        
        if matches:
            self._log("📦 Top matches (by similarity score):", level="info")
            for i, match in enumerate(matches[:3], 1):
                self._log(
                    f"  {i}. SKU: {match['id']}, Score: {match['score']:.4f}, "
                    f"Name: {match.get('metadata', {}).get('name', 'N/A')[:50]}...",
                    level="info"
                )
        
        return matches
    
    def fetch_complete_product_data(self, skus: List[str]) -> List[Dict]:
        """
        Fetch complete product data from MongoDB including full pricing tiers
        """
        self._log("\n" + "="*80, level="info")
        self._log("📊 STEP 3: Fetching Complete Product Data (MongoDB)", level="info")
        self._log("="*80, level="info")
        self._log(f"📋 Fetching data for {len(skus)} SKUs from MongoDB", level="info")
        
        start_time = datetime.now()
        products = list(self.collection.find(
            {"sku": {"$in": skus}},
            {"_id": 0}
        ))
        fetch_time = (datetime.now() - start_time).total_seconds()
        
        self._log(f"✅ Retrieved {len(products)} complete product records in {fetch_time:.2f}s", level="info")
        
        if products:
            self._log("📦 Product summary:", level="info")
            for i, product in enumerate(products[:3], 1):
                pricing_tiers = len(product.get('quantity_breaks', []))
                self._log(
                    f"  {i}. {product.get('name', 'N/A')} - "
                    f"Company: {product.get('company', 'N/A')}, "
                    f"Pricing tiers: {pricing_tiers}",
                    level="info"
                )
        else:
            self._log("⚠️ No products found in MongoDB for given SKUs", level="warning")
        
        return products
    
    def generate_mongodb_query(self, filters: Dict) -> Dict:
        """
        Generate MongoDB query from extracted filters
        """
        self._log("🔍 Generating MongoDB query from filters...", level="info")
        mongo_query = {}
        
        if filters.get("color"):
            mongo_query["color"] = {"$regex": filters["color"], "$options": "i"}
        
        if filters.get("material"):
            mongo_query["material"] = {"$regex": filters["material"], "$options": "i"}
        
        if filters.get("shape"):
            mongo_query["shape"] = {"$regex": filters["shape"], "$options": "i"}
        
        if filters.get("company"):
            mongo_query["company"] = {"$regex": filters["company"], "$options": "i"}
        
        if filters.get("capacity_range"):
            cap_range = filters["capacity_range"]
            if cap_range.get("min") or cap_range.get("max"):
                mongo_query["normalised_capacity_ml"] = {}
                if cap_range.get("min"):
                    mongo_query["normalised_capacity_ml"]["$gte"] = cap_range["min"]
                if cap_range.get("max"):
                    mongo_query["normalised_capacity_ml"]["$lte"] = cap_range["max"]
        
        if filters.get("price_range"):
            price_range = filters["price_range"]
            if price_range.get("min") or price_range.get("max"):
                mongo_query["avg_price_per_unit"] = {}
                if price_range.get("min"):
                    mongo_query["avg_price_per_unit"]["$gte"] = price_range["min"]
                if price_range.get("max"):
                    mongo_query["avg_price_per_unit"]["$lte"] = price_range["max"]
        
        if filters.get("stock_required"):
            mongo_query["stock"] = {"$regex": "In Stock", "$options": "i"}
        
        if mongo_query:
            self._log("📋 Generated MongoDB query:", level="info", data=mongo_query)
        else:
            self._log("ℹ️ No MongoDB filters needed", level="info")
        
        return mongo_query
    
    def extract_pricing_for_quantity(self, product: Dict, quantity: int) -> Dict:
        """
        Extract the appropriate pricing tier for a given quantity
        """
        self._log(f"💰 Extracting pricing for quantity: {quantity}", level="debug")
        quantity_breaks = product.get("quantity_breaks", [])
        
        if not quantity_breaks:
            self._log("⚠️ No quantity breaks found, using average price", level="debug")
            return {
                "quantity": quantity,
                "price_per_item": product.get("avg_price_per_unit", "N/A"),
                "total_price": None
            }
        
        # Find the appropriate pricing tier
        applicable_tier = None
        for tier in sorted(quantity_breaks, key=lambda x: x.get("quantity_of_packing", 0)):
            tier_qty = tier.get("quantity_of_packing", 0)
            if quantity >= tier_qty:
                applicable_tier = tier
        
        if applicable_tier:
            price_per_item = applicable_tier.get("price_per_item")
            self._log(
                f"✅ Found pricing tier: {applicable_tier.get('quantity_of_packing')}+ units "
                f"at ${price_per_item} per item",
                level="debug"
            )
            return {
                "quantity": quantity,
                "tier_quantity": applicable_tier.get("quantity_of_packing"),
                "price_per_item": price_per_item,
                "type_of_packing": applicable_tier.get("type_of_packing"),
                "unit_quantity": applicable_tier.get("unit_quantity"),
                "total_price": price_per_item * quantity if price_per_item else None
            }
        else:
            # Use first tier if quantity is below all tiers
            first_tier = quantity_breaks[0]
            price_per_item = first_tier.get("price_per_item")
            self._log(
                f"ℹ️ Quantity below minimum tier, using first tier: ${price_per_item} per item",
                level="debug"
            )
            return {
                "quantity": quantity,
                "tier_quantity": first_tier.get("quantity_of_packing"),
                "price_per_item": price_per_item,
                "type_of_packing": first_tier.get("type_of_packing"),
                "unit_quantity": first_tier.get("unit_quantity"),
                "total_price": price_per_item * quantity if price_per_item else None
            }
    
    def format_product_context(self, products: List[Dict], quantity: int = None) -> str:
        """
        Format product data for LLM context with complete pricing information
        """
        self._log("\n" + "="*80, level="info")
        self._log("📝 STEP 4: Formatting Product Context for LLM", level="info")
        self._log("="*80, level="info")
        self._log(f"📋 Formatting {len(products)} products for context", level="info")
        
        context_parts = []
        
        for i, product in enumerate(products, 1):
            context = f"\n--- Product {i} ---\n"
            context += f"Name: {product.get('name', 'N/A')}\n"
            context += f"SKU: {product.get('sku', 'N/A')}\n"
            context += f"Company: {product.get('company', 'N/A')}\n"
            context += f"Capacity: {product.get('original_capacity', 'N/A')} {product.get('original_uom', '')}\n"
            context += f"Color: {product.get('color', 'N/A')}\n"
            context += f"Material: {product.get('material', 'N/A')}\n"
            context += f"Shape: {product.get('shape', 'N/A')}\n"
            context += f"Stock Status: {product.get('stock', 'N/A')}\n"
            
            # Detailed pricing information
            if quantity:
                pricing = self.extract_pricing_for_quantity(product, quantity)
                context += f"\nPricing for {quantity} units:\n"
                context += f"  - Price per item: ${pricing['price_per_item']}\n"
                if pricing.get('total_price'):
                    context += f"  - Total price: ${pricing['total_price']:.2f}\n"
                context += f"  - Packaging: {pricing.get('type_of_packing', 'N/A')}\n"
            else:
                # Show all pricing tiers
                quantity_breaks = product.get('quantity_breaks', [])
                if quantity_breaks:
                    context += "\nPricing Tiers:\n"
                    for tier in quantity_breaks:
                        qty = tier.get('quantity_of_packing', 'N/A')
                        price = tier.get('price_per_item', 'N/A')
                        packing = tier.get('type_of_packing', 'N/A')
                        context += f"  - {qty}+ units: ${price} per item ({packing})\n"
                else:
                    avg_price = product.get('avg_price_per_unit')
                    context += f"\nAverage Price: ${avg_price if avg_price else 'N/A'}\n"
            
            context += f"URL: {product.get('url', 'N/A')}\n"
            context_parts.append(context)
        
        formatted_context = "\n".join(context_parts)
        self._log(f"✅ Context formatted ({len(formatted_context)} characters)", level="info")
        
        return formatted_context
    
    def query(self, user_query: str, verbose_override: Optional[bool] = None) -> str:
        """
        Main query method that orchestrates the hybrid RAG pipeline
        
        Args:
            user_query (str): User's question
            verbose_override (Optional[bool]): Temporarily override verbose setting for this query
        
        Returns:
            str: Generated response
        """
        # Temporarily override verbose mode if specified
        original_verbose = self.verbose
        if verbose_override is not None:
            self.set_verbose(verbose_override)
        
        try:
            # self._log("\n" + "🚀 "*40, level="info")
            self._log("🤖 NEW QUERY EXECUTION", level="info")
            # self._log("🚀 "*40 + "\n", level="info")
            
            # Step 1: Analyze query intent
            intent_analysis = self.analyze_query_intent(user_query)
            intent = intent_analysis.get("intent", "general_question")
            filters = intent_analysis.get("filters", {})
            quantity = intent_analysis.get("quantity")
            
            self._log(f"\n💡 Detected Intent: {intent.upper()}", level="info")
            if quantity:
                self._log(f"📦 Requested Quantity: {quantity}", level="info")
            
            # Step 2: Retrieve relevant products
            if intent in ["product_search", "pricing_query", "availability_check", "comparison"]:
                # Use semantic search with Pinecone
                pinecone_results = self.semantic_search(
                    user_query, 
                    top_k=10,
                    filters=filters
                )
                
                # Extract SKUs from Pinecone results
                skus = [match['id'] for match in pinecone_results]
                
                # Fetch complete data from MongoDB
                products = self.fetch_complete_product_data(skus)
                
                # If specific filters require MongoDB query, refine results
                mongo_query = self.generate_mongodb_query(filters)
                if mongo_query and skus:
                    self._log("🔍 Applying additional MongoDB filters...", level="info")
                    mongo_query["sku"] = {"$in": skus}
                    products = list(self.collection.find(mongo_query, {"_id": 0}).limit(10))
                    self._log(f"✅ Refined to {len(products)} products", level="info")
                
                # Format context with complete product data
                if products:
                    product_context = self.format_product_context(products, quantity)
                else:
                    product_context = "No matching products found."
                    self._log("⚠️ No products found matching the criteria", level="warning")
            else:
                self._log("ℹ️ General question - skipping product search", level="info")
                product_context = ""
            
            # Step 3: Generate response with Gemini
            self._log("\n" + "="*80, level="info")
            self._log("✍️ STEP 5: Response Generation (Gemini)", level="info")
            self._log("="*80, level="info")
            
            system_context = """You are a helpful product catalog assistant. 
Your role is to help users find glass bottles and jars, provide accurate pricing information, 
and answer questions about product specifications.

IMPORTANT RULES:
1. Always provide exact pricing from the context - never estimate or round
2. When discussing pricing, specify the quantity tier
3. If asked about bulk orders, show multiple pricing tiers
4. Always mention stock availability if relevant
5. Include SKU and company name when recommending products
6. If pricing data is not available, clearly state this
7. Provide product URLs when available

Be concise but comprehensive in your answers."""

            final_prompt = f"""{system_context}

User Query: {user_query}

Relevant Product Information:
{product_context}

Based on the above information, provide a helpful and accurate response to the user's query.
If the query is about pricing for a specific quantity, make sure to extract and present the exact price for that quantity.
"""
            
            self._log("🤖 Sending prompt to Gemini for response generation...", level="info")
            self._log(f"📏 Prompt size: {len(final_prompt)} characters", level="debug")
            
            start_time = datetime.now()
            response = self.llm.invoke(final_prompt)
            generation_time = (datetime.now() - start_time).total_seconds()
            
            self._log(f"✅ Response generated in {generation_time:.2f}s", level="info")
            self._log(f"📏 Response size: {len(response.content)} characters", level="info")
            
            # self._log("\n" + "✅ "*40, level="info")
            self._log("🎉 QUERY EXECUTION COMPLETE", level="info")
            # self._log("✅ "*40 + "\n", level="info")
            
            return response.content
            
        finally:
            # Restore original verbose setting
            if verbose_override is not None:
                self.set_verbose(original_verbose)


# Example usage
def main():
    # """
    # Example usage demonstrating verbose and non-verbose modes
    # """
    # print("=" * 100)
    # print("DEMO: RAG Chatbot with Verbose Mode")
    # print("=" * 100)
    
    # # Initialize chatbot with verbose mode enabled
    # print("\n1️⃣ Initializing chatbot with VERBOSE mode ON:")
    # print("-" * 100)
    # chatbot = HybridRAGChatbot(verbose=True)
    
    # # Example query with verbose output
    # print("\n2️⃣ Running query WITH verbose output:")
    # print("-" * 100)
    # query1 = "I need 500 units of 4 oz amber Boston round bottles. What's the price?"
    # response1 = chatbot.query(query1)
    # print("\n📤 FINAL RESPONSE:")
    # print("-" * 100)
    # print(response1)
    
    # # Turn off verbose mode
    # print("\n\n3️⃣ Turning verbose mode OFF:")
    # print("-" * 100)
    # chatbot.set_verbose(False)
    
    # # Example query without verbose output
    # print("\n4️⃣ Running query WITHOUT verbose output:")
    # print("-" * 100)
    # query2 = "Show me clear glass bottles between 200ml and 500ml in stock"
    # response2 = chatbot.query(query2)
    # print("\n📤 FINAL RESPONSE:")
    # print("-" * 100)
    # print(response2)
    
    # # Use verbose_override for a single query
    # print("\n\n5️⃣ Running query with temporary verbose OVERRIDE (verbose still OFF):")
    # print("-" * 100)
    # query3 = "What's the cheapest option for wine bottles?"
    # response3 = chatbot.query(query3, verbose_override=True)
    # print("\n📤 FINAL RESPONSE:")
    # print("-" * 100)
    # print(response3)
    
    # print("\n\n" + "=" * 100)
    # print("DEMO COMPLETE")
    # print("=" * 100)
    chatbot = HybridRAGChatbot(verbose=True)
    query1 = "Compare the Beverage market segment products by capacity and price."
    response1 = chatbot.query(query1)
    print("\n📤 FINAL RESPONSE:")
    print("-" * 100)
    print(response1)


if __name__ == "__main__":
    main()
