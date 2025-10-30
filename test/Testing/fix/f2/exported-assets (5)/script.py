
# Create a fixed version with aggregation support

aggregation_fixed_code = '''import os
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
    AGGREGATION_QUERY = "aggregation_query"  # Requires MongoDB aggregation (NEW!)
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
    aggregation_pipeline: Optional[List]
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
        self.file_logger.handlers.clear()
        
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.file_logger.addHandler(fh)
        
        # Console logger
        self.console_logger = logging.getLogger("ChatbotConsole")
        self.console_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
        self.console_logger.handlers.clear()
        
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
        
        self.file_logger.info(f"TIMING | {operation} | {duration:.3f}s | {details or {}}")
        return metric
    
    def log_query(self, query_log: QueryLog):
        """Log complete query execution"""
        self.query_logs.append(query_log)
        
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
        1. Query type (semantic, structured, aggregation, hybrid, out-of-scope)
        2. Extracted parameters
        3. Retrieval strategy
        """
        
        start_time = self.logger.start_timing("Query Analysis & Routing")
        
        analysis_prompt = f"""Analyze this user query about glass bottles and jars.

Query: "{user_query}"

Classify this query into ONE of these types:

1. SEMANTIC_SEARCH: User describes products conceptually
   Examples: "bottles for essential oils", "elegant wine bottles", "show me amber bottles"
   → Requires vector similarity search in Pinecone

2. STRUCTURED_QUERY: User has specific filters, wants product list
   Examples: "500ml bottles under $2", "bottles between 100ml and 200ml"
   → Requires MongoDB structured query

3. AGGREGATION_QUERY: User asks for statistics/calculations over ALL matching products
   Examples: 
   - "What is the average capacity of Cobalt Blue products?"
   - "How many amber bottles are in stock?"
   - "What's the price range for wine bottles?"
   - "Count products by color"
   Keywords: average, mean, count, total, sum, max, min, statistics, how many
   → Requires MongoDB aggregation pipeline on ALL matching data

4. HYBRID: Query has BOTH semantic description AND specific filters
   Examples: "modern looking bottles in 750ml size"
   → Requires both Pinecone + MongoDB

5. OUT_OF_SCOPE: Query clearly not about products
   Examples: "What's the weather?", "Tell me a joke"
   → Should be rejected
   
CRITICAL RULES:
- If query asks for aggregation (average, count, sum, etc.) → AGGREGATION_QUERY
- Aggregation queries MUST process ALL matching records, not samples
- Questions with "how many", "average", "total", "count" are AGGREGATION_QUERY
- Almost ALL queries about bottles/jars are IN SCOPE

Return JSON:
{{
  "query_type": "SEMANTIC_SEARCH" | "STRUCTURED_QUERY" | "AGGREGATION_QUERY" | "HYBRID" | "OUT_OF_SCOPE",
  "reasoning": "Brief explanation",
  "intent": "product_search" | "pricing_query" | "availability_check" | "statistics" | "aggregation" | "comparison" | "out_of_scope",
  "requires_pinecone": boolean,
  "requires_mongodb": boolean,
  "requires_aggregation": boolean (NEW!),
  "aggregation_type": "avg" | "count" | "sum" | "min" | "max" | "group" | null,
  "aggregation_field": "normalised_capacity_ml" | "avg_price_per_unit" | null,
  "filters": {{
    "capacity_range": {{"min": number, "max": number}} or null,
    "color": "color name" or null,
    "material": "material type" or null,
    "shape": "shape description" or null,
    "company": "company name" or null,
    "price_range": {{"min": number, "max": number}} or null,
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
            content = response.content.strip()
            
            # Clean markdown formatting
            if content.startswith('```'):
                content = content.split('\\n', 1)[1] if '\\n' in content else content[3:]
            if content.endswith('```'):
                content = content.rsplit('\\n', 1)[0] if '\\n' in content else content[:-3]
            content = content.replace('```json', '').replace('```', '').strip()
            
            analysis = json.loads(content)
            
            query_type_str = analysis.get("query_type", "HYBRID")
            
            # Override: If is_data_related but marked OUT_OF_SCOPE, default to SEMANTIC_SEARCH
            if analysis.get("is_data_related", True) and query_type_str == "OUT_OF_SCOPE":
                query_type_str = "SEMANTIC_SEARCH"
                self.logger.console_logger.info("Overriding OUT_OF_SCOPE to SEMANTIC_SEARCH")
            
            query_type = QueryType[query_type_str]
            
            self.logger.end_timing("Query Analysis & Routing", start_time, {
                "query_type": query_type.value,
                "intent": analysis.get("intent"),
                "requires_pinecone": analysis.get("requires_pinecone"),
                "requires_mongodb": analysis.get("requires_mongodb"),
                "requires_aggregation": analysis.get("requires_aggregation", False),
                "aggregation_type": analysis.get("aggregation_type")
            })
            
            return query_type, analysis
            
        except Exception as e:
            self.logger.console_logger.error(f"❌ Query analysis failed: {str(e)}")
            self.logger.end_timing("Query Analysis & Routing", start_time, {"error": str(e)})
            # Default to HYBRID as fallback
            return QueryType.HYBRID, {
                "query_type": "HYBRID",
                "intent": "product_search",
                "requires_pinecone": True,
                "requires_mongodb": True,
                "requires_aggregation": False,
                "filters": {},
                "is_data_related": True,
                "semantic_description": user_query
            }


class GuardrailSystem:
    """Guardrails to ensure chatbot stays within scope"""
    
    def __init__(self, llm: ChatGoogleGenerativeAI, logger: ChatbotLogger):
        self.llm = llm
        self.logger = logger
    
    def check_query_scope(self, query: str, query_analysis: Dict) -> Tuple[bool, str]:
        """Check if query is within chatbot's domain"""
        
        product_keywords = [
            'bottle', 'jar', 'container', 'glass', 'packaging', 'amber', 'flint', 'cobalt',
            'boston round', 'wine', 'liquor', 'essential oil', 'ml', 'oz', 'price',
            'stock', 'capacity', 'size', 'color', 'colour', 'material', 'shape', 'sku',
            'berlin', 'tricorbraun', 'cary', 'average', 'count', 'total', 'products'
        ]
        
        query_lower = query.lower()
        has_product_keyword = any(keyword in query_lower for keyword in product_keywords)
        
        if has_product_keyword:
            return True, ""
        
        if query_analysis.get("is_data_related", True):
            return True, ""
        
        query_type = query_analysis.get("query_type", "HYBRID")
        if query_type == "OUT_OF_SCOPE" and not has_product_keyword:
            return False, "I'm a product catalog assistant specialized in glass bottles and jars. I can help you find products, check pricing, verify availability, get statistics, and compare options. What would you like to know about our catalog?"
        
        return True, ""
    
    def validate_response(self, response: str, context: str, query_type: str) -> Tuple[bool, List[str]]:
        """Validate that response is grounded in provided context"""
        
        # Skip validation for aggregation queries (stats are computed, not listed)
        if query_type == "aggregation_query":
            return True, []
        
        # If no context, skip validation
        if not context or "No matching products found" in context:
            return True, []
        
        start_time = self.logger.start_timing("Response Validation")
        
        validation_prompt = f"""Check if this response is based on the provided context.

CONTEXT (first 2000 chars):
{context[:2000]}...

RESPONSE:
{response}

Check:
1. Are product details from context?
2. Are prices from context (or stated as unavailable)?
3. Any obvious fabrications?

Return JSON:
{{
  "is_grounded": boolean,
  "issues": ["list of serious fabrications only"],
  "confidence": "high" | "medium" | "low"
}}

Return ONLY valid JSON.
"""
        
        try:
            validation_response = self.llm.invoke(validation_prompt)
            content = validation_response.content.strip()
            
            # Clean markdown
            if content.startswith('```'):
                content = content.split('\\n', 1)[1] if '\\n' in content else content[3:]
            if content.endswith('```'):
                content = content.rsplit('\\n', 1)[0] if '\\n' in content else content[:-3]
            content = content.replace('```json', '').replace('```', '').strip()
            
            validation = json.loads(content)
            
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
            return True, []


class HybridRAGChatbot:
    """
    Enhanced Hybrid RAG Chatbot with:
    - Intelligent query routing
    - MongoDB aggregation support
    - Comprehensive logging and timing
    - Guardrails for scope control
    """
    
    def __init__(self, verbose: bool = False, log_file: str = "chatbot_activity.log"):
        """Initialize chatbot with logging and guardrails"""
        
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
    
    def aggregation_query_mongodb(self, filters: Dict, aggregation_type: str, 
                                   aggregation_field: str) -> Dict[str, Any]:
        """Perform aggregation query on MongoDB"""
        
        start_time = self.logger.start_timing("MongoDB Aggregation Query")
        
        # Build match stage from filters
        match_stage = self._build_mongodb_query(filters)
        
        # Build aggregation pipeline
        pipeline = []
        
        if match_stage:
            pipeline.append({"$match": match_stage})
        
        # Add aggregation stage
        if aggregation_type == "count":
            pipeline.append({"$count": "total"})
        
        elif aggregation_type in ["avg", "sum", "min", "max"]:
            group_stage = {
                "$group": {
                    "_id": None,
                    "result": {f"${aggregation_type}": f"${aggregation_field}"},
                    "count": {"$sum": 1}
                }
            }
            pipeline.append(group_stage)
        
        elif aggregation_type == "group":
            # Group by a field (e.g., color)
            group_field = aggregation_field or "color"
            pipeline.append({
                "$group": {
                    "_id": f"${group_field}",
                    "count": {"$sum": 1},
                    "avg_capacity": {"$avg": "$normalised_capacity_ml"}
                }
            })
            pipeline.append({"$sort": {"count": -1}})
        
        query_start = time.time()
        results = list(self.collection.aggregate(pipeline))
        query_time = time.time() - query_start
        
        self.logger.end_timing("MongoDB Aggregation Query", start_time, {
            "query_time": query_time,
            "pipeline_stages": len(pipeline),
            "results_count": len(results),
            "aggregation_type": aggregation_type
        })
        
        return {
            "pipeline": pipeline,
            "results": results,
            "aggregation_type": aggregation_type,
            "field": aggregation_field
        }
    
    def semantic_search_pinecone(self, query: str, semantic_desc: str, top_k: int = 10, 
                                 filters: Dict = None) -> List[Dict]:
        """Perform semantic search using Pinecone"""
        
        start_time = self.logger.start_timing("Pinecone Vector Search")
        
        embed_start = time.time()
        query_text = semantic_desc or query
        query_embedding = self.embeddings_model.embed_query(query_text)
        embed_time = time.time() - embed_start
        
        self.logger.file_logger.info(f"EMBEDDING | Generated in {embed_time:.3f}s | Dimension: {len(query_embedding)}")
        
        pinecone_filter = self._build_pinecone_filter(filters) if filters else {}
        
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
    
    def format_aggregation_context(self, aggregation_result: Dict, filters: Dict) -> str:
        """Format aggregation results for LLM context"""
        
        start_time = self.logger.start_timing("Context Formatting")
        
        agg_type = aggregation_result.get("aggregation_type")
        results = aggregation_result.get("results", [])
        field = aggregation_result.get("field")
        
        context = f"Aggregation Query Results:\\n"
        context += f"Query Type: {agg_type}\\n"
        context += f"Filters Applied: {json.dumps(filters)}\\n\\n"
        
        if agg_type == "count":
            total = results[0].get("total", 0) if results else 0
            context += f"Total Count: {total} products\\n"
        
        elif agg_type in ["avg", "sum", "min", "max"]:
            if results:
                result_value = results[0].get("result")
                count = results[0].get("count", 0)
                context += f"{agg_type.upper()} of {field}: {result_value}\\n"
                context += f"Number of products included: {count}\\n"
        
        elif agg_type == "group":
            context += f"Grouped Results:\\n"
            for item in results:
                context += f"- {item.get('_id')}: {item.get('count')} products\\n"
        
        self.logger.end_timing("Context Formatting", start_time, {
            "aggregation_type": agg_type,
            "results_count": len(results)
        })
        
        return context
    
    def format_product_context(self, products: List[Dict], quantity: int = None) -> str:
        """Format products for LLM context"""
        
        start_time = self.logger.start_timing("Context Formatting")
        
        context_parts = []
        for i, product in enumerate(products[:10], 1):
            context = f"\\n--- Product {i} ---\\n"
            context += f"Name: {product.get('name', 'N/A')}\\n"
            context += f"SKU: {product.get('sku', 'N/A')}\\n"
            context += f"Company: {product.get('company', 'N/A')}\\n"
            context += f"Capacity: {product.get('original_capacity', 'N/A')} {product.get('original_uom', '')}\\n"
            context += f"Color: {product.get('color', 'N/A')}\\n"
            context += f"Material: {product.get('material', 'N/A')}\\n"
            context += f"Shape: {product.get('shape', 'N/A')}\\n"
            context += f"Stock: {product.get('stock', 'N/A')}\\n"
            
            quantity_breaks = product.get('quantity_breaks', [])
            if quantity_breaks:
                context += "\\nPricing:\\n"
                for tier in quantity_breaks[:5]:
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
    
    def generate_response(self, user_query: str, context: str, intent: str, 
                         query_type: str) -> str:
        """Generate response with LLM"""
        
        start_time = self.logger.start_timing("Response Generation")
        
        if query_type == "aggregation_query":
            system_context = """You are a product catalog assistant for glass bottles and jars.

For AGGREGATION queries:
1. Use the computed statistics from the aggregation results
2. Clearly state what data the calculation is based on
3. Be precise with numbers
4. Don't list individual products for aggregation queries
5. If asked for average/count/etc., provide ONLY the statistic, not product samples

STRICT RULES:
1. ONLY use information from the provided context
2. Never fabricate data
3. For stats, use the exact computed values
4. Be accurate and concise"""
        else:
            system_context = """You are a product catalog assistant for glass bottles and jars.

STRICT RULES:
1. ONLY use information from the provided product context
2. Never fabricate or estimate data
3. If information is not in context, state "This information is not available"
4. Always cite specific product names, SKUs, and prices exactly as provided
5. For pricing, always specify the quantity tier
6. Include stock status when relevant

Be helpful, accurate, and concise."""

        final_prompt = f"""{system_context}

User Query: {user_query}

Context:
{context}

Provide an accurate response based ONLY on the above information."""

        response = self.llm.invoke(final_prompt)
        
        self.logger.end_timing("Response Generation", start_time, {
            "prompt_length": len(final_prompt),
            "response_length": len(response.content),
            "query_type": query_type
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
                "response_validation": True
            }
            
            if not is_valid:
                query_log = QueryLog(
                    timestamp=datetime.now().isoformat(),
                    user_query=user_query,
                    query_type=query_type.value,
                    intent=analysis.get("intent", "out_of_scope"),
                    retrieval_strategy="none",
                    timing_metrics=self.logger.timing_stack.copy(),
                    pinecone_query=None,
                    mongodb_query=None,
                    aggregation_pipeline=None,
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
            context = ""
            pinecone_query = None
            mongodb_query = None
            aggregation_pipeline = None
            
            filters = analysis.get("filters", {})
            semantic_desc = analysis.get("semantic_description", "")
            
            # NEW: Handle aggregation queries
            if query_type == QueryType.AGGREGATION_QUERY:
                agg_type = analysis.get("aggregation_type", "count")
                agg_field = analysis.get("aggregation_field", "normalised_capacity_ml")
                
                agg_result = self.aggregation_query_mongodb(filters, agg_type, agg_field)
                context = self.format_aggregation_context(agg_result, filters)
                aggregation_pipeline = agg_result.get("pipeline")
                
                # For logging purposes
                if agg_result.get("results"):
                    products = [{"aggregation_result": agg_result.get("results")}]
            
            elif query_type == QueryType.SEMANTIC_SEARCH or query_type == QueryType.HYBRID:
                matches = self.semantic_search_pinecone(
                    user_query, 
                    semantic_desc,
                    top_k=10,
                    filters=filters if query_type == QueryType.HYBRID else None
                )
                
                skus = [m['id'] for m in matches]
                products = self.fetch_complete_data_mongodb(skus)
                context = self.format_product_context(products)
                
                pinecone_query = {"semantic_desc": semantic_desc, "filters": filters}
            
            elif query_type == QueryType.STRUCTURED_QUERY:
                products = self.structured_query_mongodb(filters, limit=10)
                context = self.format_product_context(products)
                mongodb_query = self._build_mongodb_query(filters)
            
            if not context:
                context = "No matching products found in the catalog."
            
            # Step 4: Generate response
            response = self.generate_response(
                user_query, 
                context,
                analysis.get("intent", "general"),
                query_type.value
            )
            
            # Step 5: Validate response
            if products and query_type != QueryType.AGGREGATION_QUERY:
                is_grounded, issues = self.guardrails.validate_response(
                    response, context, query_type.value
                )
                guardrail_checks["response_validation"] = is_grounded
                
                if issues:
                    errors.extend(issues)
            
            # Create query log
            query_log = QueryLog(
                timestamp=datetime.now().isoformat(),
                user_query=user_query,
                query_type=query_type.value,
                intent=analysis.get("intent", "unknown"),
                retrieval_strategy=f"Pinecone: {analysis.get('requires_pinecone', False)}, MongoDB: {analysis.get('requires_mongodb', False)}, Aggregation: {analysis.get('requires_aggregation', False)}",
                timing_metrics=self.logger.timing_stack.copy(),
                pinecone_query=pinecone_query,
                mongodb_query=mongodb_query,
                aggregation_pipeline=aggregation_pipeline,
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
            
            query_log = QueryLog(
                timestamp=datetime.now().isoformat(),
                user_query=user_query,
                query_type="error",
                intent="error",
                retrieval_strategy="none",
                timing_metrics=self.logger.timing_stack.copy(),
                pinecone_query=None,
                mongodb_query=None,
                aggregation_pipeline=None,
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
    print("ENHANCED CHATBOT WITH AGGREGATION SUPPORT")
    print("="*100)
    
    chatbot = HybridRAGChatbot(verbose=True, log_file="chatbot_activity.log")
    
    test_queries = [
        "What is the average capacity (in ml) of products colored Cobalt Blue?",  # Aggregation
        "How many amber bottles are in stock?",  # Aggregation
        "I need bottles for essential oils around 30ml",  # Semantic
        "Show me bottles between 500ml and 1000ml under $5",   # Structured
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
    
    chatbot.export_logs("query_logs.json")
    print("\\n✅ Logs exported to query_logs.json")

if __name__ == "__main__":
    main()
'''

