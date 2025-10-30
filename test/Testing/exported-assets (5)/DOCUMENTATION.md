# Enhanced Chatbot Documentation

## Overview
The enhanced chatbot includes three major improvements:
1. **Intelligent Query Routing** - Identifies whether queries need vector search, structured queries, or both
2. **Comprehensive Logging System** - Tracks all activities and timing metrics when verbose=True
3. **Guardrails** - Ensures chatbot only responds to product-related queries

---

## 1. Query Routing System

### QueryType Enum
Defines four types of queries:

- **SEMANTIC_SEARCH**: Requires vector similarity search in Pinecone
  - Examples: "bottles for essential oils", "elegant wine bottles"
  - Uses: Natural language descriptions, conceptual searches

- **STRUCTURED_QUERY**: Requires MongoDB filtering only
  - Examples: "500ml bottles under $2", "amber bottles from Berlin Packaging"
  - Uses: Specific filters (price, capacity, color, company)

- **HYBRID**: Requires both Pinecone + MongoDB
  - Examples: "modern looking bottles in 750ml size"
  - Uses: Combines semantic description with specific filters

- **OUT_OF_SCOPE**: Not related to product data
  - Examples: "What's the weather?", "Tell me a joke"
  - Action: Politely decline and redirect to product queries

### QueryRouter Class

**Purpose**: Analyzes user queries and determines the optimal retrieval strategy

**Key Method**: `analyze_and_route(user_query)`

**Process**:
1. Sends query to Gemini LLM for analysis
2. Extracts:
   - Query type (semantic/structured/hybrid/out-of-scope)
   - Intent (product_search, pricing_query, etc.)
   - Filters (capacity, color, price range, etc.)
   - Whether Pinecone and/or MongoDB is needed
3. Returns QueryType and detailed analysis

**Example Output**:
```json
{
  "query_type": "HYBRID",
  "reasoning": "Query has semantic description (elegant) + specific filter (750ml)",
  "intent": "product_search",
  "requires_pinecone": true,
  "requires_mongodb": true,
  "filters": {
    "capacity_range": {"min": 750, "max": 750}
  },
  "semantic_description": "elegant wine bottles",
  "is_data_related": true
}
```

---

## 2. Logging System

### ChatbotLogger Class

**Purpose**: Centralized logging for both console (verbose mode) and file persistence

**Features**:
- Console logging (controlled by verbose flag)
- File logging (always active) → `chatbot_activity.log`
- Timing metrics for every operation
- Structured query logs for analysis

### Timing Metrics

**Tracked Operations**:
1. MongoDB Connection
2. Pinecone Connection
3. Gemini Models Initialization
4. Query Analysis & Routing
5. **Embedding Generation** (isolated timing)
6. **Pinecone Vector Search** (isolated timing)
7. **MongoDB Queries** (isolated timing)
8. Context Formatting
9. Response Generation
10. Response Validation

**Example Log Output** (verbose=True):
```
2025-10-30 10:15:23 - INFO - ⏱️  Starting: Embedding Generation
2025-10-30 10:15:24 - INFO - ✅ Completed: Embedding Generation in 0.847s
2025-10-30 10:15:24 - INFO - ⏱️  Starting: Pinecone Vector Search
2025-10-30 10:15:25 - INFO - ✅ Completed: Pinecone Vector Search in 1.234s
2025-10-30 10:15:25 - INFO - ⏱️  Starting: MongoDB Data Retrieval
2025-10-30 10:15:26 - INFO - ✅ Completed: MongoDB Data Retrieval in 0.523s
```

### File Logging

**Log File**: `chatbot_activity.log`

**Log Entries Include**:
- Timestamp
- Operation type
- Duration
- Detailed metrics (results count, query details, etc.)
- Errors (if any)

**Example File Log Entry**:
```
2025-10-30 10:15:23 | INFO | TIMING | Embedding Generation | 0.847s | {"dimension": 768}
2025-10-30 10:15:24 | INFO | TIMING | Pinecone Vector Search | 1.234s | {"results_count": 10, "filter_applied": true}
2025-10-30 10:15:25 | INFO | TIMING | MongoDB Data Retrieval | 0.523s | {"skus_requested": 10, "products_found": 8}
2025-10-30 10:15:27 | INFO | QUERY_LOG | {"timestamp": "2025-10-30T10:15:27", "query": "amber bottles", ...}
```

