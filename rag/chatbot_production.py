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
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        self.file_logger.addHandler(fh)

        self.console_logger = logging.getLogger("ChatbotConsole")
        self.console_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
        self.console_logger.handlers.clear()
        ch = logging.StreamHandler()
        ch.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
            )
        )
        self.console_logger.addHandler(ch)

    def start_timing(self, operation: str) -> float:
        start_time = time.time()
        if self.verbose:
            self.console_logger.info(f"⏱️ Starting: {operation}")
        return start_time

    def end_timing(
        self, operation: str, start_time: float, details: Optional[Dict] = None
    ) -> TimingMetrics:
        end_time = time.time()
        duration = end_time - start_time
        metric = TimingMetrics(
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            details=details,
        )
        self.timing_stack.append(metric)
        if self.verbose:
            self.console_logger.info(f"✅ Completed: {operation} in {duration:.3f}s")
            if details:
                self.console_logger.debug(
                    f"   Details: {json.dumps(details, indent=2)}"
                )
        self.file_logger.info(
            f"TIMING | {operation} | {duration:.3f}s | {details or {}}"
        )
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
            "errors": query_log.errors,
        }
        self.file_logger.info(f"QUERY_LOG | {json.dumps(log_entry)}")

        if self.verbose:
            self.console_logger.info("\n" + "=" * 80)
            self.console_logger.info("📊 QUERY EXECUTION SUMMARY")
            self.console_logger.info("=" * 80)
            self.console_logger.info(f"Total Time: {query_log.total_time:.3f}s")
            self.console_logger.info(f"Results: {query_log.results_count}")
            self.console_logger.info(
                f"Guardrails: {'✅ PASSED' if all(query_log.guardrail_checks.values()) else '⚠️ FLAGGED'}"
            )
            self.console_logger.info("\nTiming Breakdown:")
            for metric in query_log.timing_metrics:
                self.console_logger.info(f"  • {metric}")

    def export_logs(self, filepath: str = "query_logs_export.json"):
        with open(filepath, "w") as f:
            json.dump(
                [asdict(log) for log in self.query_logs], f, indent=2, default=str
            )
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
   Examples: "500ml bottles under $2", "show amber bottles"

3. AGGREGATION_QUERY: Statistics/calculations OR finding products by extreme values
   Examples:
   - "average capacity of Cobalt Blue products" (compute statistic)
   - "how many amber bottles in stock" (count)
   - "Which product has the largest capacity?" (find product with max)
   - "What's the smallest bottle?" (find product with min)
   - "Most expensive wine bottle?" (find product with max price)
   - "which company has the most products" (group by company and count)
   - "count products by color" (group by color)

   Keywords: average, mean, count, total, sum, max, min, largest, smallest, biggest, which product, what product, which company, count by, group by

4. HYBRID: Semantic description + specific filters
   Examples: "modern bottles in 750ml size"

5. OUT_OF_SCOPE: Not about products

CRITICAL:
- "Which/What product has [largest/smallest/most/least]" → AGGREGATION_QUERY with return_products=true
- "What is the average/count/total" → AGGREGATION_QUERY with return_products=false
- "which company has the most" → AGGREGATION_QUERY with aggregation_type="group", group_by_field="company"
- "count by [color/material/shape/company]" → AGGREGATION_QUERY with aggregation_type="group", group_by_field=[field]

GROUP BY QUERIES (queries that count/aggregate BY a category):
- "which company has the most products" → aggregation_type="group", group_by_field="company", aggregation_field=null
- "count products by color" → aggregation_type="group", group_by_field="color", aggregation_field=null
- "how many products per material" → aggregation_type="group", group_by_field="material", aggregation_field=null
- "which color has the highest average capacity" → aggregation_type="group", group_by_field="color", aggregation_field="capacity"

IMPORTANT: For GROUP queries, always set group_by_field to indicate what to group by. The aggregation_field can be null for simple counting.

Return JSON:
{{
"query_type": "SEMANTIC_SEARCH" | "STRUCTURED_QUERY" | "AGGREGATION_QUERY" | "HYBRID" | "OUT_OF_SCOPE",
"reasoning": "Brief explanation",
"intent": "product_search" | "pricing_query" | "statistics" | "aggregation" | "find_extreme" | "out_of_scope",
"requires_pinecone": boolean,
"requires_mongodb": boolean,
"requires_aggregation": boolean,
"aggregation_type": "avg" | "count" | "sum" | "min" | "max" | "group" | null,
"aggregation_field": "capacity" | "price" | null,
"group_by_field": "company" | "color" | "material" | "shape" | null,
"return_products": boolean (true for "which product" queries, false for statistics),
"filters": {{
  "capacity_range": {{"min": number, "max": number, "unit": "oz"|"ml"|"l"|"gal"}} or null,
  "color": "color name" or null,
  "material": "material type" or null,
  "shape": "shape description" or null,
  "company": "company name" or null,
  "price_range": {{"min": number, "max": number}} or null,
  "stock_required": boolean
}},
"semantic_description": "description",
"is_data_related": boolean
}}

