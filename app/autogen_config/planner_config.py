import os
import json
import logging
from typing import Dict, List, Any, Optional, Sequence, cast
import autogen
from autogen import ConversableAgent, GroupChat, GroupChatManager, Agent, register_function
from autogen.agentchat.user_proxy_agent import UserProxyAgent
from app.autogen_config.executor_config import create_ecommerce_agents, get_conversation_context, log_conversation
from dotenv import load_dotenv
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

class ContextAgent(ConversableAgent):
    """Agent responsible for retrieving conversation context using get_conversation_context tool"""

    def __init__(self, name="ContextAgent", **kwargs):
        super().__init__(
            name=name,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=2,
            **kwargs
        )

    def generate_reply(self, messages: Optional[List[Dict]] = None, sender: Optional[Agent] = None, **kwargs):
        if messages is None and isinstance(sender, GroupChatManager):
            messages = sender.groupchat.messages

        if messages is None or not messages:
            logger.error("ContextAgent received no messages.")
            return {"content": "TERMINATE - Error: No messages received for context retrieval."}

        last_message = messages[-1]
        content = last_message.get("content", "")
        
        if "USER_QUERY:" in str(content) and "SESSION_ID:" in str(content):
            session_id = self._extract_session_id_from_content(content)
            query = self._extract_query_from_content(content)
            
            if session_id == "unknown_session" or query == "Unknown query":
                logger.error(f"ContextAgent could not extract session_id or query.")
                return {"content": "TERMINATE - Error: Could not extract session information."}

            logger.info(f"ContextAgent calling get_conversation_context for session: {session_id}")
            
            tool_call_message = {
                "tool_calls": [
                    {
                        "id": str(uuid.uuid4()),
                        "type": "function",  # FIX: Added required 'type' field
                        "function": {
                            "name": "get_conversation_context",
                            "arguments": json.dumps({
                                "query": query,
                                "session_id": session_id
                            })
                        }
                    }
                ],
                "role": "assistant",
                "content": None
            }
            
            return tool_call_message
            
        elif last_message.get("role") in ['function', 'tool']:
            tool_result = last_message.get("content", "")
            original_query = self._extract_original_query_from_messages(messages)
            
            try:
                if isinstance(tool_result, str) and tool_result.startswith('{'):
                    result_dict = json.loads(tool_result)
                    context = result_dict.get("context", "No previous conversation context found.")
                else:
                    context = "No previous conversation context found."
            except:
                context = "No previous conversation context found."
            
            formatted_response = f"""**Previous Conversation Context:**
{context}

**User Query to Analyze:**
{original_query}"""
            
            return {"content": formatted_response, "role": "user"}
        
        else:
            logger.error(f"ContextAgent received unexpected message type.")
            return {"content": "TERMINATE - Error: Unexpected input for context agent."}
    
    def _extract_session_id_from_content(self, content: str) -> str:
        try:
            return content.split("SESSION_ID:")[1].strip().split()[0]
        except:
            return "unknown_session"
    
    def _extract_query_from_content(self, content: str) -> str:
        try:
            query_part = content.split("USER_QUERY:")[1].split("SESSION_ID:")[0].strip()
            return query_part.strip('"')
        except:
            return "Unknown query"
    
    def _extract_original_query_from_messages(self, messages: List[Dict]) -> str:
        for message in reversed(messages):
            content = message.get("content", "")
            if isinstance(content, str) and "USER_QUERY:" in content:
                try:
                    query_part = content.split("USER_QUERY:")[1].split("SESSION_ID:")[0].strip()
                    return query_part.strip('"')
                except:
                    continue
        return "Unknown query"