### QueryLog Structure

Comprehensive log for each complete query execution:

```python
@dataclass
class QueryLog:
    timestamp: str                      # When query was executed
    user_query: str                     # Original user query
    query_type: str                     # semantic_search/structured_query/hybrid
    intent: str                         # product_search/pricing_query/etc.
    retrieval_strategy: str             # Which databases were used
    timing_metrics: List[TimingMetrics] # All timing breakdowns
    pinecone_query: Optional[Dict]      # Pinecone query details
    mongodb_query: Optional[Dict]       # MongoDB query details
    results_count: int                  # Number of products found
    response_length: int                # Character length of response
    guardrail_checks: Dict[str, bool]   # Which guardrails passed
    total_time: float                   # Total query execution time
    errors: List[str]                   # Any errors encountered
```

### Export Logs

**Method**: `chatbot.export_logs("filename.json")`

Exports all query logs to JSON file for analysis, debugging, or monitoring.

---

## 3. Guardrail System

### GuardrailSystem Class

**Purpose**: Ensure chatbot stays strictly within its domain and only uses provided data

### Guardrail #1: Query Scope Check

**Method**: `check_query_scope(query, query_analysis)`

**Checks**:
- Is query related to product catalog?
- Is query type OUT_OF_SCOPE?

**Actions**:
- ✅ Pass: Continue with retrieval
- ❌ Fail: Return rejection message

**Example Rejection**:
```
"I'm a product catalog assistant specialized in glass bottles and jars. 
I can only help with product searches, pricing, specifications, and 
availability. Please ask me about our product catalog."
```

### Guardrail #2: Response Validation

**Method**: `validate_response(response, context)`

**Checks**:
- Are all product claims from the provided context?
- Are all prices directly from the context?
- Are there any fabricated details?
- Is the response relevant to the data?

**Process**:
1. Sends response + context to Gemini for validation
2. Gets validation report:
   ```json
   {
     "is_grounded": true/false,
     "issues": ["list of fabrications"],
     "confidence": "high/medium/low"
   }
   ```
3. Logs validation results
4. Flags responses with issues

### System Prompt Guardrails

The LLM system prompt includes strict rules:

```
STRICT RULES:
1. ONLY use information from the provided product context
2. Never fabricate or estimate data
3. If information is not in context, explicitly state "This information is not available"
4. Always cite specific product names, SKUs, and prices exactly as provided
5. Stay within the domain of product catalog assistance
6. For pricing, always specify the quantity tier
7. Include stock status when relevant
```

---

## Usage Examples

### Basic Usage

```python
from enhanced_chatbot import HybridRAGChatbot

# Initialize with verbose logging
chatbot = HybridRAGChatbot(verbose=True, log_file="my_logs.log")

# Query the chatbot
response = chatbot.query("I need amber bottles for essential oils around 30ml")
print(response)

# Export logs
chatbot.export_logs("query_analysis.json")
```

### Toggle Verbose Mode

```python
# Start without verbose
chatbot = HybridRAGChatbot(verbose=False)

# Enable verbose for debugging
chatbot.set_verbose(True)
response = chatbot.query("Show me wine bottles")

# Disable verbose
chatbot.set_verbose(False)
```

### Analyzing Logs

```python
import json

# Load exported logs
with open("query_logs.json", "r") as f:
    logs = json.load(f)

# Analyze performance
for log in logs:
    print(f"Query: {log['user_query']}")
    print(f"Total Time: {log['total_time']:.2f}s")
    print(f"Results: {log['results_count']}")
    print(f"Query Type: {log['query_type']}")
    print("Timing Breakdown:")
    for timing in log['timing_metrics']:
        print(f"  - {timing['operation']}: {timing['duration']:.3f}s")
    print()
```

---

## Key Improvements Summary

### 1. Query Routing
- ✅ Automatically detects if query needs vector search (Pinecone)
- ✅ Automatically detects if query needs structured filtering (MongoDB)
- ✅ Uses hybrid approach when both are needed
- ✅ Identifies out-of-scope queries