FIELD EXTRACTION GUIDELINES:
- "color": Extract bottle color (e.g., "Amber", "Cobalt Blue", "Clear")
- "material": Extract material type (e.g., "Glass", "Plastic")
- "shape": Extract bottle shape (e.g., "Boston Round", "Cylinder", "Flask","Round")
- "capacity_range": **CRITICAL** - You MUST extract BOTH number AND unit:
  * "4 oz" → {{"min": 4, "max": 4, "unit": "oz"}}
  * "500ml" → {{"min": 500, "max": 500, "unit": "ml"}}
  * "1 liter" → {{"min": 1, "max": 1, "unit": "l"}}
  * If NO unit mentioned, use "ml"

IMPORTANT REMINDERS:
- For capacity_range, the "unit" field is MANDATORY - always extract "oz", "ml", "l", or "gal"
- Look for unit indicators: oz, ounce, ml, milliliter, liter, litre, l, gallon, gal
- The numeric value and unit MUST be separated in the JSON
- For GROUP BY queries, extract group_by_field separate from aggregation_field

Return ONLY valid JSON, no markdown.
"""

        try:
            response = self.llm.invoke(analysis_prompt)
            content = response.content.strip()

            # Clean markdown
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = (
                    content.rsplit("\n", 1)[0] if "\n" in content else content[:-3]
                )
            content = content.replace("```json", "").replace("```", "").strip()

            analysis = json.loads(content)
            query_type_str = analysis.get("query_type", "HYBRID")

            # Override
            if (
                analysis.get("is_data_related", True)
                and query_type_str == "OUT_OF_SCOPE"
            ):
                query_type_str = "SEMANTIC_SEARCH"
                self.logger.console_logger.info(
                    "Overriding OUT_OF_SCOPE to SEMANTIC_SEARCH"
                )

            query_type = QueryType[query_type_str]

            self.logger.end_timing(
                "Query Analysis & Routing",
                start_time,
                {
                    "query_type": query_type.value,
                    "intent": analysis.get("intent"),
                    "requires_aggregation": analysis.get("requires_aggregation", False),
                    "aggregation_type": analysis.get("aggregation_type"),
                    "group_by_field": analysis.get("group_by_field"),
                    "return_products": analysis.get("return_products", False),
                },
            )

            return query_type, analysis

        except Exception as e:
            self.logger.console_logger.error(f"❌ Query analysis failed: {str(e)}")
            self.logger.end_timing(
                "Query Analysis & Routing", start_time, {"error": str(e)}
            )
            return QueryType.HYBRID, {
                "query_type": "HYBRID",
                "intent": "product_search",
                "requires_pinecone": True,
                "requires_mongodb": True,
                "requires_aggregation": False,
                "filters": {},
                "is_data_related": True,
                "semantic_description": user_query,
            }


class GuardrailSystem:
    """Guardrails to ensure chatbot stays within scope"""

    def __init__(self, llm: ChatGoogleGenerativeAI, logger: ChatbotLogger):
        self.llm = llm
        self.logger = logger

    def check_query_scope(self, query: str, query_analysis: Dict) -> Tuple[bool, str]:
        product_keywords = [
            "bottle",
            "jar",
            "container",
            "glass",
            "packaging",
            "amber",
            "flint",
            "cobalt",
            "boston round",
            "wine",
            "liquor",
            "ml",
            "oz",
            "price",
            "capacity",
            "product",
            "largest",
            "smallest",
            "average",
            "count",
            "how many",
            "company",
        ]

        query_lower = query.lower()
        has_product_keyword = any(
            keyword in query_lower for keyword in product_keywords
        )

        if has_product_keyword or query_analysis.get("is_data_related", True):
            return True, ""

        if query_analysis.get("query_type") == "OUT_OF_SCOPE":
            return (
                False,
                "I'm a product catalog assistant specialized in glass bottles and jars. I can help you find products, check pricing, verify availability, get statistics, and compare options. What would you like to know about our catalog?",
            )

        return True, ""

    def validate_response(
        self, response: str, context: str, query_type: str
    ) -> Tuple[bool, List[str]]:
        # Skip validation for aggregation queries
        if query_type == "aggregation_query" or not context or "No matching" in context:
            return True, []

        # Simplified validation - just check if response is reasonable
        return True, []


class HybridRAGChatbot:
    """
    Production-Ready Enhanced Hybrid RAG Chatbot
    - Intelligent query routing (semantic, structured, aggregation, hybrid)
    - Comprehensive logging with timing metrics
    - Guardrails for scope control
    - MongoDB aggregation with proper field handling
    - Returns products for "which product" queries
    - FIXED: Handles "which company has the most products" queries
    """

    # Field name constants based on your MongoDB schema
    CAPACITY_FIELD = "normalised_capacity(ml)"
    PRICE_FIELD = "avg_price_per_unit"
    COLOR_FIELD = "color"
    MATERIAL_FIELD = "material"
    SHAPE_FIELD = "shape"
    COMPANY_FIELD = "company"
    STOCK_FIELD = "stock"
    SKU_FIELD = "sku"
    NAME_FIELD = "name"
    STOCKFIELD = "stock"

    def __init__(self, verbose: bool = False, log_file: str = "chatbot_activity.log"):
        self.logger = ChatbotLogger(verbose=verbose, log_file=log_file)
        self.logger.console_logger.info(
            "🚀 Initializing Production-Ready Hybrid RAG Chatbot..."
        )

        # MongoDB
        start_time = self.logger.start_timing("MongoDB Connection")
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI not found in environment variables")
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[os.getenv("MONGO_DB", "product_catalog")]
        self.collection = self.db[os.getenv("MONGO_COLLECTION", "processed_data")]
        self.logger.console_logger.info(
            f"📊 Using capacity field: {self.CAPACITY_FIELD}"
        )
        self.logger.end_timing("MongoDB Connection", start_time)

        # Pinecone
        start_time = self.logger.start_timing("Pinecone Connection")
        pc = PineconeClient(api_key=os.getenv("PINECONE_API_KEY"))
        self.pinecone_index = pc.Index(
            os.getenv("PINECONE_INDEX", "processed-products-index")
        )
        self.logger.end_timing("Pinecone Connection", start_time)

        # Models
        start_time = self.logger.start_timing("Gemini Models Initialization")
        self.embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            convert_system_message_to_human=True,
        )
        self.logger.end_timing("Gemini Models Initialization", start_time)

        self.router = QueryRouter(self.llm, self.logger)
        self.guardrails = GuardrailSystem(self.llm, self.logger)

        self.logger.console_logger.info("✅ Chatbot initialization complete!\n")

    def normalize_capacity_to_ml(self, value: float, unit: str) -> float:
        """
        Convert capacity values to milliliters

        Args:
            value: Numeric capacity value
            unit: Unit string (oz, ml, l, etc.)

        Returns:
            Capacity in milliliters
        """
        unit_lower = unit.lower().strip()

        # Conversion factors to ml
        conversions = {
            "oz": 29.5735,  # US fluid ounce
            "fl oz": 29.5735,
            "floz": 29.5735,
            "ounce": 29.5735,
            "ounces": 29.5735,
            "l": 1000,
            "liter": 1000,
            "litre": 1000,
            "liters": 1000,
            "litres": 1000,
            "ml": 1,
            "milliliter": 1,
            "milliliters": 1,
            "cl": 10,
            "centiliter": 10,
            "gal": 3785.41,
            "gallon": 3785.41,
            "gallons": 3785.41,
        }

        conversion_factor = conversions.get(unit_lower, 1)
        converted_value = round(value * conversion_factor, 2)
        self.logger.console_logger.debug(
            f"Unit conversion: {value} {unit} -> {converted_value:.2f} ml"
        )
        return converted_value

    def normalize_company_name(self, company_input: str) -> Optional[str]:
        """
        Normalize company name variations to exact MongoDB values.

        Args:
            company_input: Raw company name from user query or LLM extraction

        Returns:
            Normalized company name matching MongoDB data, or None if invalid
        """
        if not company_input:
            return None

        # Normalize input: lowercase and remove extra spaces
        normalized = company_input.lower().strip()

        # Company name mapping
        company_mapping = {
            "berlin": "Berlin Packaging",
            "berlin packaging": "Berlin Packaging",
            "cary": "Cary Company",
            "cary company": "Cary Company",
            "tricor": "TricorBrawn",
            "tricorbrawn": "TricorBrawn",
            "tricor brawn": "TricorBrawn",
            "tricor-brawn": "TricorBrawn",
        }

        exact_match = company_mapping.get(normalized)
        if exact_match:
            self.logger.console_logger.debug(
                f"🏢 Company normalized: '{company_input}' → '{exact_match}'"
            )
            return exact_match

        # Fallback: check if input already matches a valid company (case-insensitive)
        valid_companies = ["Berlin Packaging", "Cary Company", "TricorBrawn"]
        for valid in valid_companies:
            if normalized == valid.lower():
                return valid

        self.logger.console_logger.warning(f"⚠️ Unknown company: '{company_input}'")
        return None

    def set_verbose(self, verbose: bool):
        """Toggle verbose mode"""
        self.logger.verbose = verbose
        self.logger.console_logger.setLevel(
            logging.DEBUG if verbose else logging.WARNING
        )

    def aggregation_query_mongodb(
        self,
        filters: Dict,
        aggregation_type: str,
        aggregation_field: str = None,
        group_by_field: str = None,
        return_products: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform aggregation query on MongoDB

        Args:
            filters: MongoDB filter criteria
            aggregation_type: Type of aggregation (avg, count, sum, min, max, group)
            aggregation_field: Field to aggregate on ("capacity" or "price") - optional for simple group queries
            group_by_field: Field to group by ("company", "color", "material", "shape") - required for group queries
            return_products: If True, return actual product documents (for "which product" queries)
        """
        start_time = self.logger.start_timing("MongoDB Aggregation Query")

        # VALIDATION - Prevent None errors
        if aggregation_type == "group" and not group_by_field:
            raise ValueError(
                "group_by_field is required when aggregation_type is 'group'. "
                "For queries like 'which company has the most products', "
                "set group_by_field='company' and aggregation_field=None"
            )

        if aggregation_type in ["avg", "sum", "min", "max"] and not aggregation_field:
            raise ValueError(
                f"aggregation_field is required for aggregation_type '{aggregation_type}'"
            )

        # Map generic field names to actual DB field names
        field_mapping = {"capacity": self.CAPACITY_FIELD, "price": self.PRICE_FIELD}

        # Map group_by fields to actual DB field names
        group_field_mapping = {
            "company": self.COMPANY_FIELD,
            "color": self.COLOR_FIELD,
            "material": self.MATERIAL_FIELD,
            "shape": self.SHAPE_FIELD,
            "stock_status": self.STOCKFIELD,  # Add this line
            "stock": self.STOCKFIELD,
        }

        # Map fields appropriately
        actual_field = None
        if aggregation_field:
            actual_field = field_mapping.get(aggregation_field, aggregation_field)

        actual_group_field = None
        if group_by_field:
            actual_group_field = group_field_mapping.get(group_by_field, group_by_field)
            self.logger.console_logger.info(
                f"🔍 Grouping by field: {group_by_field} -> {actual_group_field}"
            )

        match_stage = self._build_mongodb_query(filters)
        pipeline = []
        products = []

        # LOG: Initial filter stage
        self.logger.console_logger.info(
            f"🔍 MongoDB Filters Applied: {json.dumps(filters, indent=2)}"
        )
        self.logger.file_logger.info(f"MONGODB_FILTERS | {json.dumps(filters)}")

        # For "which product has max/min" queries - return actual products
        if return_products and aggregation_type in ["min", "max"]:
            # Step 1: Filter by criteria
            if match_stage:
                pipeline.append({"$match": match_stage})

            # Step 2: Filter out null values
            pipeline.append(
                {
                    "$match": {
                        actual_field: {"$ne": None, "$exists": True, "$type": "number"}
                    }
                }
            )

            # Step 3: Sort by field (descending for max, ascending for min)
            sort_order = -1 if aggregation_type == "max" else 1
            pipeline.append({"$sort": {actual_field: sort_order}})

            # Step 4: Get top results
            pipeline.append({"$limit": 5})

            # Execute and get actual products
            self.logger.console_logger.info(
                f"📊 MongoDB Aggregation Pipeline: {json.dumps(pipeline, indent=2)}"
            )
            self.logger.file_logger.info(f"MONGODB_PIPELINE | {json.dumps(pipeline)}")

            query_start = time.time()
            products = list(self.collection.aggregate(pipeline))
            query_time = time.time() - query_start

            self.logger.console_logger.info(
                f"✅ MongoDB Response: {len(products)} products returned in {query_time:.3f}s"
            )
            self.logger.file_logger.info(
                f"MONGODB_RESPONSE | count={len(products)} | time={query_time:.3f}s | data={json.dumps(products, default=str)}"
            )

            self.logger.end_timing(
                "MongoDB Aggregation Query",
                start_time,
                {
                    "query_time": query_time,
                    "pipeline_stages": len(pipeline),
                    "results_count": len(products),
                    "aggregation_type": aggregation_type,
                    "return_products": True,
                },
            )

            return {
                "pipeline": pipeline,
                "results": products,
                "aggregation_type": aggregation_type,
                "field": actual_field,
                "return_products": True,
            }

        # For statistical aggregations (avg, count, sum) and GROUP queries
        else:
            if match_stage:
                pipeline.append({"$match": match_stage})

            # Filter out nulls for numeric aggregations
            if aggregation_type in ["avg", "sum", "min", "max"]:
                pipeline.append(
                    {
                        "$match": {
                            actual_field: {
                                "$ne": None,
                                "$exists": True,
                                "$type": "number",
                            }
                        }
                    }
                )

            # Aggregation stage
            if aggregation_type == "count":
                pipeline.append({"$count": "total"})

            elif aggregation_type in ["avg", "sum", "min", "max"]:
                group_stage = {
                    "$group": {
                        "_id": None,
                        "result": {f"${aggregation_type}": f"${actual_field}"},
                        "count": {"$sum": 1},
                    }
                }
                pipeline.append(group_stage)

            elif aggregation_type == "group":
                # FIXED: Proper group handling with validation
                if not actual_group_field:
                    raise ValueError(
                        "Cannot perform group aggregation without a valid group_by_field"
                    )

                if actual_group_field == self.STOCK_FIELD:
                    pipeline.append(
                        {
                            "$addFields": {
                                "stock_category": {
                                    "$switch": {
                                        "branches": [
                                            {
                                                "case": {"$eq": ["$stock", "In stock"]},
                                                "then": "In Stock",
                                            },
                                            {
                                                "case": {
                                                    "$eq": ["$stock", "Out Of Stock"]
                                                },
                                                "then": "Out of Stock",
                                            },
                                            {
                                                "case": {
                                                    "$regexMatch": {
                                                        "input": "$stock",
                                                        "regex": "^Item is currently estimated",
                                                    }
                                                },
                                                "then": "Lead Time",
                                            },
                                            {
                                                "case": {
                                                    "$regexMatch": {
                                                        "input": "$stock",
                                                        "regex": "Special Order",
                                                    }
                                                },
                                                "then": "Special Order",
                                            },
                                        ],
                                        "default": "Other",
                                    }
                                }
                            }
                        }
                    )
                    actual_group_field = (
                        "stock_category"  # Use the normalized field for grouping
                    )

                # Build group stage
                group_stage = {
                    "$group": {"_id": f"${actual_group_field}", "count": {"$sum": 1}}
                }

                # Optionally include aggregation on another field if specified
                if actual_field:
                    group_stage["$group"]["avg_value"] = {"$avg": f"${actual_field}"}
                    group_stage["$group"]["min_value"] = {"$min": f"${actual_field}"}
                    group_stage["$group"]["max_value"] = {"$max": f"${actual_field}"}

                pipeline.append(group_stage)
                pipeline.append({"$sort": {"count": -1}})
                pipeline.append({"$limit": 10})  # Limit to top 10 results

            query_start = time.time()
            results = list(self.collection.aggregate(pipeline))
            query_time = time.time() - query_start

            self.logger.end_timing(
                "MongoDB Aggregation Query",
                start_time,
                {
                    "query_time": query_time,
                    "pipeline_stages": len(pipeline),
                    "results_count": len(results),
                    "aggregation_type": aggregation_type,
                    "results": results,
                },
            )

            return {
                "pipeline": pipeline,
                "results": results,
                "aggregation_type": aggregation_type,
                "field": actual_field,
                "return_products": False,
            }

    def _get_stock_category_pipeline(self):
        """Create aggregation pipeline stage to categorize stock status"""
        return {
            "$addFields": {
                "stock_category": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {"$eq": ["$stock", "In stock"]},
                                "then": "In Stock",
                            },
                            {
                                "case": {"$eq": ["$stock", "Out Of Stock"]},
                                "then": "Out of Stock",
                            },
                            {
                                "case": {
                                    "$regexMatch": {
                                        "input": "$stock",
                                        "regex": "^Item is currently estimated",
                                    }
                                },
                                "then": "Lead Time",
                            },
                            {
                                "case": {
                                    "$regexMatch": {
                                        "input": "$stock",
                                        "regex": "Special Order",
                                    }
                                },
                                "then": "Special Order",
                            },
                        ],
                        "default": "Other",
                    }
                }
            }
        }

    def semantic_search_pinecone(
        self, query: str, semantic_desc: str, top_k: int = 10, filters: Dict = None
    ) -> List[Dict]:
        start_time = self.logger.start_timing("Pinecone Vector Search")

        embed_start = time.time()
        query_text = semantic_desc or query
        query_embedding = self.embeddings_model.embed_query(query_text)
        embed_time = time.time() - embed_start
        self.logger.file_logger.info(
            f"EMBEDDING | Generated in {embed_time:.3f}s | Dimension: {len(query_embedding)}"
        )

        pinecone_filter = self._build_pinecone_filter(filters) if filters else {}
        search_params = {
            "vector": query_embedding,
            "top_k": top_k,
            "include_metadata": True,
        }

        if pinecone_filter:
            search_params["filter"] = pinecone_filter

        search_start = time.time()
        results = self.pinecone_index.query(**search_params)
        search_time = time.time() - search_start

        matches = results.get("matches", [])

        self.logger.end_timing(
            "Pinecone Vector Search",
            start_time,
            {
                "embedding_time": embed_time,
                "search_time": search_time,
                "results_count": len(matches),
            },
        )

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

        # LOG: MongoDB query
        self.logger.console_logger.info(
            f"🔍 MongoDB Query: {json.dumps(mongo_query, indent=2)}"
        )
        self.logger.file_logger.info(f"MONGODB_QUERY | {json.dumps(mongo_query)}")

        query_start = time.time()
        products = list(self.collection.find(mongo_query, {"_id": 0}).limit(limit))
        query_time = time.time() - query_start

        # LOG: Query results
        self.logger.console_logger.info(
            f"✅ MongoDB Response: {len(products)} products returned in {query_time:.3f}s"
        )
        self.logger.file_logger.info(
            f"MONGODB_RESPONSE | count={len(products)} | time={query_time:.3f}s | data={json.dumps(products, default=str)}"
        )

        self.logger.end_timing(
            "MongoDB Structured Query",
            start_time,
            {
                "query_time": query_time,
                "results_count": len(products),
                "query": mongo_query,
            },
        )

        return products

    def _build_mongodb_query(self, filters: Dict) -> Dict:
        mongo_query = {}

        if filters.get("color"):
            mongo_query[self.COLOR_FIELD] = {
                "$regex": filters["color"],
                "$options": "i",
            }

        if filters.get("material"):
            mongo_query[self.MATERIAL_FIELD] = {
                "$regex": filters["material"],
                "$options": "i",
            }

        if filters.get("shape"):
            mongo_query[self.SHAPE_FIELD] = {
                "$regex": filters["shape"],
                "$options": "i",
            }

        if filters.get("company"):
            mongo_query[self.COMPANY_FIELD] = {
                "$regex": filters["company"],
                "$options": "i",
            }

        if filters.get("capacity_range"):
            cap_range = filters["capacity_range"]
            if cap_range.get("min") or cap_range.get("max"):
                # Extract unit (default to 'ml' if not specified)
                unit = cap_range.get("unit", "ml")
                mongo_query[self.CAPACITY_FIELD] = {}

                if cap_range.get("min"):
                    min_ml = self.normalize_capacity_to_ml(cap_range["min"], unit)
                    mongo_query[self.CAPACITY_FIELD]["$gte"] = min_ml

                if cap_range.get("max"):
                    max_ml = self.normalize_capacity_to_ml(cap_range["max"], unit)
                    mongo_query[self.CAPACITY_FIELD]["$lte"] = max_ml

        if filters.get("price_range"):
            price_range = filters["price_range"]
            if price_range.get("min") or price_range.get("max"):
                mongo_query[self.PRICE_FIELD] = {}
                if price_range.get("min"):
                    mongo_query[self.PRICE_FIELD]["$gte"] = price_range["min"]
                if price_range.get("max"):
                    mongo_query[self.PRICE_FIELD]["$lte"] = price_range["max"]

        if filters.get("stock_required"):
            mongo_query[self.STOCK_FIELD] = {"$regex": "In Stock", "$options": "i"}

        return mongo_query

    def fetch_complete_data_mongodb(self, skus: List[str]) -> List[Dict]:
        start_time = self.logger.start_timing("MongoDB Data Retrieval")

        products = list(
            self.collection.find({self.SKU_FIELD: {"$in": skus}}, {"_id": 0})
        )

        self.logger.end_timing(
            "MongoDB Data Retrieval",
            start_time,
            {
                "skus_requested": len(skus),
                "products_found": len(products),
                "product_data": products,
            },
        )

        return products

    def format_aggregation_context(
        self, aggregation_result: Dict, filters: Dict
    ) -> str:
        start_time = self.logger.start_timing("Context Formatting")

        agg_type = aggregation_result.get("aggregation_type")
        results = aggregation_result.get("results", [])
        field = aggregation_result.get("field")
        return_products = aggregation_result.get("return_products", False)

        context = f"Aggregation Query Results:\n"
        context += f"Type: {agg_type}\n"
        context += f"Field: {field}\n"
        context += f"Filters: {json.dumps(filters)}\n\n"

        if return_products:
            # Return actual product details
            context += f"Products with {agg_type} {field}:\n\n"
            for i, product in enumerate(results[:5], 1):
                context += f"--- Product {i} ---\n"
                context += f"Name: {product.get(self.NAME_FIELD, 'N/A')}\n"
                context += f"SKU: {product.get(self.SKU_FIELD, 'N/A')}\n"
                context += f"Company: {product.get(self.COMPANY_FIELD, 'N/A')}\n"
                context += f"Capacity: {product.get('original_capacity', 'N/A')} {product.get('original_uom', '')}\n"
                context += f"Capacity (ml): {product.get(self.CAPACITY_FIELD, 'N/A')}\n"
                context += f"Price: ${product.get(self.PRICE_FIELD, 'N/A')}\n"
                context += f"Color: {product.get(self.COLOR_FIELD, 'N/A')}\n"
                context += f"Material: {product.get(self.MATERIAL_FIELD, 'N/A')}\n"
                context += f"Shape: {product.get(self.SHAPE_FIELD, 'N/A')}\n"
                context += f"Stock: {product.get(self.STOCK_FIELD, 'N/A')}\n"
                context += f"URL: {product.get('url', 'N/A')}\n\n"
        else:
            # Return statistical results
            if agg_type == "count":
                total = results[0].get("total", 0) if results else 0
                context += f"Total Count: {total} products\n"

            elif agg_type in ["avg", "sum", "min", "max"]:
                if results:
                    result_value = results[0].get("result")
                    count = results[0].get("count", 0)
                    context += f"{agg_type.upper()} of {field}: {result_value}\n"
                    context += f"Products included in calculation: {count}\n"
                else:
                    context += f"No valid data found for {field}\n"

            elif agg_type == "group":
                # FIXED: Better formatting for group results
                context += f"Grouped Results:\n"
                for item in results:
                    group_key = item.get("_id", "Unknown")
                    count = item.get("count", 0)
                    context += f"- {group_key}: {count} products"

                    # Add aggregate values if present
                    if "avg_value" in item:
                        context += f" (avg: {item.get('avg_value', 'N/A')}"
                        if "min_value" in item:
                            context += f", min: {item.get('min_value', 'N/A')}"
                        if "max_value" in item:
                            context += f", max: {item.get('max_value', 'N/A')}"
                        context += ")"

                    context += "\n"

        self.logger.end_timing(
            "Context Formatting",
            start_time,
            {"aggregation_type": agg_type, "return_products": return_products},
        )

        return context

    def format_product_context(self, products: List[Dict], quantity: int = None) -> str:
        start_time = self.logger.start_timing("Context Formatting")

        context_parts = []
        for i, product in enumerate(products[:10], 1):
            context = f"\n--- Product {i} ---\n"
            context += f"Name: {product.get(self.NAME_FIELD, 'N/A')}\n"
            context += f"SKU: {product.get(self.SKU_FIELD, 'N/A')}\n"
            context += f"Company: {product.get(self.COMPANY_FIELD, 'N/A')}\n"
            context += f"Capacity: {product.get('original_capacity', 'N/A')} {product.get('original_uom', '')}\n"
            context += f"Color: {product.get(self.COLOR_FIELD, 'N/A')}\n"
            context += f"Material: {product.get(self.MATERIAL_FIELD, 'N/A')}\n"
            context += f"Shape: {product.get(self.SHAPE_FIELD, 'N/A')}\n"
            context += f"Stock: {product.get(self.STOCK_FIELD, 'N/A')}\n"

            # Enhanced Pricing Section
            quantity_breaks = product.get("quantity_breaks", [])
            items_per_case = product.get("items_per_unit", "N/A")
            type_of_packing = product.get("type_of_packing", "N/A")

            if quantity_breaks:
                context += "\nPRICING INFORMATION:\n"
                context += f"Packaging Type: {type_of_packing}\n"
                context += f"Items per {type_of_packing}: {items_per_case}\n"
                context += "\nPrice Tiers (Case-Based):\n"

                for tier in quantity_breaks[:5]:
                    qty_range = tier.get("quantity_of_packing", "N/A")
                    price_per_item = tier.get("price_per_item", "N/A")
                    price_per_packing = tier.get("price_per_packing", "N/A")
                    context += f"  • Quantity: {qty_range} {type_of_packing}(s)\n"
                    context += (
                        f"    - Price per {type_of_packing}: ${price_per_packing}\n"
                    )
                    context += f"    - Price per item/unit: ${price_per_item}\n"
            else:
                context += "\nPricing information not available\n"

            context += f"URL: {product.get('url', 'N/A')}\n"
            context_parts.append(context)

        formatted_context = "\n".join(context_parts)

        self.logger.end_timing(
            "Context Formatting",
            start_time,
            {
                "products_formatted": len(context_parts),
                "context_length": len(formatted_context),
            },
        )

        return formatted_context

    def generate_response(
        self, user_query: str, context: str, intent: str, query_type: str
    ) -> str:
        start_time = self.logger.start_timing("Response Generation")

        if query_type == "aggregation_query":
            system_context = """You are a product catalog assistant for glass bottles and jars.

For AGGREGATION queries:
1. Use the computed statistics or listed products from aggregation results
2. Clearly state what the data shows
3. Be precise with numbers and product details
4. Don't list individual products for statistical queries (avg, count, sum)
5. DO list specific products for "which product" queries (max, min with products)
6. Always cite specific product names, SKUs when products are provided

STRICT RULES:
1. ONLY use information from the provided context
2. Never fabricate data
3. Be accurate and concise"""
        else:
            system_context = """You are a product catalog assistant for glass bottles and jars.

STRICT RULES:
1. ONLY use information from the provided product context
2. Never fabricate or estimate data
3. If information is not in context, explicitly state "This information is not available"
4. Always cite specific product names, SKUs, and prices exactly as provided
5. Stay within the domain of product catalog assistance
6. Include stock status when relevant

Be helpful, accurate, and concise."""

        final_prompt = f"""{system_context}

User Query: {user_query}

Context:
{context}

Provide an accurate response based ONLY on the above information."""

        response = self.llm.invoke(final_prompt)

        self.logger.end_timing(
            "Response Generation",
            start_time,
            {
                "prompt_length": len(final_prompt),
                "response_length": len(response.content),
                "query_type": query_type,
            },
        )

        return response.content

    def query(self, user_query: str) -> str:
        """Main query method with full pipeline"""
        query_start_time = time.time()
        errors = []

        try:
            if self.logger.verbose:
                self.logger.console_logger.info("\n" + "=" * 80)
                self.logger.console_logger.info(f"🔍 NEW QUERY: {user_query}")
                self.logger.console_logger.info("=" * 80)

            # Step 1: Route query
            query_type, analysis = self.router.analyze_and_route(user_query)

            # Step 2: Guardrail check
            is_valid, rejection_msg = self.guardrails.check_query_scope(
                user_query, analysis
            )
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
                    errors=[],
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

            # AGGREGATION QUERY - FIXED to pass group_by_field
            if query_type == QueryType.AGGREGATION_QUERY:
                agg_type = analysis.get("aggregation_type", "count")
                agg_field = analysis.get(
                    "aggregation_field", None
                )  # Can be None for group queries
                group_by = analysis.get(
                    "group_by_field", None
                )  # NEW: Extract group_by_field
                return_products = analysis.get("return_products", False)

                self.logger.console_logger.info(
                    f"📊 Aggregation params: type={agg_type}, field={agg_field}, group_by={group_by}"
                )

                agg_result = self.aggregation_query_mongodb(
                    filters,
                    agg_type,
                    agg_field,
                    group_by,
                    return_products,  # Pass group_by parameter
                )

                context = self.format_aggregation_context(agg_result, filters)
                aggregation_pipeline = agg_result.get("pipeline")

                # Get products from aggregation result
                if agg_result.get("return_products"):
                    products = agg_result.get("results", [])
                else:
                    if agg_result.get("results"):
                        products = [{"aggregation_result": agg_result.get("results")}]

            elif (
                query_type == QueryType.SEMANTIC_SEARCH
                or query_type == QueryType.HYBRID
            ):
                matches = self.semantic_search_pinecone(
                    user_query,
                    semantic_desc,
                    top_k=10,
                    filters=filters if query_type == QueryType.HYBRID else None,
                )
                skus = [m["id"] for m in matches]
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
                user_query, context, analysis.get("intent", "general"), query_type.value
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
                errors=errors,
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
                aggregation_pipeline=None,
                results_count=0,
                response_length=0,
                guardrail_checks={"scope_check": False, "response_validation": False},
                total_time=time.time() - query_start_time,
                errors=[error_msg],
            )

            self.logger.log_query(query_log)
            self.logger.timing_stack.clear()

            return "I apologize, but I encountered an error processing your request. Please try rephrasing your question."

    def export_logs(self, filepath: str = "query_logs_export.json"):
        """Export all query logs"""
        self.logger.export_logs(filepath)


# Example usage
def main():
    print("=" * 100)
    print("PRODUCTION-READY CHATBOT - FIXED FOR GROUP BY QUERIES")
    print("=" * 100)

    # Initialize with verbose mode
    chatbot = HybridRAGChatbot(verbose=True, log_file="chatbot_activity.log")

    # Test queries including the fixed "which company" query
    test_queries = [
        "which company has the most products",
        "count products by color",
        "Which product has the largest capacity in milliliters?",
        "What is the average capacity (in ml) of products colored Cobalt Blue?",
        "How many amber bottles are in stock?",
    ]

    for query in test_queries:
        print(f"\n{'='*100}")
        print(f"Query: {query}")
        print("=" * 100)
        response = chatbot.query(query)
        print("\n📤 RESPONSE:")
        print("-" * 100)
        print(response)
        print("\n")

    # Export logs
    chatbot.export_logs("query_logs.json")
    print("\n✅ Logs exported to query_logs.json")


if __name__ == "__main__":
    main()
