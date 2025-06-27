# --- START OF FILE planner_config.py ---

import os
import json
import logging
from typing import Dict, List, Any, Optional, Sequence, cast # Added Sequence and cast
import autogen
from autogen import ConversableAgent, GroupChat, GroupChatManager, Agent # Ensure Agent is imported
from autogen.agentchat.user_proxy_agent import UserProxyAgent
from app.autogen_config.executor_config import create_ecommerce_agents # register_all_tools is handled internally by create_ecommerce_agents
from dotenv import load_dotenv
from app.autogen_config.executor_config import register_all_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

class EcommerceAssistant:
    def __init__(self):
        self.llm_config = {
            "config_list": [
                {
                    "model": "gemini-1.5-flash-latest", # Using a common, capable model
                    "api_key": os.getenv("GEMINI_API_KEY"),
                    "api_type": "google"
                }
            ],
            "temperature": 0.5, # Slightly lower for more predictable tool use
            "max_tokens": 2048
        }
        
        self._setup_agents()
        self._setup_group_chat()
    
    def _setup_agents(self):
        self.ecommerce_assistant, self.tool_executor = create_ecommerce_agents(self.llm_config.copy())
        
        # Ensure names are what executor_config sets them to, for clarity in this file's logic
        # These are the names set *inside* executor_config.create_ecommerce_agents
        # Typically "EcommerceAssistant" and "ToolExecutor"
        logger.info(f"Tool Proposing Agent created with name: {self.ecommerce_assistant.name}")
        logger.info(f"Tool Executing Agent created with name: {self.tool_executor.name}")
        
        self.query_analyzer = ConversableAgent(
            name="QueryAnalyzer",
            llm_config=self.llm_config.copy(),
            system_message="""You are the QueryAnalyzer. Your task is to understand the user's query and then provide a concise instruction for the 'EcommerceAssistant' agent.
If the query requires a tool (e.g., product search, reviews, context lookup):
1. Analyze the query to determine the intent and extract necessary parameters.
2. Formulate a clear instruction for 'EcommerceAssistant' to use the appropriate tool.
   Example Instruction: "EcommerceAssistant, please use the search_amazon_products tool with keyword 'laptops' and limit 3."
   Example Instruction: "EcommerceAssistant, get reviews for Amazon product ASIN 'B0XYZ123' limiting to 3 reviews."
3. Respond ONLY with this instruction, prefixed by "Instruction for EcommerceAssistant: ".

If the query is general (e.g., greeting, general shopping advice):
- Respond with: "Instruction for GeneralAssistant: [User's original query or your summary for GeneralAssistant]"

Do not call tools yourself. Your role is to direct.""",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1, # Should speak once then pass control
        )
        
        self.response_formatter = ConversableAgent(
            name="ResponseFormatter",
            llm_config=self.llm_config.copy(),
            system_message="""You are the ResponseFormatter. You receive results from tool executions (as messages with role 'tool') or messages from other agents.
Format product information clearly: 🛍️ **Name** 💰 Price ⭐ Rating 🔗 [Link](URL).
Format reviews: 📝 **Reviews:** ⭐ Rating - "Text..."
If you receive an error message from a tool, explain it clearly and suggest next steps.
If no data found, state that. Provide helpful follow-up suggestions.
After formatting, if the task is complete, end your response with TERMINATE.""",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1, # Should speak once
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
        )
        
        self.general_assistant = ConversableAgent(
            name="GeneralAssistant",
            llm_config=self.llm_config.copy(),
            system_message="""You are the GeneralAssistant. You receive instructions from QueryAnalyzer.
Handle general shopping questions, greetings, or provide advice as instructed.
After responding, end your message with TERMINATE.""",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1, # Should speak once
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
        )
        
        self.user_proxy = ConversableAgent(
            name="UserProxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0, # UserProxy only initiates
            llm_config=False,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            system_message="A human user representation that initiates the conversation."
        )

    def _setup_group_chat(self):
        agents_list: List[Agent] = [
            self.user_proxy,
            self.query_analyzer,
            self.ecommerce_assistant, # This is the tool-proposing agent
            self.tool_executor,       # This is the tool-executing agent
            self.response_formatter,
            self.general_assistant
        ]
        
        self.group_chat = GroupChat(
            agents=agents_list,
            messages=[],
            max_round=8,
            speaker_selection_method=self.custom_speaker_selection_func,
            allow_repeat_speaker=False # Important to prevent loops without progress
        )
        
        self.chat_manager = GroupChatManager(
            groupchat=self.group_chat,
            llm_config=self.llm_config.copy(), # Manager can use LLM for complex orchestration if needed
            system_message="Orchestrate the e-commerce assistance chat. Follow speaker selection rigorously."
        )

    def custom_speaker_selection_func(self, last_speaker: Agent, groupchat: GroupChat) -> Optional[Agent]:
        messages = groupchat.messages
        if not messages:
            # This case should ideally not be hit if user_proxy initiates.
            # If it is, routing to user_proxy might be a way to restart or error out.
            logger.warning("CustomSpeakerSelect: No messages found, returning None to terminate.")
            return None 

        last_message = messages[-1]
        # Use last_speaker.name as it's the agent object that just finished its turn.
        speaker_name = last_speaker.name 
        content = last_message.get("content", "") # Get raw content
        
        logger.info(f"CustomSpeakerSelect: Last speaker='{speaker_name}', Msg Role='{last_message.get('role')}', Has tool_calls='{bool(last_message.get('tool_calls'))}', Content='{content[:100]}'")

        if speaker_name == self.user_proxy.name:
            return self.query_analyzer
            
        elif speaker_name == self.query_analyzer.name:
            if "Instruction for EcommerceAssistant:" in content:
                return self.ecommerce_assistant
            elif "Instruction for GeneralAssistant:" in content:
                return self.general_assistant
            else:
                logger.warning(f"QueryAnalyzer output not understood for routing: {content}")
                return None # End chat or route to user_proxy for clarification
                
        elif speaker_name == self.ecommerce_assistant.name:
            # ** CRITICAL FIX HERE **
            # Check if the ecommerce_assistant (tool proposer) actually made a tool call
            if last_message.get("tool_calls"):
                logger.info(f"Routing: {self.ecommerce_assistant.name} made tool_calls, to {self.tool_executor.name}")
                return self.tool_executor
            else:
                # If EcommerceAssistant didn't make a tool call (e.g., it just chatted or needs more info)
                logger.warning(f"Routing: {self.ecommerce_assistant.name} did NOT make tool_calls. Content: {content}. Routing to {self.response_formatter.name} to handle.")
                return self.response_formatter # Or back to QueryAnalyzer, or UserProxy to ask for clarification.
                                               # Sending to ResponseFormatter assumes it can handle non-tool-result messages.
                
        elif speaker_name == self.tool_executor.name:
            # ToolExecutor's response should be a message with role "tool" containing the function's output.
            if last_message.get("role") == "tool":
                logger.info(f"Routing: {self.tool_executor.name} returned tool response, to {self.response_formatter.name}")
                return self.response_formatter
            else:
                # This case indicates an issue, ToolExecutor should always reply with a tool message.
                logger.error(f"Routing: {self.tool_executor.name} did not return a 'tool' role message. Message: {last_message}. Routing to ResponseFormatter to report error.")
                return self.response_formatter # Let formatter try to explain the problem.
            
        elif speaker_name == self.response_formatter.name or speaker_name == self.general_assistant.name:
            if "TERMINATE" in content:
                logger.info(f"Routing: {speaker_name} terminated. Ending chat.")
                return None 
            else:
                # If they didn't terminate, could be an error or incomplete thought.
                # Forcing termination here to avoid loops if they don't use TERMINATE correctly.
                logger.warning(f"Routing: {speaker_name} did not terminate. Forcing end of chat.")
                return None
        elif speaker_name == "LoggingInitiator":
            if last_message.get("tool_calls"):
                logger.info(f"Routing: LoggingInitiator made tool call. Handing off to ToolExecutor.")
                return self.tool_executor
            else:
                logger.warning("LoggingInitiator did not make tool call. Terminating.")
                return None

        logger.warning(f"CustomSpeakerSelect: No rule matched for speaker '{speaker_name}'. Ending chat.")
        return None # Default to ending the conversation if no rule matches

    def process_query(self, query: str, session_id: str) -> str:
        try:
            logger.info(f"Processing query: '{query[:100]}' for session_id: {session_id}")
            
            self.group_chat.reset() # Reset messages for a new query
            
            enhanced_message = f"USER_QUERY: \"{query}\"\nSESSION_ID: {session_id}"
            
            chat_result = self.user_proxy.initiate_chat(
                self.chat_manager,
                message=enhanced_message,
                max_turns=10 # Max turns for the entire interaction flow
            )
            
            response = self._extract_final_response()
            
            self._log_successful_interaction(query, response, session_id) # Attempt logging
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query '{query[:50]}...': {str(e)}", exc_info=True)
            return f"I apologize, but I encountered an error processing your request: {str(e)}. Please try rephrasing."

    def _extract_final_response(self) -> str:
        messages = self.group_chat.messages
        if not messages:
            return "No response was generated."

        target_agents = [self.response_formatter.name, self.general_assistant.name]
        for message in reversed(messages):
            agent_name = message.get("name", "")
            content = message.get("content", "").strip()
            
            if agent_name in target_agents and content:
                # Remove TERMINATE and other internal markers if present
                content_cleaned = content.replace("TERMINATE", "").strip()
                if "USER_QUERY:" not in content_cleaned and "SESSION_ID:" not in content_cleaned and content_cleaned:
                    return content_cleaned
        
        # Fallback if no clean response from target agents
        last_message_content = messages[-1].get("content", "").strip().replace("TERMINATE", "")
        if last_message_content and "USER_QUERY:" not in last_message_content:
            return last_message_content
            
        return "I processed your request but could not form a clear final response."

    def _log_successful_interaction(self, query: str, response: str, session_id: str):
        """
        Logs the query and response into memory using the log_conversation tool directly.
        Skips unsuccessful interactions (e.g., error/apology responses).
        """

        if "error" in response.lower() or "apologize" in response.lower() or "could not form" in response.lower():
            logger.info(f"Skipping logging for unsuccessful interaction. Query: {query[:50]}")
            return

        try:
            logger.info(f"[LOGGING] Attempting to log interaction for session {session_id}")

            # Create agents
            temp_logging_initiator = UserProxyAgent(
                name="LoggingInitiator",
                llm_config=False,
                code_execution_config={"use_docker": False}
            )

            temp_log_agents: List[Agent] = [temp_logging_initiator, self.tool_executor]

            # Re-register tools on temp agents
            register_all_tools(self.ecommerce_assistant, self.tool_executor)  # THIS LINE IS ESSENTIAL

            temp_log_group_chat = GroupChat(
                agents=temp_log_agents,
                messages=[],
                max_round=3,
                speaker_selection_method="round_robin",
                allow_repeat_speaker=True
            )

            temp_log_manager = GroupChatManager(groupchat=temp_log_group_chat, llm_config=self.llm_config.copy())

            # Force direct tool execution — bypass LLM
            temp_logging_initiator.initiate_chat(
                temp_log_manager,
                function_calls=[
                    {
                        "name": "log_conversation",
                        "arguments": {
                            "user_query": query[:500],
                            "assistant_response": response[:500],
                            "session_id": session_id
                        }
                    }
                ]
            )

            logger.info(f"[LOGGING] Logging call for session {session_id} completed.")

        except Exception as e:
            logger.warning(f"[LOGGING] Failed to log conversation for session {session_id}: {str(e)}", exc_info=True)


    

    def test_tools_registration(self) -> Dict:
        try:
            assistant_tools = list(self.ecommerce_assistant._function_map.keys()) if hasattr(self.ecommerce_assistant, '_function_map') else ["N/A"]
            executor_tools = list(self.tool_executor._function_map.keys()) if hasattr(self.tool_executor, '_function_map') else ["N/A"]
            
            return {
                "proposing_agent_name": self.ecommerce_assistant.name,
                "proposing_agent_tools": assistant_tools,
                "executing_agent_name": self.tool_executor.name,
                "executing_agent_tools": executor_tools, # Executor usually has the actual functions
                "registration_status": "success" if "search_amazon_products" in executor_tools else "check_failed"
            }
        except Exception as e:
            return {"error": str(e), "registration_status": "error_during_check"}

    def get_debug_info(self) -> Dict:
        try:
            debug_info = {
                "agents_in_group_chat": [agent.name for agent in self.group_chat.agents],
                "llm_model": self.llm_config["config_list"][0]["model"],
                "tools_registration": self.test_tools_registration(),
                "current_chat_messages_count": len(self.group_chat.messages),
            }
            if self.group_chat.messages:
                debug_info["last_5_messages"] = [
                    {"agent": msg.get("name", "N/A"), "role": msg.get("role", "N/A"), "content_preview": str(msg.get("content", ""))[:150], "tool_calls": msg.get("tool_calls")}
                    for msg in self.group_chat.messages[-5:]
                ]
            return debug_info
        except Exception as e:
            return {"debug_error": str(e)}