class LoggingAgent(ConversableAgent):
    """Agent responsible for calling the log_conversation tool and terminating."""
    
    def __init__(self, name="LoggingAgent", **kwargs):
        super().__init__(
            name=name,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=2,
            **kwargs
        )

    def generate_reply(self, messages: Optional[List[Dict]] = None, sender: Optional[Agent] = None, **kwargs):
        if messages is None and isinstance(sender, GroupChatManager):
            messages = sender.groupchat.messages

        if messages is None or not messages:
            logger.error("LoggingAgent received no messages.")
            return {"content": "TERMINATE - Error: No messages received for logging."}

        last_message = messages[-1]
        role = last_message.get("role")
        last_speaker_name = last_message.get("name")
        formatted_response = last_message.get("content")

        if last_speaker_name in ["ResponseFormatter", "GeneralAssistant"] and not last_message.get("tool_calls"):

            if not isinstance(formatted_response, str) or not formatted_response.strip() or "TERMINATE" in formatted_response.upper():
                response_preview = str(formatted_response)[:100]
                logger.error(f"LoggingAgent received invalid response for logging from {last_speaker_name}. Content: {response_preview}")
                return {"content": f"TERMINATE - Error: Received invalid response format for logging."}

            logger.info(f"LoggingAgent received final response text from {last_speaker_name}, attempting to call log_conversation.")

            session_id = EcommerceAssistant._extract_session_id_from_messages_static(messages)
            original_query = EcommerceAssistant._extract_original_query_from_messages_static(messages)

            if session_id == "unknown_session" or original_query == "Unknown query":
                logger.error(f"LoggingAgent could not extract session_id or original_query from history.")
                return {"content": "TERMINATE - Error: Could not log due to missing session/query info."}

            tool_call_message = {
                "tool_calls": [
                    {
                        "id": str(uuid.uuid4()),
                        "type": "function",  # FIX: Added required 'type' field
                        "function": {
                            "name": "log_conversation",
                            "arguments": json.dumps({
                                "user_query": original_query,
                                "assistant_response": formatted_response,
                                "session_id": session_id
                            })
                        }
                    }
                ],
                "role": "assistant",
                "content": None
            }

            logger.info(f"LoggingAgent generating log_conversation tool call message.")
            return tool_call_message

        elif role in ['function', 'tool']:
            logger.info("LoggingAgent received log result, generating TERMINATE.")
            return {"content": "TERMINATE"}

        else:
            content_preview = str(formatted_response)[:100]
            logger.error(f"LoggingAgent received unexpected message from '{last_speaker_name}' with role '{role}'. Content: {content_preview}")
            return {"content": "TERMINATE - Error: Received unexpected input."}


