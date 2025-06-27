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
    
    # FIX 1: Remove placeholders and use actual names
    assistant = ConversableAgent(
        name="EcommerceAssistant",
        system_message=(
            """You are a sophisticated E-commerce Assistant named 'EcommerceAssistant'.
Your role is to understand instructions from 'QueryAnalyzer' and use available tools.

Available Tools: get_conversation_context, log_conversation, search_amazon_products, amazon_product_reviews, search_walmart_products, walmart_product_reviews.

**Workflow Logic:**

1. **Receive Instruction from QueryAnalyzer:**
   - If instruction contains "get context first": Call get_conversation_context with the user query and session ID
   - If instruction is direct (e.g., "search for laptops"): Call the appropriate search tool directly

2. **After receiving tool results:**
   - If context was retrieved: Use context + original query to make the product search
   - If product search was successful: Call log_conversation to save the interaction
   - Provide final results to ResponseFormatter

3. **Output Rules:**
   - For tool calls: Respond ONLY with the tool_calls JSON
   - For final results: Provide concise summary without using TERMINATE"""
        ),
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    
    user_proxy = ConversableAgent(
        name="ToolExecutor",
        llm_config=False,
        is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"],
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
    )
    
    return assistant, user_proxy


# FIX 2: Add error handling and logging to tool functions
def get_conversation_context(
    query: Annotated[str, "The user query to search context for"], 
    session_id: Annotated[str, "The session ID to retrieve context from"]
) -> str:
    """Get conversation context from RAG memory"""
    try:
        logger.info(f"[CONTEXT] Fetching context for query: {query[:50]}... session: {session_id}")
        context = query_context_from_memory(query, session_id)
        
        if not context or context.strip() == "":
            logger.info(f"[CONTEXT] No context found for session: {session_id}")
            return "No previous conversation context found."
        
        logger.info(f"[CONTEXT] Retrieved {len(context)} chars of context")
        return f"Previous context:\n{context}"
        
    except Exception as e:
        logger.error(f"[CONTEXT] Error getting context: {str(e)}")
        return f"Error retrieving context: {str(e)}"


def log_conversation(user_query: str, assistant_response: str, session_id: str):
    """
    Logs the user query and assistant response to the vector DB for RAG context.
    """
    try:
        full_entry = f"User: {user_query.strip()}\nAgent: {assistant_response.strip()}"
        timestamp = time.time()

        collection = chroma_client.get_or_create_collection(name=f"user_session_{session_id}")
        collection.add(
            documents=[full_entry],
            metadatas=[{"timestamp": timestamp}],
            ids=[str(uuid.uuid4())]
        )

        logger.info(f"[LOG] Logged conversation for session {session_id}")
        return "Conversation successfully logged."
    except Exception as e:
        logger.error(f"[LOG] Failed to log conversation: {e}")
        return f"Error logging conversation: {e}"



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
            return [{"message": "No Amazon products found", "keyword": keyword}]
        
        logger.info(f"[AMAZON] Found {len(results)} products")
        return results
        
    except Exception as e:
        logger.error(f"[AMAZON] Search error: {str(e)}")
        return [{"error": f"Amazon search failed: {str(e)}", "keyword": keyword}]


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
            return [{"message": "No reviews found", "asin": asin}]
        
        logger.info(f"[AMAZON REVIEWS] Found {len(results)} reviews")
        return results
        
    except Exception as e:
        logger.error(f"[AMAZON REVIEWS] Error: {str(e)}")
        return [{"error": f"Failed to get reviews: {str(e)}", "asin": asin}]


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
            return [{"message": "No Walmart products found", "keyword": keyword}]
        
        logger.info(f"[WALMART] Found {len(results)} products")
        return results
        
    except Exception as e:
        logger.error(f"[WALMART] Search error: {str(e)}")
        return [{"error": f"Walmart search failed: {str(e)}", "keyword": keyword}]


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
            return [{"message": "No reviews found", "us_item_id": us_item_id}]
        
        logger.info(f"[WALMART REVIEWS] Found {len(results)} reviews")
        return results
        
    except Exception as e:
        logger.error(f"[WALMART REVIEWS] Error: {str(e)}")
        return [{"error": f"Failed to get reviews: {str(e)}", "us_item_id": us_item_id}]


def register_all_tools(assistant: ConversableAgent, user_proxy: ConversableAgent):
    """Register all tools with both agents using official AutoGen approach"""
    
    tools = [
        (get_conversation_context, "Get previous conversation context from memory"),
        (log_conversation, "Log conversation to memory for future reference"),
        (search_amazon_products, "Search for products on Amazon with keyword and limit"),
        (amazon_product_reviews, "Get reviews for Amazon products using ASIN"),
        (search_walmart_products, "Search for products on Walmart with keyword and limit"),
        (walmart_product_reviews, "Get reviews for Walmart products using item ID"),
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
    
    logger.info("[TOOLS] All tools registration completed")
    
    # FIX 3: Verify tools are actually registered
    if hasattr(user_proxy, '_function_map'):
        registered_tools = list(user_proxy._function_map.keys())
        logger.info(f"[TOOLS] Executor has tools: {registered_tools}")
    else:
        logger.warning("[TOOLS] No function map found on executor")


def create_ecommerce_agents(llm_config: Dict):
    """Main function to create and configure e-commerce agents"""
    logger.info("[SETUP] Creating ecommerce agents...")
    
    assistant, user_proxy = setup_agents(llm_config)
    register_all_tools(assistant, user_proxy)
    
    logger.info(f"[SETUP] Created assistant: {assistant.name}")
    logger.info(f"[SETUP] Created executor: {user_proxy.name}")
    
    return assistant, user_proxy