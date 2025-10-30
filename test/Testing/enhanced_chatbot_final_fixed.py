import os
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
    SEMANTIC_SEARCH = "semantic_search"
    STRUCTURED_QUERY = "structured_query"
    AGGREGATION_QUERY = "aggregation_query"
    HYBRID = "hybrid"
    OUT_OF_SCOPE = "out_of_scope"


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

        self.file_logger = logging.getLogger("ChatbotFileLogger")
        self.file_logger.setLevel(logging.INFO)
        self.file_logger.handlers.clear()

        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.file_logger.addHandler(fh)

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
        start_time = time.time()
        if self.verbose:
            self.console_logger.info(f"⏱️  Starting: {operation}")
        return start_time

    def end_timing(self, operation: str, start_time: float, details: Optional[Dict] = None) -> TimingMetrics:
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
            self.console_logger.info("\n" + "="*80)
            self.console_logger.info("📊 QUERY EXECUTION SUMMARY")
            self.console_logger.info("="*80)
            self.console_logger.info(f"Total Time: {query_log.total_time:.3f}s")
            self.console_logger.info(f"Results: {query_log.results_count}")
            self.console_logger.info(f"Guardrails: {'✅ PASSED' if all(query_log.guardrail_checks.values()) else '⚠️  FLAGGED'}")

    def export_logs(self, filepath: str = "query_logs_export.json"):
        with open(filepath, 'w') as f:
            json.dump([asdict(log) for log in self.query_logs], f, indent=2, default=str)
        self.file_logger.info(f"Exported {len(self.query_logs)} logs to {filepath}")


class QueryRouter:
    """Intelligent query routing system"""

    def __init__(self, llm: ChatGoogleGenerativeAI, logger: ChatbotLogger):
        self.llm = llm
        self.logger = logger

    def analyze_and_route(self, user_query: str) -> Tuple[QueryType, Dict[str, Any]]:
        start_time = self.logger.start_timing("Query Analysis & Routing")

        analysis_prompt = f"""Analyze this user query about glass bottles and jars.

Query: "{user_query}"

Classify into ONE type:

1. SEMANTIC_SEARCH: Conceptual product description
   Examples: "bottles for essential oils", "elegant wine bottles"

2. STRUCTURED_QUERY: Specific filters, wants product list
   Examples: "500ml bottles under $2"

3. AGGREGATION_QUERY: Statistics/calculations over ALL matching products
   Examples: "average capacity of Cobalt Blue products", "how many amber bottles"
   Keywords: average, mean, count, total, sum, max, min, statistics

4. HYBRID: Semantic + filters
   Examples: "modern bottles in 750ml"

5. OUT_OF_SCOPE: Not about products

CRITICAL: Aggregation queries MUST process ALL matching records.

Return JSON:
{{
  "query_type": "SEMANTIC_SEARCH" | "STRUCTURED_QUERY" | "AGGREGATION_QUERY" | "HYBRID" | "OUT_OF_SCOPE",
  "reasoning": "Brief explanation",
  "intent": "product_search" | "pricing_query" | "availability_check" | "statistics" | "aggregation" | "out_of_scope",
  "requires_pinecone": boolean,
  "requires_mongodb": boolean,
  "requires_aggregation": boolean,
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
  "semantic_description": "description",
  "quantity": number or null,
  "is_data_related": boolean
}}

Return ONLY valid JSON.
"""

        try:
            response = self.llm.invoke(analysis_prompt)
            content = response.content.strip()

            # Clean markdown
            if content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content[3:]
            if content.endswith('```'):
                content = content.rsplit('\n', 1)[0] if '\n' in content else content[:-3]
            content = content.replace('```json', '').replace('```', '').strip()

            analysis = json.loads(content)
            query_type_str = analysis.get("query_type", "HYBRID")

            # Override: data-related but OUT_OF_SCOPE -> SEMANTIC_SEARCH
            if analysis.get("is_data_related", True) and query_type_str == "OUT_OF_SCOPE":
                query_type_str = "SEMANTIC_SEARCH"

            query_type = QueryType[query_type_str]

            self.logger.end_timing("Query Analysis & Routing", start_time, {
                "query_type": query_type.value,
                "intent": analysis.get("intent"),
                "requires_aggregation": analysis.get("requires_aggregation", False)
            })

            return query_type, analysis

        except Exception as e:
            self.logger.console_logger.error(f"❌ Query analysis failed: {str(e)}")
            self.logger.end_timing("Query Analysis & Routing", start_time, {"error": str(e)})
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
        product_keywords = [
            'bottle', 'jar', 'container', 'glass', 'packaging', 'amber', 'flint', 'cobalt',
            'boston round', 'wine', 'liquor', 'ml', 'oz', 'price', 'capacity', 'average', 'count'
        ]

        query_lower = query.lower()
        has_product_keyword = any(keyword in query_lower for keyword in product_keywords)

        if has_product_keyword or query_analysis.get("is_data_related", True):
            return True, ""

        if query_analysis.get("query_type") == "OUT_OF_SCOPE":
            return False, "I'm a product catalog assistant specialized in glass bottles and jars."

        return True, ""

    def validate_response(self, response: str, context: str, query_type: str) -> Tuple[bool, List[str]]:
        # Skip validation for aggregation
        if query_type == "aggregation_query" or not context or "No matching" in context:
            return True, []

        start_time = self.logger.start_timing("Response Validation")

        validation_prompt = f"""Check if this response is based on context.

CONTEXT: {context[:2000]}
RESPONSE: {response}

Return JSON:
{{
  "is_grounded": boolean,
  "issues": ["list"],
  "confidence": "high" | "medium" | "low"
}}
"""

        try:
            validation_response = self.llm.invoke(validation_prompt)
            content = validation_response.content.strip()

            if content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content[3:]
            if content.endswith('```'):
                content = content.rsplit('\n', 1)[0] if '\n' in content else content[:-3]
            content = content.replace('```json', '').replace('```', '').strip()

            validation = json.loads(content)

            is_valid = validation.get("is_grounded", True)
            issues = validation.get("issues", [])

            self.logger.end_timing("Response Validation", start_time, {"is_grounded": is_valid})
            return is_valid, issues

        except Exception as e:
            self.logger.end_timing("Response Validation", start_time, {"error": str(e)})
            return True, []