class EcommerceAssistant:
    def __init__(self):
        self.llm_config = {
            "config_list": [
                {
                    "model": os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo"),
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "api_type": "openai",
                }
            ],
            "temperature": 0.3,
            "max_tokens": 2048
        }

        self._setup_agents()
        self._setup_group_chat()

    def _setup_agents(self):
        # Create e-commerce agents (search and review tools)
        self.ecommerce_assistant, self.tool_executor = create_ecommerce_agents(self.llm_config.copy())

        self.ecommerce_assistant.update_system_message(
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

**CRITICAL: Your final message MUST ONLY contain the tool calls JSON and NOT include any text explanation or conversational filler.**
**CRITICAL: Ensure the role of your message is 'assistant'.**
"""
        )

        logger.info(f"Tool Proposing Agent created with name: {self.ecommerce_assistant.name}")
        logger.info(f"Tool Executing Agent created with name: {self.tool_executor.name}")

        # Create context agent with tool capability
        self.context_agent = ContextAgent(
            name="ContextAgent",
            llm_config=self.llm_config.copy(),
            system_message="""You are the ContextAgent responsible for retrieving conversation context using get_conversation_context tool.
You receive the initial user message and extract session_id and query to call get_conversation_context.
After receiving the tool result, format it properly for QueryAnalyzer.
Do NOT add any other text, explanations, or hypothetical examples. Do NOT output TERMINATE.
Ensure the role of your response message is 'user' when passing to QueryAnalyzer."""
        )

        self.query_analyzer = ConversableAgent(
            name="QueryAnalyzer",
            llm_config=self.llm_config.copy(),
            system_message="""You are the QueryAnalyzer. Analyze user queries with the context provided by ContextAgent and provide instructions.
**CRITICAL: If the context is "No previous conversation context found.", rely SOLELY on the "User Query to Analyze" to determine the instruction. Do not invent context.**
Respond ONLY with the exact instruction format (e.g., "EcommerceAssistant, search for '[product]'...").
Do NOT add any other text, explanations, or questions. Do NOT output TERMINATE.
Ensure the role of your message is 'user'.""",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
        )

        self.response_formatter = ConversableAgent(
            name="ResponseFormatter",
            llm_config=self.llm_config.copy(),
            system_message="""You are the ResponseFormatter. Format tool results into user-friendly responses.
**CRITICAL: Your response MUST contain ONLY the formatted text and NOTHING else.**
Do NOT call any tools, include TERMINATE, or add conversational filler after the formatted response.
Ensure the role of your message is 'assistant'. The LoggingAgent will pick up this text.""",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
        )

        # Create logging agent with tool capability
        self.logging_agent = LoggingAgent(name="LoggingAgent", llm_config=self.llm_config.copy())

        self.general_assistant = ConversableAgent(
            name="GeneralAssistant",
            llm_config=self.llm_config.copy(),
            system_message="""You are the GeneralAssistant for general shopping questions.
**CRITICAL: Your response MUST contain ONLY the text content and NOTHING else.**
After generating your response, provide *only* the text content. The LoggingAgent will pick up this text.
Ensure the role of your message is 'assistant'.
Do NOT output TERMINATE yourself or call any tools.""",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
        )

        self.user_proxy = ConversableAgent(
            name="UserProxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            llm_config=False,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            system_message="A human user representation that initiates the conversation and listens for TERMINATE."
        )

        self._register_tools()

    def _setup_group_chat(self):
        agents_list: List[Agent] = [
            self.user_proxy,
            self.context_agent,
            self.query_analyzer,
            self.ecommerce_assistant,
            self.tool_executor,
            self.response_formatter,
            self.general_assistant,
            self.logging_agent,
        ]

        self.group_chat = GroupChat(
            agents=agents_list,
            messages=[],
            max_round=40,
            speaker_selection_method=self.custom_speaker_selection_func,
            allow_repeat_speaker=True
        )

        self.chat_manager = GroupChatManager(
            groupchat=self.group_chat,
            llm_config=self.llm_config.copy(),
            system_message="Orchestrate the e-commerce assistance chat."
        )

    def _register_tools(self):
        from app.autogen_config.executor_config import (
            search_amazon_products, amazon_product_reviews,
            search_walmart_products, walmart_product_reviews,
            filter_amazon_products, filter_walmart_products,
            amazon_product_descriptions_by_keyword, walmart_product_descriptions_by_keyword,
            get_product_reviews_from_both_platforms, get_product_descriptions_from_both_platforms,
            search_products_from_both_platforms
        )

        # Clear existing function maps to prevent override warnings
        if hasattr(self.ecommerce_assistant, '_function_map'): 
            self.ecommerce_assistant._function_map.clear()
        if hasattr(self.tool_executor, '_function_map'): 
            self.tool_executor._function_map.clear()
        if hasattr(self.context_agent, '_function_map'): 
            self.context_agent._function_map.clear()
        if hasattr(self.logging_agent, '_function_map'): 
            self.logging_agent._function_map.clear()

        # Register e-commerce tools for EcommerceAssistant
        ecommerce_tools_callable = [
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

        for tool_func, description in ecommerce_tools_callable:
            try:
                register_function(
                    tool_func, 
                    caller=self.ecommerce_assistant, 
                    executor=self.tool_executor, 
                    name=tool_func.__name__, 
                    description=description
                )
                logger.info(f"[TOOLS] Registered {tool_func.__name__} for EcommerceAssistant")
            except Exception as e:
                logger.error(f"[TOOLS] Failed to register {tool_func.__name__}: {str(e)}")

        # Register get_conversation_context tool for ContextAgent
        try:
            register_function(
                get_conversation_context,
                caller=self.context_agent,
                executor=self.tool_executor,
                name="get_conversation_context",
                description="Get previous conversation context from memory"
            )
            logger.info("[TOOLS] Registered get_conversation_context for ContextAgent")
        except Exception as e:
            logger.error(f"[TOOLS] Failed to register get_conversation_context: {str(e)}")

        # Register log_conversation tool for LoggingAgent
        try:
            register_function(
                log_conversation,
                caller=self.logging_agent,
                executor=self.tool_executor,
                name="log_conversation",
                description="Log conversation to memory for future reference"
            )
            logger.info("[TOOLS] Registered log_conversation for LoggingAgent")
        except Exception as e:
            logger.error(f"[TOOLS] Failed to register log_conversation: {str(e)}")

    @staticmethod
    def _extract_session_id_from_messages_static(messages: List[Dict]) -> str:
        for message in reversed(messages):
            content = message.get("content", "")
            if isinstance(content, str) and "SESSION_ID:" in content:
                try:
                    return content.split("SESSION_ID:")[1].strip().split()[0]
                except IndexError:
                    continue
        return "unknown_session"

    @staticmethod
    def _extract_original_query_from_messages_static(messages: List[Dict]) -> str:
        for message in reversed(messages):
            content = message.get("content", "")
            if isinstance(content, str) and "USER_QUERY:" in content:
                try:
                    query_part = content.split("USER_QUERY:")[1].split("SESSION_ID:")[0].strip()
                    return query_part.strip('"')
                except Exception:
                    continue
        return "Unknown query"

    def _extract_session_id_from_messages(self) -> str:
        return self._extract_session_id_from_messages_static(self.group_chat.messages)

    def _extract_original_query_from_messages(self) -> str:
        return self._extract_original_query_from_messages_static(self.group_chat.messages)

    def custom_speaker_selection_func(self, last_speaker: Agent, groupchat: GroupChat) -> Optional[Agent]:
        messages = groupchat.messages
        last_message = messages[-1]
        speaker_name = last_speaker.name
        content = last_message.get("content", "")
        has_tool_calls = bool(last_message.get("tool_calls"))
        role = last_message.get("role")

        logger.info(f"CustomSpeakerSelect: Speaker='{speaker_name}', Role='{role}', ToolCalls={has_tool_calls}, Content='{str(content)[:100]}...'")

        if isinstance(content, str) and "TERMINATE" in content.rstrip():
            logger.info(f"{speaker_name} output TERMINATE, ending chat.")
            return None

        # Flow: UserProxy -> ContextAgent -> QueryAnalyzer -> (EcommerceAssistant/GeneralAssistant) -> ResponseFormatter -> LoggingAgent -> TERMINATE

        if speaker_name == self.user_proxy.name:
            return self.context_agent

        elif speaker_name == self.context_agent.name:
            if has_tool_calls:
                # ContextAgent made get_conversation_context call, route to executor
                return self.tool_executor
            else:
                # ContextAgent formatted context, route to QueryAnalyzer
                return self.query_analyzer

        elif speaker_name == self.query_analyzer.name:
            if isinstance(content, str):
                if "EcommerceAssistant" in content:
                    return self.ecommerce_assistant
                elif "GeneralAssistant" in content:
                    return self.general_assistant
            # Fallback
            return self.general_assistant

        elif speaker_name == self.ecommerce_assistant.name:
            if has_tool_calls:
                return self.tool_executor
            # If EcommerceAssistant fails to make a tool call, route to GeneralAssistant
            return self.general_assistant

        elif speaker_name == self.tool_executor.name:
            if role in ['function', 'tool']:
                # Check who made the tool call by looking at previous message
                if len(messages) >= 2:
                    caller_name = messages[-2].get('name')
                    if caller_name == self.context_agent.name:
                        return self.context_agent  # Route back to ContextAgent to format result
                    elif caller_name == self.ecommerce_assistant.name:
                        return self.response_formatter
                    elif caller_name == self.logging_agent.name:
                        return self.logging_agent  # Route back to LoggingAgent to terminate
            return None

        elif speaker_name in [self.response_formatter.name, self.general_assistant.name]:
            if not has_tool_calls:
                logger.info(f"Route: {speaker_name} produced final text. Routing to LoggingAgent.")
                return self.logging_agent
            else:
                # This should not happen, but if it does, it's an error.
                logger.error(f"Route: {speaker_name} unexpectedly made tool calls. Terminating.")
                return None

        elif speaker_name == self.logging_agent.name:
            # The LoggingAgent's generate_reply handles two states.
            # 1. It receives text from ResponseFormatter/GeneralAssistant and outputs a tool_call message.
            # 2. It receives the result of its tool_call and outputs a TERMINATE message.
            if has_tool_calls:
                # This is state 1. Route the tool call to the executor.
                return self.tool_executor
            else:
                # This must be state 2 (the TERMINATE message). The global check at the top will catch it.
                # If we get here and it's not TERMINATE, it's an error, and returning None is correct.
                return None

        # Fallback for any other unexpected agent state
        logger.error(f"CustomSpeakerSelect: Unexpected speaker '{speaker_name}'. Terminating chat.")
        return None

    def process_query(self, query: str, session_id: str) -> str:
        try:
            logger.info(f"Processing query: '{query[:100]}' for session_id: {session_id}")
            self.group_chat.messages.clear()
            enhanced_message = f'USER_QUERY: "{query}"\nSESSION_ID: {session_id}\n\nPlease retrieve conversation history for this session and then analyze the query.'
            self.user_proxy.initiate_chat(self.chat_manager, message=enhanced_message, max_turns=40)
            response = self._extract_final_response()
            logger.info(f"Chat finished. Total messages: {len(self.group_chat.messages)}")
            return response
        except Exception as e:
            logger.error(f"Error processing query '{query[:50]}...': {str(e)}", exc_info=True)
            return f"I apologize, but I encountered an error processing your request: {str(e)}. Please try rephrasing."

    def _extract_final_response(self) -> str:
        messages = self.group_chat.messages
        if not messages:
            return "No response was generated."

        for i in range(len(messages) -1, -1, -1):
            message = messages[i]
            speaker_name = message.get("name")
            
            # Find the first message from our final output agents. This is the user-facing response.
            if speaker_name in [self.response_formatter.name, self.general_assistant.name]:
                 content = message.get("content", "")
                 if isinstance(content, str) and content.strip():
                    cleaned_content = content.replace("TERMINATE", "").strip()
                    if cleaned_content:
                         logger.info(f"Extracted final response from {speaker_name} at index {i}: {cleaned_content[:200]}...")
                         return cleaned_content

        logger.warning("_extract_final_response: No suitable message found.")
        return "I was unable to generate a final response at this time. Please check the logs for details."

    def test_tools_registration(self) -> Dict:
        """Test if tools are properly registered"""
        try:
            assistant_callable_tools = list(self.ecommerce_assistant._function_map.keys()) if hasattr(self.ecommerce_assistant, '_function_map') else ["N/A (_function_map missing)"]
            context_callable_tools = list(self.context_agent._function_map.keys()) if hasattr(self.context_agent, '_function_map') else ["N/A (_function_map missing)"]
            formatter_callable_tools = list(self.response_formatter._function_map.keys()) if hasattr(self.response_formatter, '_function_map') else ["N/A (_function_map missing)"]
            general_callable_tools = list(self.general_assistant._function_map.keys()) if hasattr(self.general_assistant, '_function_map') else ["N/A (_function_map missing)"]
            logging_callable_tools = list(self.logging_agent._function_map.keys()) if hasattr(self.logging_agent, '_function_map') else ["N/A (_function_map missing)"]

            executor_execution_tools = list(self.tool_executor.function_map.keys()) if hasattr(self.tool_executor, 'function_map') else ["N/A (function_map missing)"]

            return {
                "ecommerce_assistant_callable_tools": assistant_callable_tools,
                "context_agent_callable_tools": context_callable_tools,
                "response_formatter_callable_tools": formatter_callable_tools,
                "general_assistant_callable_tools": general_callable_tools,
                "logging_agent_callable_tools": logging_callable_tools,
                "tool_executor_execution_tools_runtime": executor_execution_tools,
                "has_ecommerce_search_tools_callable_by_assistant": any("search_" in tool for tool in assistant_callable_tools),
                "has_context_tools_callable_by_context_agent": "get_conversation_context" in context_callable_tools,
                "has_logging_tools_callable_by_logging_agent": "log_conversation" in logging_callable_tools,
                "expected_tools_registered_as_callable": sorted(list(set(assistant_callable_tools + context_callable_tools + logging_callable_tools + ["N/A (_function_map missing)"])))
            }
        except Exception as e:
            logger.error(f"Error during tool registration check: {e}")
            return {"error": str(e), "registration_status": "error_during_check"}

    def get_debug_info(self) -> Dict:
        """Get comprehensive debug information"""
        try:
            debug_info = {
                "agents_in_group_chat": [agent.name for agent in self.group_chat.agents],
                "llm_model": self.llm_config["config_list"][0]["model"],
                "tools_registration": self.test_tools_registration(),
                "current_chat_messages_count": len(self.group_chat.messages),
                "context_agent_info": {
                    "name": self.context_agent.name,
                    "has_context_method": hasattr(self.context_agent, 'generate_reply')
                },
                "session_extraction_test_on_current_history": {
                    "session_id": self._extract_session_id_from_messages(),
                    "original_query": self._extract_original_query_from_messages()
                },
                 "groupchat_config": {
                     "max_round": self.group_chat.max_round,
                     "allow_repeat_speaker": self.group_chat.allow_repeat_speaker,
                 }
            }

            if self.group_chat.messages:
                debug_info["last_20_messages"] = [
                    {
                        "agent": msg.get("name", "N/A"),
                        "role": msg.get("role", "N/A"),
                        "content_preview": (str(msg.get("content", ""))[:300] + '...') if msg.get("content") else str(msg.get("content")),
                        "has_tool_calls": bool(msg.get("tool_calls")),
                        "tool_call_names": [tc.get("function", {}).get("name") for tc in msg.get("tool_calls", [])] if msg.get("tool_calls") else [],
                         "tool_response_count": len(msg.get("tool_responses", [])) if msg.get("tool_responses") else 0
                    }
                    for msg in self.group_chat.messages[-20:]
                ]

            return debug_info
        except Exception as e:
            logger.error(f"Error gathering debug info: {e}")
            return {"debug_error": str(e)}