### 2. Logging & Timing
- ✅ Console logging when verbose=True
- ✅ File logging always active
- ✅ Tracks timing for: embedding generation, Pinecone search, MongoDB queries
- ✅ Comprehensive query logs with all details
- ✅ Export logs to JSON for analysis

### 3. Guardrails
- ✅ Scope check: Rejects non-product queries
- ✅ Response validation: Ensures responses are grounded in data
- ✅ System prompt constraints: LLM instructed to stay within data
- ✅ Explicit messaging when information is unavailable

---

## Log File Structure

### chatbot_activity.log

```
2025-10-30 10:15:20 | INFO | MongoDB Connection | 0.234s | {}
2025-10-30 10:15:21 | INFO | Pinecone Connection | 0.456s | {}
2025-10-30 10:15:23 | INFO | Query Analysis & Routing | 1.234s | {"query_type": "HYBRID", ...}
2025-10-30 10:15:23 | INFO | EMBEDDING | Generated in 0.847s | Dimension: 768
2025-10-30 10:15:24 | INFO | TIMING | Pinecone Vector Search | 1.234s | {"results_count": 10}
2025-10-30 10:15:25 | INFO | TIMING | MongoDB Data Retrieval | 0.523s | {"products_found": 8}
2025-10-30 10:15:26 | INFO | TIMING | Response Generation | 2.156s | {"response_length": 456}
2025-10-30 10:15:27 | INFO | QUERY_LOG | {...full query log JSON...}
```

### query_logs_export.json

```json
[
  {
    "timestamp": "2025-10-30T10:15:27",
    "user_query": "amber bottles for essential oils",
    "query_type": "SEMANTIC_SEARCH",
    "intent": "product_search",
    "retrieval_strategy": "Pinecone: True, MongoDB: True",
    "timing_metrics": [
      {
        "operation": "Query Analysis & Routing",
        "duration": 1.234,
        "details": {"query_type": "SEMANTIC_SEARCH"}
      },
      {
        "operation": "Pinecone Vector Search",
        "duration": 1.234,
        "details": {"results_count": 10}
      }
    ],
    "results_count": 8,
    "response_length": 456,
    "guardrail_checks": {
      "scope_check": true,
      "response_validation": true
    },
    "total_time": 5.678,
    "errors": []
  }
]
```

---

## Migration from Original Code

### Original Code
```python
chatbot = HybridRAGChatbot(verbose=True)
response = chatbot.query("Show me bottles")
```

### Enhanced Code
```python
# Same interface - fully backward compatible!
chatbot = HybridRAGChatbot(verbose=True, log_file="logs.log")
response = chatbot.query("Show me bottles")

# New feature: Export logs
chatbot.export_logs("analysis.json")
```

**No breaking changes** - the enhanced version maintains the same interface while adding new capabilities!

---

## Performance Monitoring

With the enhanced logging, you can now monitor:

1. **Query Routing Accuracy**: Are queries being routed correctly?
2. **Response Times**: Which operations are slowest?
3. **Guardrail Effectiveness**: How many queries are out of scope?
4. **Database Usage**: How often is each database used?
5. **Error Patterns**: What types of errors occur?

Example analysis:
```python
# Calculate average response times
avg_time = sum(log['total_time'] for log in logs) / len(logs)
print(f"Average query time: {avg_time:.2f}s")

# Count query types
query_types = {}
for log in logs:
    qt = log['query_type']
    query_types[qt] = query_types.get(qt, 0) + 1

print("Query type distribution:", query_types)
```

---

## Troubleshooting

### Verbose Mode Not Working
- Check: `chatbot.logger.verbose` should be `True`
- Check: Console logger level should be `DEBUG`

### Logs Not Being Written
- Check: File permissions for log file
- Check: Log file path is valid

### Guardrails Too Strict
- Adjust validation prompts in `GuardrailSystem`
- Review rejection messages

### Slow Performance
- Check timing metrics to identify bottleneck
- Consider reducing `top_k` for Pinecone
- Consider indexing MongoDB fields
