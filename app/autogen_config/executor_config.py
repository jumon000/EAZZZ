import os
import logging
from typing import Dict, List, Any, Annotated
from datetime import datetime
import autogen
from autogen import ConversableAgent, register_function
import uuid
import time
import logging
from app.db.RAG_db import chroma_client
from app.services.amazon_search_service import AmazonService
from app.services.walmart_search_service import WalmartService
from app.services.RAG_service import query_context_from_memory
from app.db.RAG_db import log_session_interaction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_agents(llm_config: Dict):
    """Setup assistant and executor agents following official AutoGen patterns"""
    
    assistant = ConversableAgent(
        name="EcommerceAssistant",
        system_message=(
            """You are a sophisticated E-commerce Assistant named 'EcommerceAssistant'.
Your role is to understand instructions from 'QueryAnalyzer' and use available tools.

Available Tools: 
- search_amazon_products, amazon_product_reviews, search_walmart_products, walmart_product_reviews
- filter_amazon_products, filter_walmart_products (for advanced filtering)
- amazon_product_descriptions_by_keyword, walmart_product_descriptions_by_keyword (for detailed product info)
- get_product_reviews_from_both_platforms, get_product_descriptions_from_both_platforms (for comprehensive comparison)
- search_products_from_both_platforms (for cross-platform search)

**Tool Usage Guidelines:**
- Use basic search tools (search_amazon_products, search_walmart_products) for simple product searches
- Use filter tools when users specify criteria like price range, ratings, brand, etc.
- Use description tools when users want detailed product information, features, or specifications
- Use review tools when users want customer feedback and opinions
- Use cross-platform tools when users want to compare products across Amazon and Walmart
- Use both_platforms tools when users want comprehensive information from both sources

**CRITICAL: Always make tool calls in the correct order and format**

**Important Notes:**
- Context will be retrieved by ContextAgent before you are called
- Logging will be handled by LoggingAgent after ResponseFormatter
- Focus only on e-commerce search, review, and comparison tools
- Always make the minimum required tool calls based on instructions

**IMPORTANT:** Make sure every tool call has a unique ID and proper structure."""
        ),
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    
    # Use standard ConversableAgent as executor - this is the key fix
    user_proxy = ConversableAgent(
        name="ToolExecutor",
        llm_config=False,  # No LLM for executor
        is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"],
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        code_execution_config=False,  # Disable code execution
    )
    
    return assistant, user_proxy


def search_amazon_products(
    keyword: Annotated[str, "The search keyword for Amazon products"], 
    limit: Annotated[int, "Number of products to return (1-10)"] = 3
) -> List[Dict]:
    """Search for products on Amazon"""
    try:
        if not keyword.strip():
            return [{"error": "Keyword cannot be empty"}]
        
        limit = max(1, min(limit, 10))
        logger.info(f"[AMAZON] Searching: {keyword} (limit: {limit})")
        
        results = AmazonService.get_top_products(keyword.strip(), limit)
        
        if not results:
            logger.info(f"[AMAZON] No products found for: {keyword}")
            return [{"message": "No Amazon products found", "keyword": keyword, "platform": "Amazon"}]
        
        # Add platform identifier to each result
        for result in results:
            result["platform"] = "Amazon"
        
        logger.info(f"[AMAZON] Found {len(results)} products")
        return results
        
    except Exception as e:
        logger.error(f"[AMAZON] Search error: {str(e)}")
        return [{"error": f"Amazon search failed: {str(e)}", "keyword": keyword, "platform": "Amazon"}]


def filter_amazon_products(
    keyword: Annotated[str, "The search keyword for Amazon products"],
    filters: Annotated[Dict, "Filter criteria (e.g., {'price_min': 10, 'price_max': 100, 'rating_min': 4})"],
    limit: Annotated[int, "Number of products to return (1-10)"] = 3
) -> List[Dict]:
    """Filter Amazon products by keyword and specific criteria like price, rating, brand"""
    try:
        if not keyword.strip():
            return [{"error": "Keyword cannot be empty"}]
        
        limit = max(1, min(limit, 10))
        logger.info(f"[AMAZON FILTER] Searching: {keyword} with filters: {filters} (limit: {limit})")
        
        results = AmazonService.get_filtered_products(keyword.strip(), filters, limit)
        
        if not results:
            logger.info(f"[AMAZON FILTER] No products found for: {keyword} with filters: {filters}")
            return [{"message": "No Amazon products found with specified filters", "keyword": keyword, "filters": filters, "platform": "Amazon"}]
        
        # Add platform identifier to each result
        for result in results:
            result["platform"] = "Amazon"
        
        logger.info(f"[AMAZON FILTER] Found {len(results)} filtered products")
        return results
        
    except Exception as e:
        logger.error(f"[AMAZON FILTER] Search error: {str(e)}")
        return [{"error": f"Amazon filtered search failed: {str(e)}", "keyword": keyword, "filters": filters, "platform": "Amazon"}]


def amazon_product_reviews(
    asin: Annotated[str, "The Amazon ASIN (product identifier) to get reviews for"], 
    limit: Annotated[int, "Number of reviews to return (1-20)"] = 5
) -> List[Dict]:
    """Get reviews for an Amazon product"""
    try:
        if not asin.strip():
            return [{"error": "ASIN cannot be empty"}]
        
        logger.info(f"[AMAZON REVIEWS] Getting reviews for: {asin}")
        results = AmazonService._get_product_reviews(asin.strip())
        
        if results and len(results) > limit:
            results = results[:limit]
        
        if not results:
            return [{"message": "No reviews found", "asin": asin, "platform": "Amazon"}]
        
        # Add platform identifier
        for result in results:
            result["platform"] = "Amazon"
        
        logger.info(f"[AMAZON REVIEWS] Found {len(results)} reviews")
        return results
        
    except Exception as e:
        logger.error(f"[AMAZON REVIEWS] Error: {str(e)}")
        return [{"error": f"Failed to get reviews: {str(e)}", "asin": asin, "platform": "Amazon"}]


def amazon_product_descriptions_by_keyword(
    keyword: Annotated[str, "The search keyword for Amazon products"],
    product_limit: Annotated[int, "Number of products to get descriptions for (1-5)"] = 2
) -> List[Dict]:
    """Get detailed descriptions for Amazon products based on keyword search"""
    try:
        if not keyword.strip():
            return [{"error": "Keyword cannot be empty"}]
        
        product_limit = max(1, min(product_limit, 5))
        logger.info(f"[AMAZON DESCRIPTIONS] Getting descriptions for: {keyword} (limit: {product_limit})")
        
        results = AmazonService.get_product_descriptions_by_keyword(keyword.strip(), product_limit)
        
        if not results:
            logger.info(f"[AMAZON DESCRIPTIONS] No product descriptions found for: {keyword}")
            return [{"message": "No Amazon product descriptions found", "keyword": keyword, "platform": "Amazon"}]
        
        # Add platform identifier to each result
        for result in results:
            result["platform"] = "Amazon"
        
        logger.info(f"[AMAZON DESCRIPTIONS] Found {len(results)} product descriptions")
        return results
        
    except Exception as e:
        logger.error(f"[AMAZON DESCRIPTIONS] Error: {str(e)}")
        return [{"error": f"Failed to get product descriptions: {str(e)}", "keyword": keyword, "platform": "Amazon"}]


def search_walmart_products(
    keyword: Annotated[str, "The search keyword for Walmart products"], 
    limit: Annotated[int, "Number of products to return (1-10)"] = 3
) -> List[Dict]:
    """Search for products on Walmart"""
    try:
        if not keyword.strip():
            return [{"error": "Keyword cannot be empty"}]
        
        limit = max(1, min(limit, 10))
        logger.info(f"[WALMART] Searching: {keyword} (limit: {limit})")
        
        results = WalmartService.get_top_products(keyword.strip(), limit)
        
        if not results:
            logger.info(f"[WALMART] No products found for: {keyword}")
            return [{"message": "No Walmart products found", "keyword": keyword, "platform": "Walmart"}]
        
        # Add platform identifier to each result
        for result in results:
            result["platform"] = "Walmart"
        
        logger.info(f"[WALMART] Found {len(results)} products")
        return results
        
    except Exception as e:
        logger.error(f"[WALMART] Search error: {str(e)}")
        return [{"error": f"Walmart search failed: {str(e)}", "keyword": keyword, "platform": "Walmart"}]


def filter_walmart_products(
    keyword: Annotated[str, "The search keyword for Walmart products"],
    filters: Annotated[Dict, "Filter criteria (e.g., {'price_min': 10, 'price_max': 100, 'rating_min': 4})"]
) -> List[Dict]:
    """Filter Walmart products by keyword and specific criteria like price, rating, brand"""
    try:
        if not keyword.strip():
            return [{"error": "Keyword cannot be empty"}]
        
        logger.info(f"[WALMART FILTER] Searching: {keyword} with filters: {filters}")
        
        results = WalmartService.get_filtered_products(keyword.strip(), filters)
        
        if not results:
            logger.info(f"[WALMART FILTER] No products found for: {keyword} with filters: {filters}")
            return [{"message": "No Walmart products found with specified filters", "keyword": keyword, "filters": filters, "platform": "Walmart"}]
        
        # Add platform identifier to each result
        for result in results:
            result["platform"] = "Walmart"
        
        logger.info(f"[WALMART FILTER] Found {len(results)} filtered products")
        return results
        
    except Exception as e:
        logger.error(f"[WALMART FILTER] Search error: {str(e)}")
        return [{"error": f"Walmart filtered search failed: {str(e)}", "keyword": keyword, "filters": filters, "platform": "Walmart"}]


def walmart_product_reviews(
    us_item_id: Annotated[str, "The Walmart item ID to get reviews for"], 
    limit: Annotated[int, "Number of reviews to return (1-20)"] = 5
) -> List[Dict]:
    """Get reviews for a Walmart product"""
    try:
        if not us_item_id.strip():
            return [{"error": "Item ID cannot be empty"}]
        
        logger.info(f"[WALMART REVIEWS] Getting reviews for: {us_item_id}")
        results = WalmartService._get_product_reviews(us_item_id.strip())
        
        if results and len(results) > limit:
            results = results[:limit]
        
        if not results:
            return [{"message": "No reviews found", "us_item_id": us_item_id, "platform": "Walmart"}]
        
        # Add platform identifier
        for result in results:
            result["platform"] = "Walmart"
        
        logger.info(f"[WALMART REVIEWS] Found {len(results)} reviews")
        return results
        
    except Exception as e:
        logger.error(f"[WALMART REVIEWS] Error: {str(e)}")
        return [{"error": f"Failed to get reviews: {str(e)}", "us_item_id": us_item_id, "platform": "Walmart"}]


def walmart_product_descriptions_by_keyword(
    keyword: Annotated[str, "The search keyword for Walmart products"],
    product_limit: Annotated[int, "Number of products to get descriptions for (1-5)"] = 2
) -> List[Dict]:
    """Get detailed descriptions for Walmart products based on keyword search"""
    try:
        if not keyword.strip():
            return [{"error": "Keyword cannot be empty"}]
        
        product_limit = max(1, min(product_limit, 5))
        logger.info(f"[WALMART DESCRIPTIONS] Getting descriptions for: {keyword} (limit: {product_limit})")
        
        results = WalmartService.get_product_descriptions_by_keyword(keyword.strip(), product_limit)
        
        if not results:
            logger.info(f"[WALMART DESCRIPTIONS] No product descriptions found for: {keyword}")
            return [{"message": "No Walmart product descriptions found", "keyword": keyword, "platform": "Walmart"}]
        
        # Add platform identifier to each result
        for result in results:
            result["platform"] = "Walmart"
        
        logger.info(f"[WALMART DESCRIPTIONS] Found {len(results)} product descriptions")
        return results
        
    except Exception as e:
        logger.error(f"[WALMART DESCRIPTIONS] Error: {str(e)}")
        return [{"error": f"Failed to get product descriptions: {str(e)}", "keyword": keyword, "platform": "Walmart"}]


def get_product_reviews_from_both_platforms(
    keyword: Annotated[str, "The search keyword for products on both platforms"],
    product_limit: Annotated[int, "Number of products per platform to get reviews for (1-3)"] = 2
) -> Dict[str, Any]:
    """Get reviews from both Amazon and Walmart for comparison"""
    try:
        if not keyword.strip():
            return {"error": "Keyword cannot be empty"}
        
        product_limit = max(1, min(product_limit, 3))
        logger.info(f"[BOTH PLATFORMS REVIEWS] Getting reviews for: {keyword} (limit: {product_limit} per platform)")
        
        amazon_reviews = AmazonService.get_product_reviews_by_keyword(keyword.strip(), product_limit)
        walmart_reviews = WalmartService.get_product_reviews_by_keyword(keyword.strip(), product_limit)
        
        # Add platform identifiers
        if amazon_reviews:
            for review in amazon_reviews:
                if isinstance(review, dict):
                    review["platform"] = "Amazon"
        
        if walmart_reviews:
            for review in walmart_reviews:
                if isinstance(review, dict):
                    review["platform"] = "Walmart"
        
        result = {
            "keyword": keyword,
            "amazon_reviews": amazon_reviews or [],
            "walmart_reviews": walmart_reviews or [],
            "comparison_summary": {
                "amazon_review_count": len(amazon_reviews) if amazon_reviews else 0,
                "walmart_review_count": len(walmart_reviews) if walmart_reviews else 0
            }
        }
        
        logger.info(f"[BOTH PLATFORMS REVIEWS] Found {len(amazon_reviews or [])} Amazon reviews and {len(walmart_reviews or [])} Walmart reviews")
        return result
        
    except Exception as e:
        logger.error(f"[BOTH PLATFORMS REVIEWS] Error: {str(e)}")
        return {"error": f"Failed to get reviews from both platforms: {str(e)}", "keyword": keyword}


def get_product_descriptions_from_both_platforms(
    keyword: Annotated[str, "The search keyword for products on both platforms"],
    product_limit: Annotated[int, "Number of products per platform to get descriptions for (1-3)"] = 2
) -> Dict[str, Any]:
    """Get detailed descriptions from both Amazon and Walmart for comparison"""
    try:
        if not keyword.strip():
            return {"error": "Keyword cannot be empty"}
        
        product_limit = max(1, min(product_limit, 3))
        logger.info(f"[BOTH PLATFORMS DESCRIPTIONS] Getting descriptions for: {keyword} (limit: {product_limit} per platform)")
        
        amazon_descriptions = AmazonService.get_product_descriptions_by_keyword(keyword.strip(), product_limit)
        walmart_descriptions = WalmartService.get_product_descriptions_by_keyword(keyword.strip(), product_limit)
        
        # Add platform identifiers
        if amazon_descriptions:
            for desc in amazon_descriptions:
                if isinstance(desc, dict):
                    desc["platform"] = "Amazon"
        
        if walmart_descriptions:
            for desc in walmart_descriptions:
                if isinstance(desc, dict):
                    desc["platform"] = "Walmart"
        
        result = {
            "keyword": keyword,
            "amazon_descriptions": amazon_descriptions or [],
            "walmart_descriptions": walmart_descriptions or [],
            "comparison_summary": {
                "amazon_product_count": len(amazon_descriptions) if amazon_descriptions else 0,
                "walmart_product_count": len(walmart_descriptions) if walmart_descriptions else 0
            }
        }
        
        logger.info(f"[BOTH PLATFORMS DESCRIPTIONS] Found {len(amazon_descriptions or [])} Amazon descriptions and {len(walmart_descriptions or [])} Walmart descriptions")
        return result
        
    except Exception as e:
        logger.error(f"[BOTH PLATFORMS DESCRIPTIONS] Error: {str(e)}")
        return {"error": f"Failed to get descriptions from both platforms: {str(e)}", "keyword": keyword}


def search_products_from_both_platforms(
    keyword: Annotated[str, "The search keyword for products on both platforms"],
    limit: Annotated[int, "Number of products per platform to return (1-5)"] = 2
) -> Dict[str, Any]:
    """Search for products from both Amazon and Walmart for comparison"""
    try:
        if not keyword.strip():
            return {"error": "Keyword cannot be empty"}
        
        limit = max(1, min(limit, 5))
        logger.info(f"[BOTH PLATFORMS SEARCH] Searching: {keyword} (limit: {limit} per platform)")
        
        amazon_products = AmazonService.get_top_products(keyword.strip(), limit)
        walmart_products = WalmartService.get_top_products(keyword.strip(), limit)
        
        # Add platform identifiers
        if amazon_products:
            for product in amazon_products:
                if isinstance(product, dict):
                    product["platform"] = "Amazon"
        
        if walmart_products:
            for product in walmart_products:
                if isinstance(product, dict):
                    product["platform"] = "Walmart"
        
        result = {
            "keyword": keyword,
            "amazon_products": amazon_products or [],
            "walmart_products": walmart_products or [],
            "comparison_summary": {
                "amazon_product_count": len(amazon_products) if amazon_products else 0,
                "walmart_product_count": len(walmart_products) if walmart_products else 0,
                "total_products": (len(amazon_products) if amazon_products else 0) + (len(walmart_products) if walmart_products else 0)
            }
        }
        
        logger.info(f"[BOTH PLATFORMS SEARCH] Found {len(amazon_products or [])} Amazon products and {len(walmart_products or [])} Walmart products")
        return result
        
    except Exception as e:
        logger.error(f"[BOTH PLATFORMS SEARCH] Error: {str(e)}")
        return {"error": f"Failed to search both platforms: {str(e)}", "keyword": keyword}


# Tool functions for agent-based context and logging
def get_conversation_context(
    query: Annotated[str, "The user query to search context for"], 
    session_id: Annotated[str, "The session ID to retrieve context from"]
) -> Dict[str, Any]:
    """Get conversation context from RAG memory"""
    try:
        logger.info(f"[CONTEXT] Fetching context for query: {query[:50]}... session: {session_id}")
        
        if not session_id or session_id.strip() == "":
            logger.warning("[CONTEXT] No session ID provided")
            return {"error": "No session ID provided for context retrieval."}
        
        context = query_context_from_memory(query, session_id)
        
        if not context or context.strip() == "":
            logger.info(f"[CONTEXT] No context found for session: {session_id}")
            return {"message": "No previous conversation context found.", "session_id": session_id}
        
        logger.info(f"[CONTEXT] Retrieved {len(context)} chars of context")
        return {"context": context, "session_id": session_id, "status": "success"}
        
    except Exception as e:
        logger.error(f"[CONTEXT] Error getting context: {str(e)}")
        return {"error": f"Error retrieving context: {str(e)}", "session_id": session_id}


def log_conversation(
    user_query: Annotated[str, "The user query to log"], 
    assistant_response: Annotated[str, "The assistant response to log"], 
    session_id: Annotated[str, "The session ID to log conversation for"]
) -> Dict[str, Any]:
    """
    Logs the user query and assistant response to the vector DB for RAG context using the internal session logger.
    """
    try:
        if not session_id or session_id.strip() == "":
            return {"error": "No session ID provided for logging.", "status": "failed"}
        if not user_query.strip() or not assistant_response.strip():
            return {"error": "Empty query or response provided.", "status": "failed"}
        
        log_session_interaction(user_query, assistant_response, session_id)
        return {"message": f"Conversation successfully logged for session {session_id}.", "status": "success"}

    except Exception as e:
        return {"error": f"Error logging conversation: {e}", "status": "failed"}


def register_ecommerce_tools(assistant: ConversableAgent, user_proxy: ConversableAgent):
    """Register e-commerce tools with agents"""

    # Clear existing function maps to prevent override warnings
    if hasattr(assistant, '_function_map'):
        assistant._function_map.clear()
        logger.info("[TOOLS] Cleared assistant function map")
    
    if hasattr(user_proxy, '_function_map'):
        user_proxy._function_map.clear()
        logger.info("[TOOLS] Cleared executor function map")
    
    tools = [
        # Basic search tools
        (search_amazon_products, "Search for products on Amazon with keyword and limit"),
        (search_walmart_products, "Search for products on Walmart with keyword and limit"),
        
        # Advanced filtering tools
        (filter_amazon_products, "Filter Amazon products by keyword and specific criteria (price, rating, brand)"),
        (filter_walmart_products, "Filter Walmart products by keyword and specific criteria (price, rating, brand)"),
        
        # Review tools
        (amazon_product_reviews, "Get reviews for Amazon products using ASIN"),
        (walmart_product_reviews, "Get reviews for Walmart products using item ID"),
        
        # Description tools
        (amazon_product_descriptions_by_keyword, "Get detailed descriptions for Amazon products by keyword"),
        (walmart_product_descriptions_by_keyword, "Get detailed descriptions for Walmart products by keyword"),
        
        # Cross-platform comparison tools
        (get_product_reviews_from_both_platforms, "Get reviews from both Amazon and Walmart for comparison"),
        (get_product_descriptions_from_both_platforms, "Get detailed descriptions from both platforms for comparison"),
        (search_products_from_both_platforms, "Search for products from both Amazon and Walmart for comparison"),
    ]
    
    for tool_func, description in tools:
        try:
            register_function(
                tool_func,
                caller=assistant,
                executor=user_proxy,
                name=tool_func.__name__,
                description=description,
            )
            logger.info(f"[TOOLS] Registered: {tool_func.__name__}")
        except Exception as e:
            logger.error(f"[TOOLS] Failed to register {tool_func.__name__}: {str(e)}")
    
    logger.info("[TOOLS] E-commerce tools registration completed")
    

    if hasattr(user_proxy, '_function_map'):
        registered_tools = list(user_proxy._function_map.keys())
        logger.info(f"[TOOLS] Executor has tools: {registered_tools}")
    else:
        logger.warning("[TOOLS] No function map found on executor")


def create_ecommerce_agents(llm_config: Dict):
    """Main function to create and configure e-commerce agents"""
    logger.info("[SETUP] Creating ecommerce agents...")
    
    assistant, user_proxy = setup_agents(llm_config)
    register_ecommerce_tools(assistant, user_proxy)
    
    logger.info(f"[SETUP] Created assistant: {assistant.name}")
    logger.info(f"[SETUP] Created executor: {user_proxy.name}")
    
    return assistant, user_proxy