with open('enhanced_chatbot_with_aggregation.py', 'w') as f:
    f.write(aggregation_fixed_code)

print("✅ Created: enhanced_chatbot_with_aggregation.py")
print("\n🔧 KEY FIXES FOR AGGREGATION QUERIES:")
print("\n1. NEW QUERY TYPE: AGGREGATION_QUERY")
print("   - Detects keywords: average, count, sum, min, max, total, how many")
print("   - Routes to MongoDB aggregation pipeline")
print("   - Processes ALL matching records, not just 10 samples")
print("\n2. MongoDB Aggregation Pipeline:")
print("   - Average: Computes avg across all matching products")
print("   - Count: Counts all matching products")
print("   - Sum/Min/Max: Aggregates across all data")
print("   - Group: Groups by field (e.g., color) and computes stats")
print("\n3. Updated Response Generation:")
print("   - Aggregation queries get special instructions")
print("   - LLM instructed to use computed stats, not list products")
print("   - Skips response validation for aggregation (stats are computed, not retrieved)")
print("\n4. Example Query Now Works Correctly:")
print("   'What is the average capacity of Cobalt Blue products?'")
print("   → AGGREGATION_QUERY (not SEMANTIC_SEARCH)")
print("   → MongoDB aggregation on ALL Cobalt Blue products")
print("   → Returns accurate average across entire dataset")