class HybridRAGChatbot:
    """Enhanced Hybrid RAG Chatbot with aggregation support"""

    def __init__(self, verbose: bool = False, log_file: str = "chatbot_activity.log"):
        self.logger = ChatbotLogger(verbose=verbose, log_file=log_file)
        self.logger.console_logger.info("🚀 Initializing Enhanced Hybrid RAG Chatbot...")

        # MongoDB
        start_time = self.logger.start_timing("MongoDB Connection")
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI not found")

        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[os.getenv("MONGO_DB", "product_catalog")]
        self.collection = self.db[os.getenv("MONGO_COLLECTION", "processed_data")]
        self.logger.end_timing("MongoDB Connection", start_time)

        # Pinecone
        start_time = self.logger.start_timing("Pinecone Connection")
        pc = PineconeClient(api_key=os.getenv("PINECONE_API_KEY"))
        self.pinecone_index = pc.Index(os.getenv("PINECONE_INDEX", "processed-products-index"))
        self.logger.end_timing("Pinecone Connection", start_time)

        # Models
        start_time = self.logger.start_timing("Gemini Models Initialization")
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
        self.logger.end_timing("Gemini Models Initialization", start_time)

        self.router = QueryRouter(self.llm, self.logger)
        self.guardrails = GuardrailSystem(self.llm, self.logger)

        self.logger.console_logger.info("✅ Chatbot initialization complete!\n")

    def aggregation_query_mongodb(self, filters: Dict, aggregation_type: str, 
                                   aggregation_field: str) -> Dict[str, Any]:
        """Perform aggregation query on MongoDB with NULL handling"""

        start_time = self.logger.start_timing("MongoDB Aggregation Query")

        match_stage = self._build_mongodb_query(filters)
        pipeline = []

        if match_stage:
            pipeline.append({"$match": match_stage})

        # CRITICAL FIX: Filter out null/missing values BEFORE aggregation
        if aggregation_type in ["avg", "sum", "min", "max"]:
            pipeline.append({
                "$match": {
                    aggregation_field: {"$ne": None, "$exists": True, "$type": "number"}
                }
            })

        # Aggregation stage
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
        start_time = self.logger.start_timing("Pinecone Vector Search")

        query_text = semantic_desc or query
        query_embedding = self.embeddings_model.embed_query(query_text)

        pinecone_filter = self._build_pinecone_filter(filters) if filters else {}

        search_params = {
            "vector": query_embedding,
            "top_k": top_k,
            "include_metadata": True
        }
        if pinecone_filter:
            search_params["filter"] = pinecone_filter

        results = self.pinecone_index.query(**search_params)
        matches = results.get('matches', [])

        self.logger.end_timing("Pinecone Vector Search", start_time, {"results_count": len(matches)})
        return matches

    def _build_pinecone_filter(self, filters: Dict) -> Dict:
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
        start_time = self.logger.start_timing("MongoDB Structured Query")

        mongo_query = self._build_mongodb_query(filters)
        products = list(self.collection.find(mongo_query, {"_id": 0}).limit(limit))

        self.logger.end_timing("MongoDB Structured Query", start_time, {"results_count": len(products)})
        return products

    def _build_mongodb_query(self, filters: Dict) -> Dict:
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
        start_time = self.logger.start_timing("MongoDB Data Retrieval")
        products = list(self.collection.find({"sku": {"$in": skus}}, {"_id": 0}))
        self.logger.end_timing("MongoDB Data Retrieval", start_time, {"products_found": len(products)})
        return products

    def format_aggregation_context(self, aggregation_result: Dict, filters: Dict) -> str:
        start_time = self.logger.start_timing("Context Formatting")

        agg_type = aggregation_result.get("aggregation_type")
        results = aggregation_result.get("results", [])
        field = aggregation_result.get("field")

        context = f"Aggregation Query Results:\n"
        context += f"Type: {agg_type}\n"
        context += f"Filters: {json.dumps(filters)}\n\n"

        if agg_type == "count":
            total = results[0].get("total", 0) if results else 0
            context += f"Total Count: {total} products\n"

        elif agg_type in ["avg", "sum", "min", "max"]:
            if results:
                result_value = results[0].get("result")
                count = results[0].get("count", 0)
                context += f"{agg_type.upper()} of {field}: {result_value}\n"
                context += f"Products included: {count}\n"
            else:
                context += f"No valid data found for {field}\n"

        elif agg_type == "group":
            context += f"Grouped Results:\n"
            for item in results:
                context += f"- {item.get('_id')}: {item.get('count')} products\n"

        self.logger.end_timing("Context Formatting", start_time, {"aggregation_type": agg_type})
        return context

    def format_product_context(self, products: List[Dict], quantity: int = None) -> str:
        start_time = self.logger.start_timing("Context Formatting")

        context_parts = []
        for i, product in enumerate(products[:10], 1):
            context = f"\n--- Product {i} ---\n"
            context += f"Name: {product.get('name', 'N/A')}\n"
            context += f"SKU: {product.get('sku', 'N/A')}\n"
            context += f"Capacity: {product.get('original_capacity', 'N/A')} {product.get('original_uom', '')}\n"
            context += f"Color: {product.get('color', 'N/A')}\n"
            context_parts.append(context)

        formatted_context = "\n".join(context_parts)
        self.logger.end_timing("Context Formatting", start_time, {"products_formatted": len(context_parts)})
        return formatted_context

    def generate_response(self, user_query: str, context: str, intent: str, 
                         query_type: str) -> str:
        start_time = self.logger.start_timing("Response Generation")

        if query_type == "aggregation_query":
            system_context = """You are a product catalog assistant.

For AGGREGATION queries:
1. Use the computed statistics from aggregation results
2. State what data the calculation is based on
3. Be precise with numbers
4. Don't list individual products
5. If no valid data, state that clearly

STRICT: ONLY use provided information."""
        else:
            system_context = """You are a product catalog assistant.

STRICT RULES:
1. ONLY use provided information
2. Never fabricate data
3. Be accurate and concise"""

        final_prompt = f"""{system_context}

User Query: {user_query}

Context:
{context}

Provide accurate response based ONLY on above information."""

        response = self.llm.invoke(final_prompt)

        self.logger.end_timing("Response Generation", start_time, {"query_type": query_type})
        return response.content

    def query(self, user_query: str) -> str:
        query_start_time = time.time()
        errors = []

        try:
            query_type, analysis = self.router.analyze_and_route(user_query)

            is_valid, rejection_msg = self.guardrails.check_query_scope(user_query, analysis)

            guardrail_checks = {"scope_check": is_valid, "response_validation": True}

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

            # Retrieve data
            products = []
            context = ""
            pinecone_query = None
            mongodb_query = None
            aggregation_pipeline = None

            filters = analysis.get("filters", {})
            semantic_desc = analysis.get("semantic_description", "")

            # AGGREGATION QUERY
            if query_type == QueryType.AGGREGATION_QUERY:
                agg_type = analysis.get("aggregation_type", "count")
                agg_field = analysis.get("aggregation_field", "normalised_capacity_ml")

                agg_result = self.aggregation_query_mongodb(filters, agg_type, agg_field)
                context = self.format_aggregation_context(agg_result, filters)
                aggregation_pipeline = agg_result.get("pipeline")

                if agg_result.get("results"):
                    products = [{"aggregation_result": agg_result.get("results")}]

            elif query_type == QueryType.SEMANTIC_SEARCH or query_type == QueryType.HYBRID:
                matches = self.semantic_search_pinecone(
                    user_query, semantic_desc, top_k=10,
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
                context = "No matching products found."

            # Generate response
            response = self.generate_response(user_query, context, analysis.get("intent", "general"), query_type.value)

            # Validate response
            if products and query_type != QueryType.AGGREGATION_QUERY:
                is_grounded, issues = self.guardrails.validate_response(response, context, query_type.value)
                guardrail_checks["response_validation"] = is_grounded
                if issues:
                    errors.extend(issues)

            # Log query
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
            error_msg = f"Error: {str(e)}"
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

            return "I encountered an error. Please try rephrasing your question."

    def export_logs(self, filepath: str = "query_logs_export.json"):
        self.logger.export_logs(filepath)


def main():
    print("="*100)
    print("ENHANCED CHATBOT WITH NULL HANDLING IN AGGREGATION")
    print("="*100)

    chatbot = HybridRAGChatbot(verbose=True)

    test_queries = [
        "What is the average capacity (in ml) of products colored Cobalt Blue?",
        "How many amber bottles are in stock?",
        "I need bottles for essential oils around 30ml",
    ]

    for query in test_queries:
        print(f"\n{'='*100}")
        print(f"Query: {query}")
        print('='*100)

        response = chatbot.query(query)

        print("\n📤 RESPONSE:")
        print("-"*100)
        print(response)
        print("\n")

    chatbot.export_logs("query_logs.json")
    print("\n✅ Logs exported")

if __name__ == "__main__":
    main()
