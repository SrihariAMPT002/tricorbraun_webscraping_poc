
# Create the enhanced chatbot code with improved query routing, logging, and guardrails

enhanced_code = '''import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from pinecone import Pinecone as PineconeClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
import json
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

load_dotenv()


class QueryType(Enum):
    """Types of queries that determine retrieval strategy"""
    SEMANTIC_SEARCH = "semantic_search"  # Requires vector search in Pinecone
    STRUCTURED_QUERY = "structured_query"  # Requires MongoDB filtering
    HYBRID = "hybrid"  # Requires both Pinecone + MongoDB
    OUT_OF_SCOPE = "out_of_scope"  # Not related to product data


@dataclass
class TimingMetrics:
    """Track timing for each operation"""
    operation: str
    start_time: float
    end_time: float
    duration: float
    details: Optional[Dict] = None
    
    def __str__(self):
        return f"{self.operation}: {self.duration:.3f}s"


@dataclass
class QueryLog:
    """Comprehensive log entry for each query"""
    timestamp: str
    user_query: str
    query_type: str
    intent: str
    retrieval_strategy: str
    timing_metrics: List[TimingMetrics]
    pinecone_query: Optional[Dict]
    mongodb_query: Optional[Dict]
    results_count: int
    response_length: int
    guardrail_checks: Dict[str, bool]
    total_time: float
    errors: List[str]


class ChatbotLogger:
    """Centralized logging system for the chatbot"""
    
    def __init__(self, verbose: bool = False, log_file: str = "chatbot_activity.log"):
        self.verbose = verbose
        self.log_file = log_file
        self.query_logs: List[QueryLog] = []
        self.timing_stack: List[TimingMetrics] = []
        
        # Setup file logger
        self.file_logger = logging.getLogger("ChatbotFileLogger")
        self.file_logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.file_logger.addHandler(fh)
        
        # Console logger
        self.console_logger = logging.getLogger("ChatbotConsole")
        self.console_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
        
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        ))
        self.console_logger.addHandler(ch)
    
    def start_timing(self, operation: str) -> float:
        """Start timing an operation"""
        start_time = time.time()
        if self.verbose:
            self.console_logger.info(f"⏱️  Starting: {operation}")
        return start_time
    
    def end_timing(self, operation: str, start_time: float, details: Optional[Dict] = None) -> TimingMetrics:
        """End timing and create metric"""
        end_time = time.time()
        duration = end_time - start_time
        
        metric = TimingMetrics(
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            details=details
        )
        
        self.timing_stack.append(metric)
        
        if self.verbose:
            self.console_logger.info(f"✅ Completed: {operation} in {duration:.3f}s")
            if details:
                self.console_logger.debug(f"   Details: {json.dumps(details, indent=2)}")
        
        # Log to file
        self.file_logger.info(f"TIMING | {operation} | {duration:.3f}s | {details or {}}")
        
        return metric
    
    def log_query(self, query_log: QueryLog):
        """Log complete query execution"""
        self.query_logs.append(query_log)
        
        # Write detailed log to file
        log_entry = {
            "timestamp": query_log.timestamp,
            "query": query_log.user_query,
            "type": query_log.query_type,
            "intent": query_log.intent,
            "strategy": query_log.retrieval_strategy,
            "timing": [str(t) for t in query_log.timing_metrics],
            "total_time": query_log.total_time,
            "results_count": query_log.results_count,
            "guardrail_passed": all(query_log.guardrail_checks.values()),
            "errors": query_log.errors
        }
        
        self.file_logger.info(f"QUERY_LOG | {json.dumps(log_entry)}")
        
        if self.verbose:
            self.console_logger.info("\\n" + "="*80)
            self.console_logger.info("📊 QUERY EXECUTION SUMMARY")
            self.console_logger.info("="*80)
            self.console_logger.info(f"Total Time: {query_log.total_time:.3f}s")
            self.console_logger.info(f"Results: {query_log.results_count}")
            self.console_logger.info(f"Guardrails: {'✅ PASSED' if all(query_log.guardrail_checks.values()) else '⚠️  FLAGGED'}")
            self.console_logger.info("\\nTiming Breakdown:")
            for metric in query_log.timing_metrics:
                self.console_logger.info(f"  • {metric}")
    
    def export_logs(self, filepath: str = "query_logs_export.json"):
        """Export all query logs to JSON"""
        with open(filepath, 'w') as f:
            json.dump([asdict(log) for log in self.query_logs], f, indent=2, default=str)
        self.file_logger.info(f"Exported {len(self.query_logs)} logs to {filepath}")


class QueryRouter:
    """Intelligent query routing system"""
    
    def __init__(self, llm: ChatGoogleGenerativeAI, logger: ChatbotLogger):
        self.llm = llm
        self.logger = logger
    
    def analyze_and_route(self, user_query: str) -> Tuple[QueryType, Dict[str, Any]]:
        """
        Analyze query and determine:
        1. Query type (semantic, structured, hybrid, out-of-scope)
        2. Extracted parameters
        3. Retrieval strategy
        """
        
        start_time = self.logger.start_timing("Query Analysis & Routing")
        
        analysis_prompt = f"""Analyze this user query and determine the appropriate retrieval strategy.

Query: "{user_query}"

Classify this query into ONE of these types:
1. SEMANTIC_SEARCH: User is describing products conceptually (e.g., "bottles for essential oils", "elegant wine bottles")
   → Requires vector similarity search in Pinecone

2. STRUCTURED_QUERY: User has specific filters/criteria (e.g., "500ml bottles under $2", "amber bottles from Berlin")
   → Requires MongoDB structured query

3. HYBRID: Query has both semantic description AND specific filters (e.g., "modern looking bottles in 750ml size")
   → Requires both Pinecone vector search + MongoDB filtering

4. OUT_OF_SCOPE: Query is not related to product search (e.g., "What's the weather?", "Tell me a joke")
   → Should be rejected with appropriate message

Return JSON with:
{{
  "query_type": "SEMANTIC_SEARCH" | "STRUCTURED_QUERY" | "HYBRID" | "OUT_OF_SCOPE",
  "reasoning": "Brief explanation of why this type was chosen",
  "intent": "product_search" | "pricing_query" | "availability_check" | "comparison" | "general_info" | "out_of_scope",
  "requires_pinecone": boolean,
  "requires_mongodb": boolean,
  "filters": {{
    "capacity": "value with unit",
    "capacity_range": {{"min": number, "max": number}},
    "color": "color name",
    "material": "material type",
    "shape": "shape description",
    "company": "company name",
    "price_range": {{"min": number, "max": number}},
    "stock_required": boolean
  }},
  "semantic_description": "Natural language description for vector search",
  "quantity": number or null,
  "is_data_related": boolean
}}

Return ONLY valid JSON, no markdown.
"""
        
        try:
            response = self.llm.invoke(analysis_prompt)
            analysis = json.loads(response.content.strip().strip('`').replace('json\\n', ''))
            
            query_type = QueryType[analysis.get("query_type", "HYBRID")]
            
            self.logger.end_timing("Query Analysis & Routing", start_time, {
                "query_type": query_type.value,
                "intent": analysis.get("intent"),
                "requires_pinecone": analysis.get("requires_pinecone"),
                "requires_mongodb": analysis.get("requires_mongodb")
            })
            
            return query_type, analysis
            
        except Exception as e:
            self.logger.console_logger.error(f"❌ Query analysis failed: {str(e)}")
            self.logger.end_timing("Query Analysis & Routing", start_time, {"error": str(e)})
            # Default to hybrid as fallback
            return QueryType.HYBRID, {
                "query_type": "HYBRID",
                "intent": "product_search",
                "requires_pinecone": True,
                "requires_mongodb": True,
                "filters": {},
                "is_data_related": True
            }


class GuardrailSystem:
    """Guardrails to ensure chatbot stays within scope"""
    
    def __init__(self, llm: ChatGoogleGenerativeAI, logger: ChatbotLogger):
        self.llm = llm
        self.logger = logger
    
    def check_query_scope(self, query: str, query_analysis: Dict) -> Tuple[bool, str]:
        """Check if query is within chatbot's domain"""
        
        if not query_analysis.get("is_data_related", True):
            return False, "I'm a product catalog assistant specialized in glass bottles and jars. I can only help with product searches, pricing, specifications, and availability. Please ask me about our product catalog."
        
        if query_analysis.get("query_type") == "OUT_OF_SCOPE":
            return False, "That question is outside my area of expertise. I can help you find glass bottles and jars, provide pricing information, check availability, and compare products. What would you like to know about our catalog?"
        
        return True, ""
    
    def validate_response(self, response: str, context: str) -> Tuple[bool, List[str]]:
        """Validate that response is grounded in provided context"""
        
        start_time = self.logger.start_timing("Response Validation")
        
        validation_prompt = f"""Check if this response is strictly based on the provided context.

CONTEXT:
{context[:2000]}...

RESPONSE:
{response}

Verify:
1. Are all product claims from the context?
2. Are all prices directly from the context?
3. Are there any fabricated details?
4. Is the response relevant to the data provided?

Return JSON:
{{
  "is_grounded": boolean,
  "issues": ["list of any fabrications or unsupported claims"],
  "confidence": "high" | "medium" | "low"
}}

Return ONLY valid JSON.
"""
        
        try:
            validation_response = self.llm.invoke(validation_prompt)
            validation = json.loads(validation_response.content.strip().strip('`').replace('json\\n', ''))
            
            is_valid = validation.get("is_grounded", True)
            issues = validation.get("issues", [])
            
            self.logger.end_timing("Response Validation", start_time, {
                "is_grounded": is_valid,
                "issues_count": len(issues)
            })
            
            return is_valid, issues
            
        except Exception as e:
            self.logger.console_logger.warning(f"⚠️  Response validation failed: {str(e)}")
            self.logger.end_timing("Response Validation", start_time, {"error": str(e)})
            return True, []  # Allow response on validation failure


class HybridRAGChatbot:
    """
    Enhanced Hybrid RAG Chatbot with:
    - Intelligent query routing
    - Comprehensive logging and timing
    - Guardrails for scope control
    """
    
    def __init__(self, verbose: bool = False, log_file: str = "chatbot_activity.log"):
        """Initialize chatbot with logging and guardrails"""
        
        # Initialize logger
        self.logger = ChatbotLogger(verbose=verbose, log_file=log_file)
        self.logger.console_logger.info("🚀 Initializing Enhanced Hybrid RAG Chatbot...")
        
        # Initialize MongoDB
        start_time = self.logger.start_timing("MongoDB Connection")
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI not found in environment variables")
        
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[os.getenv("MONGO_DB", "product_catalog")]
        self.collection = self.db[os.getenv("MONGO_COLLECTION", "processed_data")]
        self.logger.end_timing("MongoDB Connection", start_time)
        
        # Initialize Pinecone
        start_time = self.logger.start_timing("Pinecone Connection")
        pc = PineconeClient(api_key=os.getenv("PINECONE_API_KEY"))
        self.pinecone_index = pc.Index(os.getenv("PINECONE_INDEX", "processed-products-index"))
        self.logger.end_timing("Pinecone Connection", start_time)
        
        # Initialize embeddings and LLM
        start_time = self.logger.start_timing("Gemini Models Initialization")
        self.embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.1,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            convert_system_message_to_human=True
        )
        self.logger.end_timing("Gemini Models Initialization", start_time)
        
        # Initialize router and guardrails
        self.router = QueryRouter(self.llm, self.logger)
        self.guardrails = GuardrailSystem(self.llm, self.logger)
        
        self.logger.console_logger.info("✅ Chatbot initialization complete!\\n")
    
    def set_verbose(self, verbose: bool):
        """Toggle verbose mode"""
        self.logger.verbose = verbose
        self.logger.console_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    
    def semantic_search_pinecone(self, query: str, semantic_desc: str, top_k: int = 10, 
                                 filters: Dict = None) -> List[Dict]:
        """Perform semantic search using Pinecone"""
        
        start_time = self.logger.start_timing("Pinecone Vector Search")
        
        # Generate embedding
        embed_start = time.time()
        query_text = semantic_desc or query
        query_embedding = self.embeddings_model.embed_query(query_text)
        embed_time = time.time() - embed_start
        
        self.logger.file_logger.info(f"EMBEDDING | Generated in {embed_time:.3f}s | Dimension: {len(query_embedding)}")
        
        # Build Pinecone filters
        pinecone_filter = self._build_pinecone_filter(filters) if filters else {}
        
        # Query Pinecone
        search_params = {
            "vector": query_embedding,
            "top_k": top_k,
            "include_metadata": True
        }
        if pinecone_filter:
            search_params["filter"] = pinecone_filter
        
        search_start = time.time()
        results = self.pinecone_index.query(**search_params)
        search_time = time.time() - search_start
        
        matches = results.get('matches', [])
        
        self.logger.end_timing("Pinecone Vector Search", start_time, {
            "embedding_time": embed_time,
            "search_time": search_time,
            "results_count": len(matches),
            "filter_applied": bool(pinecone_filter)
        })
        
        return matches
    
    def _build_pinecone_filter(self, filters: Dict) -> Dict:
        """Build Pinecone metadata filter"""
        pinecone_filter = {}
        
        if filters.get("color"):
            pinecone_filter["color"] = {"$eq": filters["color"]}
        if filters.get("material"):
            pinecone_filter["material"] = {"$eq": filters["material"]}
        if filters.get("company"):
            pinecone_filter["company"] = {"$eq": filters["company"]}
        if filters.get("stock_required"):
            pinecone_filter["in_stock"] = True
        
        return pinecone_filter
    
    def structured_query_mongodb(self, filters: Dict, limit: int = 10) -> List[Dict]:
        """Perform structured query in MongoDB"""
        
        start_time = self.logger.start_timing("MongoDB Structured Query")
        
        mongo_query = self._build_mongodb_query(filters)
        
        query_start = time.time()
        products = list(self.collection.find(mongo_query, {"_id": 0}).limit(limit))
        query_time = time.time() - query_start
        
        self.logger.end_timing("MongoDB Structured Query", start_time, {
            "query_time": query_time,
            "results_count": len(products),
            "query": mongo_query
        })
        
        return products
    
    def _build_mongodb_query(self, filters: Dict) -> Dict:
        """Build MongoDB query from filters"""
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
            mongo_query["normalised_capacity_ml"] = {}
            if cap_range.get("min"):
                mongo_query["normalised_capacity_ml"]["$gte"] = cap_range["min"]
            if cap_range.get("max"):
                mongo_query["normalised_capacity_ml"]["$lte"] = cap_range["max"]
        
        if filters.get("price_range"):
            price_range = filters["price_range"]
            mongo_query["avg_price_per_unit"] = {}
            if price_range.get("min"):
                mongo_query["avg_price_per_unit"]["$gte"] = price_range["min"]
            if price_range.get("max"):
                mongo_query["avg_price_per_unit"]["$lte"] = price_range["max"]
        
        if filters.get("stock_required"):
            mongo_query["stock"] = {"$regex": "In Stock", "$options": "i"}
        
        return mongo_query
    
    def fetch_complete_data_mongodb(self, skus: List[str]) -> List[Dict]:
        """Fetch complete product data from MongoDB by SKUs"""
        
        start_time = self.logger.start_timing("MongoDB Data Retrieval")
        
        products = list(self.collection.find(
            {"sku": {"$in": skus}},
            {"_id": 0}
        ))
        
        self.logger.end_timing("MongoDB Data Retrieval", start_time, {
            "skus_requested": len(skus),
            "products_found": len(products)
        })
        
        return products
    
    def format_product_context(self, products: List[Dict], quantity: int = None) -> str:
        """Format products for LLM context"""
        
        start_time = self.logger.start_timing("Context Formatting")
        
        context_parts = []
        for i, product in enumerate(products[:10], 1):  # Limit to top 10
            context = f"\\n--- Product {i} ---\\n"
            context += f"Name: {product.get('name', 'N/A')}\\n"
            context += f"SKU: {product.get('sku', 'N/A')}\\n"
            context += f"Company: {product.get('company', 'N/A')}\\n"
            context += f"Capacity: {product.get('original_capacity', 'N/A')} {product.get('original_uom', '')}\\n"
            context += f"Color: {product.get('color', 'N/A')}\\n"
            context += f"Material: {product.get('material', 'N/A')}\\n"
            context += f"Shape: {product.get('shape', 'N/A')}\\n"
            context += f"Stock: {product.get('stock', 'N/A')}\\n"
            
            # Pricing
            quantity_breaks = product.get('quantity_breaks', [])
            if quantity_breaks:
                context += "\\nPricing:\\n"
                for tier in quantity_breaks[:5]:  # Limit tiers
                    qty = tier.get('quantity_of_packing', 'N/A')
                    price = tier.get('price_per_item', 'N/A')
                    context += f"  - {qty}+ units: ${price}\\n"
            
            context += f"URL: {product.get('url', 'N/A')}\\n"
            context_parts.append(context)
        
        formatted_context = "\\n".join(context_parts)
        
        self.logger.end_timing("Context Formatting", start_time, {
            "products_formatted": len(context_parts),
            "context_length": len(formatted_context)
        })
        
        return formatted_context
    
    def generate_response(self, user_query: str, product_context: str, intent: str) -> str:
        """Generate response with LLM"""
        
        start_time = self.logger.start_timing("Response Generation")
        
        system_context = """You are a product catalog assistant for glass bottles and jars.

STRICT RULES:
1. ONLY use information from the provided product context
2. Never fabricate or estimate data
3. If information is not in context, explicitly state "This information is not available"
4. Always cite specific product names, SKUs, and prices exactly as provided
5. Stay within the domain of product catalog assistance
6. For pricing, always specify the quantity tier
7. Include stock status when relevant

Be helpful, accurate, and concise."""

        final_prompt = f"""{system_context}

User Query: {user_query}

Product Information:
{product_context}

Provide an accurate response based ONLY on the above product information."""

        response = self.llm.invoke(final_prompt)
        
        self.logger.end_timing("Response Generation", start_time, {
            "prompt_length": len(final_prompt),
            "response_length": len(response.content)
        })
        
        return response.content
    
    def query(self, user_query: str) -> str:
        """Main query method with full pipeline"""
        
        query_start_time = time.time()
        errors = []
        
        try:
            if self.logger.verbose:
                self.logger.console_logger.info("\\n" + "="*80)
                self.logger.console_logger.info(f"🔍 NEW QUERY: {user_query}")
                self.logger.console_logger.info("="*80)
            
            # Step 1: Route query
            query_type, analysis = self.router.analyze_and_route(user_query)
            
            # Step 2: Guardrail check
            is_valid, rejection_msg = self.guardrails.check_query_scope(user_query, analysis)
            
            guardrail_checks = {
                "scope_check": is_valid,
                "response_validation": True  # Will update later
            }
            
            if not is_valid:
                # Query out of scope
                query_log = QueryLog(
                    timestamp=datetime.now().isoformat(),
                    user_query=user_query,
                    query_type=query_type.value,
                    intent=analysis.get("intent", "out_of_scope"),
                    retrieval_strategy="none",
                    timing_metrics=self.logger.timing_stack.copy(),
                    pinecone_query=None,
                    mongodb_query=None,
                    results_count=0,
                    response_length=len(rejection_msg),
                    guardrail_checks=guardrail_checks,
                    total_time=time.time() - query_start_time,
                    errors=[]
                )
                
                self.logger.log_query(query_log)
                self.logger.timing_stack.clear()
                
                return rejection_msg
            
            # Step 3: Retrieve data based on query type
            products = []
            pinecone_query = None
            mongodb_query = None
            
            filters = analysis.get("filters", {})
            semantic_desc = analysis.get("semantic_description", "")
            
            if query_type == QueryType.SEMANTIC_SEARCH or query_type == QueryType.HYBRID:
                # Use Pinecone
                matches = self.semantic_search_pinecone(
                    user_query, 
                    semantic_desc,
                    top_k=10,
                    filters=filters if query_type == QueryType.HYBRID else None
                )
                
                skus = [m['id'] for m in matches]
                products = self.fetch_complete_data_mongodb(skus)
                
                pinecone_query = {"semantic_desc": semantic_desc, "filters": filters}
            
            if query_type == QueryType.STRUCTURED_QUERY:
                # Use MongoDB only
                products = self.structured_query_mongodb(filters, limit=10)
                mongodb_query = self._build_mongodb_query(filters)
            
            # Step 4: Format context
            product_context = self.format_product_context(
                products, 
                quantity=analysis.get("quantity")
            ) if products else "No matching products found in the catalog."
            
            # Step 5: Generate response
            response = self.generate_response(
                user_query, 
                product_context,
                analysis.get("intent", "general")
            )
            
            # Step 6: Validate response
            is_grounded, issues = self.guardrails.validate_response(response, product_context)
            guardrail_checks["response_validation"] = is_grounded
            
            if issues:
                errors.extend(issues)
            
            # Create query log
            query_log = QueryLog(
                timestamp=datetime.now().isoformat(),
                user_query=user_query,
                query_type=query_type.value,
                intent=analysis.get("intent", "unknown"),
                retrieval_strategy=f"Pinecone: {analysis.get('requires_pinecone', False)}, MongoDB: {analysis.get('requires_mongodb', False)}",
                timing_metrics=self.logger.timing_stack.copy(),
                pinecone_query=pinecone_query,
                mongodb_query=mongodb_query,
                results_count=len(products),
                response_length=len(response),
                guardrail_checks=guardrail_checks,
                total_time=time.time() - query_start_time,
                errors=errors
            )
            
            self.logger.log_query(query_log)
            self.logger.timing_stack.clear()
            
            return response
            
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            self.logger.console_logger.error(f"❌ {error_msg}")
            
            # Log error
            query_log = QueryLog(
                timestamp=datetime.now().isoformat(),
                user_query=user_query,
                query_type="error",
                intent="error",
                retrieval_strategy="none",
                timing_metrics=self.logger.timing_stack.copy(),
                pinecone_query=None,
                mongodb_query=None,
                results_count=0,
                response_length=0,
                guardrail_checks={"scope_check": False, "response_validation": False},
                total_time=time.time() - query_start_time,
                errors=[error_msg]
            )
            
            self.logger.log_query(query_log)
            self.logger.timing_stack.clear()
            
            return "I apologize, but I encountered an error processing your request. Please try rephrasing your question."
    
    def export_logs(self, filepath: str = "query_logs_export.json"):
        """Export all query logs"""
        self.logger.export_logs(filepath)


# Example usage
def main():
    print("="*100)
    print("ENHANCED CHATBOT WITH QUERY ROUTING, LOGGING & GUARDRAILS")
    print("="*100)
    
    # Initialize with verbose mode
    chatbot = HybridRAGChatbot(verbose=True, log_file="chatbot_activity.log")
    
    # Test queries
    test_queries = [
        "I need amber bottles for essential oils around 30ml",  # Semantic
        "Show me bottles between 500ml and 1000ml under $5",   # Structured
        "Modern looking wine bottles in 750ml size",            # Hybrid
        "What's the weather today?",                            # Out of scope
    ]
    
    for query in test_queries:
        print(f"\\n{'='*100}")
        print(f"Query: {query}")
        print('='*100)
        
        response = chatbot.query(query)
        
        print("\\n📤 RESPONSE:")
        print("-"*100)
        print(response)
        print("\\n")
    
    # Export logs
    chatbot.export_logs("query_logs.json")
    print("\\n✅ Logs exported to query_logs.json")

if __name__ == "__main__":
    main()
'''

# Write to file
with open('enhanced_chatbot.py', 'w') as f:
    f.write(enhanced_code)

print("✅ Enhanced chatbot code created successfully!")
print("\nKey improvements:")
print("1. ✅ Query routing system that identifies if query needs Pinecone, MongoDB, or both")
print("2. ✅ Comprehensive logging system with timing metrics for each operation")
print("3. ✅ Guardrails to keep chatbot strictly within data scope")
print("4. ✅ Detailed activity logs saved to file when verbose=True")
print("5. ✅ Network timing tracked for: embedding, Pinecone search, MongoDB queries")
print("\nFile created: enhanced_chatbot.py")
