
"""
KAI-Fusion ReactAgent Node - Modern LangGraph-Based AI Agent Orchestration
=========================================================================

This module implements a sophisticated ReactAgent node using the latest LangGraph API,
serving as the orchestration brain of the KAI-Fusion platform. Built on LangGraph's
modern create_react_agent framework, it provides enterprise-grade agent capabilities
with advanced tool integration, state-based memory management, and multilingual support.

ARCHITECTURAL OVERVIEW:
======================

The ReactAgent operates on the modern LangGraph state-based paradigm:
1. **State Management**: Uses CompiledStateGraph for robust execution flow
2. **Message-Based Communication**: Handles conversations as message sequences
3. **Tool Orchestration**: Automatic tool calling and result processing
4. **Memory Integration**: Checkpointer-based persistent memory

┌─────────────────────────────────────────────────────────────┐
│              Modern ReactAgent Architecture                 │
├─────────────────────────────────────────────────────────────┤
│  Messages  →  [CompiledStateGraph]  →  [Tool Execution]     │
│      ↓               ↑                       ↓              │
│  [Checkpointer]  ←  [State Updates]  ←  [Agent Reasoning]   │
│      ↓               ↑                       ↓              │
│  [Persistence]  →  [Response Generation]  ←  [Results]      │
└─────────────────────────────────────────────────────────────┘

KEY INNOVATIONS:
===============

1. **Multilingual Intelligence**: Native Turkish/English support with cultural context
2. **Efficiency Optimization**: Smart tool usage to minimize unnecessary calls
3. **Memory Integration**: Sophisticated conversation history management
4. **Retriever Tool Support**: Seamless RAG integration with document search
5. **Error Resilience**: Robust error handling with graceful degradation
6. **Performance Monitoring**: Built-in execution tracking and optimization

TOOL ECOSYSTEM:
==============

The agent supports multiple tool types:
- **Search Tools**: Web search, document retrieval, knowledge base queries
- **API Tools**: External service integration, data fetching
- **Processing Tools**: Text analysis, data transformation
- **Memory Tools**: Conversation history, context management
- **Custom Tools**: User-defined business logic tools

MEMORY ARCHITECTURE:
===================

Advanced memory management with multiple layers:
- **Short-term Memory**: Current conversation context
- **Long-term Memory**: Persistent user preferences and history  
- **Working Memory**: Intermediate reasoning steps and tool results
- **Semantic Memory**: Vector-based knowledge storage and retrieval

PERFORMANCE OPTIMIZATIONS:
=========================

1. **Smart Tool Selection**: Context-aware tool prioritization
2. **Caching Strategy**: Intelligent result caching to avoid redundant calls
3. **Parallel Execution**: Where possible, execute tools concurrently
4. **Resource Management**: Memory and computation resource optimization
5. **Timeout Handling**: Graceful handling of slow or unresponsive tools

MULTILINGUAL CAPABILITIES:
=========================

- **Language Detection**: Automatic detection of user language
- **Contextual Responses**: Culturally appropriate responses in Turkish/English
- **Code-Switching**: Natural handling of mixed-language inputs
- **Localized Tool Usage**: Language-specific tool selection and parameterization

ERROR HANDLING STRATEGY:
=======================

Comprehensive error handling with multiple fallback mechanisms:
1. **Tool Failure Recovery**: Alternative tool selection on failure
2. **Memory Corruption Handling**: State recovery and cleanup
3. **Timeout Management**: Graceful handling of long-running operations
4. **Partial Result Processing**: Useful output even from incomplete operations

INTEGRATION PATTERNS:
====================

Seamless integration with KAI-Fusion ecosystem:
- **LangGraph Compatibility**: Full state management integration
- **LangSmith Tracing**: Comprehensive observability and debugging
- **Vector Store Integration**: Advanced RAG capabilities
- **Custom Node Connectivity**: Easy integration with custom business logic

AUTHORS: KAI-Fusion Development Team
VERSION: 2.1.0
LAST_UPDATED: 2025-07-26
LICENSE: Proprietary
"""

from ..base import NodePosition, ProcessorNode, NodeInput, NodePropertyType, NodeType, NodeOutput, NodeProperty
from app.nodes.memory import BufferMemoryNode
from app.core.tool import AutoToolManager
from typing import Dict, Any, Sequence, List, Optional
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.memory import BaseMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
import re
import sys
import os
import logging
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

# ================================================================================
# DEBUG CALLBACK HANDLER (Console step-by-step traces for LLM and Tool calls)
# ================================================================================
class AgentDebugCallback(BaseCallbackHandler):
    """
    Debug callback handler for LangChain agent execution tracing.
    
    This handler provides detailed console output for debugging purposes,
    capturing events from chains, LLMs, and tools during agent execution.
    Useful for development and troubleshooting agent behavior.
    """
    
    @staticmethod
    def _safe_name(serialized) -> str:
        """
        Safely extract component name from serialized data.
        
        Args:
            serialized: The serialized component data, can be dict, object, or None.
            
        Returns:
            str: The extracted name or 'unknown' if extraction fails.
        """
        try:
            if serialized is None:
                return "unknown"
            if isinstance(serialized, dict):
                # LangChain often passes {"id": [...]} or {"name": "..."} etc.
                return serialized.get("name") or serialized.get("id") or "unknown"
            # Fallback to type name
            return type(serialized).__name__
        except Exception:
            return "unknown"

    def on_chain_start(self, serialized, inputs, **kwargs):
        """
        Callback triggered when a chain starts execution.
        
        Args:
            serialized: Serialized chain data.
            inputs: Input data being passed to the chain.
            **kwargs: Additional keyword arguments.
        """
        try:
            name = self._safe_name(serialized)
            keys = list(inputs.keys()) if isinstance(inputs, dict) else type(inputs)
            print(f"[TRACE][CHAIN.START] {name} inputs_keys={keys}")
        except Exception as e:
            print(f"[TRACE][CHAIN.START] error={e}")

    def on_chain_end(self, outputs, **kwargs):
        """
        Callback triggered when a chain completes execution.
        
        Args:
            outputs: Output data produced by the chain.
            **kwargs: Additional keyword arguments.
        """
        try:
            keys = list(outputs.keys()) if isinstance(outputs, dict) else type(outputs)
            print(f"[TRACE][CHAIN.END] outputs_keys={keys}")
        except Exception as e:
            print(f"[TRACE][CHAIN.END] error={e}")

    def on_chain_error(self, error, **kwargs):
        """
        Callback triggered when a chain encounters an error.
        
        Args:
            error: The exception that occurred.
            **kwargs: Additional keyword arguments.
        """
        try:
            print(f"[TRACE][CHAIN.ERROR] {type(error).__name__}: {error}")
        except Exception:
            pass

    def on_llm_start(self, serialized, prompts, **kwargs):
        """
        Callback triggered when an LLM call starts.
        
        Args:
            serialized: Serialized LLM data.
            prompts: List of prompts being sent to the LLM.
            **kwargs: Additional keyword arguments.
        """
        try:
            name = self._safe_name(serialized)
            count = len(prompts) if hasattr(prompts, "__len__") else "unknown"
            print(f"[TRACE][LLM.START] {name} prompts={count}")
            for i, p in enumerate(prompts or [], 1):
                p_str = str(p)
                snippet = p_str[:500].replace("\n", " ")
                print(f"[TRACE][LLM.PROMPT {i}] {snippet}")
        except Exception as e:
            print(f"[TRACE][LLM.START] error={e}")

    def on_llm_end(self, response, **kwargs):
        """
        Callback triggered when an LLM call completes.
        
        Args:
            response: The LLM response object containing generations and usage info.
            **kwargs: Additional keyword arguments.
        """
        try:
            gens = getattr(response, "generations", None)
            text = gens[0][0].text if gens and gens[0] and gens[0][0] else ""
            print(f"[TRACE][LLM.END] text_snippet={text[:300].replace(chr(10), ' ')}")
            llm_output = getattr(response, "llm_output", None)
            usage = llm_output.get("token_usage") if isinstance(llm_output, dict) else None
            if usage:
                print(f"[TRACE][LLM.USAGE] {usage}")
        except Exception as e:
            print(f"[TRACE][LLM.END] parse_error={e}")

    def on_llm_error(self, error, **kwargs):
        """
        Callback triggered when an LLM call encounters an error.
        
        Args:
            error: The exception that occurred.
            **kwargs: Additional keyword arguments.
        """
        try:
            print(f"[TRACE][LLM.ERROR] {type(error).__name__}: {error}")
        except Exception:
            pass

    def on_tool_start(self, serialized, input_str, **kwargs):
        """
        Callback triggered when a tool execution starts.
        
        Args:
            serialized: Serialized tool data.
            input_str: Input string being passed to the tool.
            **kwargs: Additional keyword arguments.
        """
        try:
            name = self._safe_name(serialized)
            print(f"[TRACE][TOOL.START] {name} args={input_str}")
        except Exception as e:
            print(f"[TRACE][TOOL.START] error={e}")

    def on_tool_end(self, output, **kwargs):
        """
        Callback triggered when a tool execution completes.
        
        Args:
            output: The output produced by the tool.
            **kwargs: Additional keyword arguments.
        """
        try:
            out_snippet = str(output)[:300].replace("\n", " ")
            print(f"[TRACE][TOOL.END] output={out_snippet}")
        except Exception as e:
            print(f"[TRACE][TOOL.END] error={e}")

    def on_tool_error(self, error, **kwargs):
        """
        Callback triggered when a tool execution encounters an error.
        
        Args:
            error: The exception that occurred.
            **kwargs: Additional keyword arguments.
        """
        try:
            print(f"[TRACE][TOOL.ERROR] {type(error).__name__}: {error}")
        except Exception:
            pass

# ================================================================================
# NOTE (2026-01): Multilingual auto-detection + language-specific prompt blocks were
# removed to keep the Agent node compact. Users can control language/behavior via
# the node's `system_prompt` setting.
# ================================================================================

# ================================================================================
# REACTAGENT NODE - THE ORCHESTRATION BRAIN OF KAI-FUSION
# ================================================================================

class ReactAgentNode(ProcessorNode):
    """
    KAI-Fusion ReactAgent - Modern LangGraph-Based AI Agent Orchestration Engine
    ==========================================================================
    
    The ReactAgentNode is the crown jewel of the KAI-Fusion platform, representing the
    culmination of modern AI agent architecture, multilingual intelligence, and
    enterprise-grade orchestration capabilities. Built upon LangGraph's latest
    create_react_agent framework, it transcends traditional agent limitations to deliver
    sophisticated, state-driven AI interactions with robust memory and tool management.

    AUTHORS: KAI-Fusion Development Team
    MAINTAINER: Senior AI Architecture Team
    VERSION: 3.0.0
    LAST_UPDATED: 2025-09-07
    LICENSE: Proprietary - KAI-Fusion Platform
    """
    
    def __init__(self):
        """Initialize ReactAgentNode with modular metadata configuration."""
        super().__init__()
        self._metadata = self._build_metadata()
        self.auto_tool_manager = AutoToolManager()

    def _build_metadata(self) -> Dict[str, Any]:
        """Build comprehensive metadata dictionary from modular components."""
        return {
            "name": self._get_node_name(),
            "display_name": self._get_display_name(),
            "description": self._get_description(),
            "category": self._get_category(),
            "node_type": self._get_node_type(),
            "colors": ["purple-500", "indigo-600"],      
            "icon": {"name": "bot", "path": None, "alt": None},
            "inputs": self._build_input_schema(),
            "outputs": self._build_output_schema(),
            "properties": self._build_properties_schema()
        }

    def _build_properties_schema(self) -> List[NodeProperty]:
        """Build the properties schema from modular property definitions."""
        return [
            NodeProperty(
                name="agent_type",
                displayName="Agent Type",
                type=NodePropertyType.SELECT,
                options=[
                    {"label": "ReAct Agent +", "value": "react"},
                    {"label": "Conversational Agent", "value": "conversational"},
                    {"label": "Task-Oriented Agent", "value": "task_oriented"},
                ],
                default="react",
                required=True,
            ),
            NodeProperty(
                name="user_prompt_template",
                displayName="User Prompt Template",
                type=NodePropertyType.TEXT_AREA,
                default="${{input}}",
                hint="Template for user input using ${{variable}} syntax",
                required=True,
            ),
            NodeProperty(
                name="system_prompt",
                displayName="System Prompt",
                type=NodePropertyType.TEXT_AREA,
                default="You are a helpful assistant. Use tools to answer questions.",
                hint="Define agent behavior and capabilities. This is the core system instruction.",
                required=False,
            ),
            NodeProperty(
                name="max_iterations",
                displayName="Max Iterations",
                type=NodePropertyType.RANGE,
                default=5,
                min=1,
                max=20,
                minLabel="Quick",
                maxLabel="Thorough",
                required=True,
            ),
            NodeProperty(
                name="temperature",
                displayName="Temperature",
                type=NodePropertyType.RANGE,
                default=0.7,
                min=0.0,
                max=2.0,
                step=0.1,
                color="purple-400",
                minLabel="Precise",
                maxLabel="Creative",
                required=True,
            ),
            NodeProperty(
                name="enable_memory",
                displayName="Enable Memory",
                type=NodePropertyType.CHECKBOX,
                default=True,
                hint="Allow agent to remember previous interactions",
            ),
            NodeProperty(
                name="enable_tools",
                displayName="Enable Tools",
                type=NodePropertyType.CHECKBOX,
                default=True,
                hint="Allow agent to use connected tools and functions",
            ),
        ]

    def _get_node_name(self) -> str:
        """Get the internal node name identifier."""
        return "Agent"

    def _get_display_name(self) -> str:
        """Get the user-friendly display name."""
        return "Agent"

    def _get_description(self) -> str:
        """Get the detailed node description."""
        return "Orchestrates LLM, tools, and memory for complex, multi-step tasks."

    def _get_category(self) -> str:
        """Get the node category for UI organization."""
        return "Agents"

    def _get_node_type(self) -> NodeType:
        """Get the processor node type."""
        return NodeType.PROCESSOR

    def _build_input_schema(self) -> List[NodeInput]:
        """Build the input schema from modular input definitions."""
        return [
            self._create_input_node(),
            self._create_llm_input(),
            self._create_tools_input(),
            self._create_memory_input(),
            self._create_max_iterations_input(),
            self._create_system_prompt_input()
        ]

    def _build_output_schema(self) -> List[NodeOutput]:
        """Build the output schema from modular output definitions."""
        return [self._create_output_node()]

    def _create_input_node(self) -> NodeInput:
        """Create the main input node configuration."""
        return NodeInput(
            name="input",
            displayName="Input",
            type="string",
            is_connection=True,
            required=True,
            description="The user's input to the agent."
        )

    def _create_llm_input(self) -> NodeInput:
        """Create the LLM connection input configuration."""
        return NodeInput(
            name="llm",
            displayName="LLM",
            type="BaseLanguageModel",
            required=True,
            is_connection=True,
            direction=NodePosition.BOTTOM,
            description="The language model that the agent will use."
        )

    def _create_tools_input(self) -> NodeInput:
        """Create the tools connection input configuration."""
        return NodeInput(
            name="tools",
            displayName="Tools",
            type="Sequence[BaseTool]",
            required=False,
            is_connection=True,
            direction=NodePosition.BOTTOM,
            description="The tools that the agent can use."
        )

    def _create_memory_input(self) -> NodeInput:
        """Create the memory connection input configuration."""
        return NodeInput(
            name="memory",
            displayName="Memory",
            type="BaseMemory",
            required=False,
            is_connection=True,
            direction=NodePosition.BOTTOM,
            description="The memory that the agent can use."
        )

    def _create_max_iterations_input(self) -> NodeInput:
        """Create the max iterations parameter input configuration."""
        return NodeInput(
            name="max_iterations",
            type="int",
            default=10,
            description="The maximum number of iterations the agent can perform."
        )

    def _create_system_prompt_input(self) -> NodeInput:
        """Create the system prompt parameter input configuration."""
        return NodeInput(
            name="system_prompt",
            type="str",
            default="You are a helpful assistant.",
            description="The system prompt for the agent."
        )

    def _create_output_node(self) -> NodeOutput:
        """Create the main output node configuration."""
        return NodeOutput(
            name="output",
            displayName="Output",
            type="str",
            description="The final output from the agent.",
            is_connection=True,
        )
    
    def get_required_packages(self) -> list[str]:
        """
        DYNAMIC METHOD: Returns the Python packages required by ReactAgentNode.
        
        This method is critical for the dynamic export system to work.
        Returns LangGraph and agent dependencies required for ReactAgent.
        """
        return [
            "langgraph>=0.2.0",            # LangGraph for new agent orchestration
            "langchain>=0.1.0",            # LangChain core framework
            "langchain-core>=0.1.0",       # LangChain core components
            "langchain-community>=0.0.10", # Community tools and agents
            "pydantic>=2.5.0",             # Data validation
            "typing-extensions>=4.8.0"     # Advanced typing support
        ]

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Runnable]) -> Runnable:
        """
        Sets up and returns a RunnableLambda that executes the agent.

        NOTE: Multilingual detection/prompt blocks were removed. Language/behavior is controlled
        purely via the user-provided `system_prompt`.
        """
        def agent_executor_lambda(runtime_inputs: dict) -> dict:
            # Setup encoding and validate connections
            self._setup_encoding()
            llm, tools, memory = self._validate_and_extract_connections(connected_nodes)

            # Prepare tools and detect language
            tools_list = self._prepare_tools(tools)
            # Trace prepared tools for visibility
            try:
                tool_names = [getattr(t, "name", type(t).__name__) for t in (tools_list or [])]
                print(f"[TRACE][AGENT.TOOLS] prepared={len(tools_list)} tools={tool_names}")
            except Exception as e:
                print(f"[TRACE][AGENT.TOOLS] error listing tools: {e}")

            # CRITICAL FIX: Use templated inputs instead of extracting separately
            # The templating has already been applied to the 'inputs' parameter by node_executor.py
            user_input = self._extract_user_input_from_templated_inputs(runtime_inputs, inputs)

            # Create agent graph using new API
            agent_graph = self._create_agent(llm, tools_list, memory, inputs)

            # Prepare final input and execute
            final_input = self._prepare_final_input_for_graph(user_input, memory)
            return self._execute_graph_with_error_handling(agent_graph, final_input, memory, user_input=user_input)

        return RunnableLambda(agent_executor_lambda)

    def _setup_encoding(self) -> None:
        """Setup UTF-8 encoding for Turkish character support."""
        try:
            # Force UTF-8 encoding for all string operations
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')

            # Set environment variables for UTF-8 (Docker-compatible)
            os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
            os.environ.setdefault('LANG', 'C.UTF-8')
            os.environ.setdefault('LC_ALL', 'C.UTF-8')

            print(f"[DEBUG] Encoding setup completed - Default: {sys.getdefaultencoding()}")

        except Exception as encoding_error:
            print(f"[WARNING] Encoding setup failed: {encoding_error}")

    def _validate_and_extract_connections(self, connected_nodes: Dict[str, Runnable]) -> tuple:
        """Validate connections and extract LLM, tools, and memory components."""
        print(f"[DEBUG] Agent connected_nodes keys: {list(connected_nodes.keys())}")
        print(f"[DEBUG] Agent connected_nodes types: {[(k, type(v)) for k, v in connected_nodes.items()]}")

        llm = connected_nodes.get("llm")
        tools = connected_nodes.get("tools")
        memory = connected_nodes.get("memory")

        # Enhanced LLM validation
        self._validate_llm_connection(llm, connected_nodes)

        return llm, tools, memory

    def _validate_llm_connection(self, llm: Any, connected_nodes: Dict[str, Runnable]) -> None:
        """Validate that LLM connection is properly configured."""
        print(f"[DEBUG] LLM received: {type(llm)}")
        if llm is None:
            available_connections = list(connected_nodes.keys())
            raise ValueError(
                f"A valid LLM connection is required. "
                f"Available connections: {available_connections}. "
                f"Make sure to connect an OpenAI Chat node to the 'llm' input of this Agent."
            )

        if not isinstance(llm, BaseLanguageModel):
            raise ValueError(
                f"Connected LLM must be a BaseLanguageModel instance, got {type(llm)}. "
                f"Ensure the OpenAI Chat node is properly configured and connected."
            )

    def _extract_user_input(self, runtime_inputs: Any, inputs: Dict[str, Any]) -> str:
        """Extract user input from various input formats."""
        if isinstance(runtime_inputs, str):
            return runtime_inputs
        elif isinstance(runtime_inputs, dict):
            return runtime_inputs.get("input", inputs.get("input", ""))
        else:
            return inputs.get("input", "")

    def _extract_user_input_from_templated_inputs(self, runtime_inputs: Any, templated_inputs: Dict[str, Any]) -> str:
        """
        Extract user input from templated input fields.

        Logic:
        - Chat mode: user_prompt_template contains {{input}} which gets templated to actual user message
          -> Use templated user_prompt_template as the user input
        - StartNode mode: user_prompt_template is empty or not used
          -> Use the connected 'input' field directly

        This method ensures both modes work correctly.
        """
        # Get the templated user_prompt_template (this is where {{input}} becomes "actual message")
        templated_user_prompt = ""
        if isinstance(templated_inputs, dict):
            templated_user_prompt = templated_inputs.get("user_prompt_template", "").strip()

        # Get raw user_prompt_template from user_data
        raw_template = self.user_data.get("user_prompt_template", "").strip()

        # CHAT MODE: If user_prompt_template was successfully templated (contains actual content)
        # Use the templated value as user input
        if templated_user_prompt and raw_template:
            # Check if templating actually happened (value changed from raw template)
            if templated_user_prompt != raw_template and "{{" not in templated_user_prompt:
                print(f"[TEMPLATE] ReactAgent using templated user_prompt_template (Chat mode): '{templated_user_prompt[:50]}...'")
                return templated_user_prompt

        # STARTNODE MODE or FALLBACK: Use the connected 'input' field
        # Priority 1: templated 'input' field from connections
        if isinstance(templated_inputs, dict) and "input" in templated_inputs:
            templated_input = templated_inputs["input"]
            if isinstance(templated_input, str) and templated_input.strip():
                print(f"[TEMPLATE] ReactAgent using connected input (StartNode mode): '{templated_input[:50]}...'")
                return templated_input

        # Priority 2: runtime_inputs string
        if isinstance(runtime_inputs, str) and runtime_inputs.strip():
            print(f"[TEMPLATE] ReactAgent using runtime input: '{runtime_inputs[:50]}...'")
            return runtime_inputs

        # Priority 3: runtime_inputs dict
        if isinstance(runtime_inputs, dict):
            runtime_input = runtime_inputs.get("input", "")
            if runtime_input and isinstance(runtime_input, str):
                print(f"[TEMPLATE] ReactAgent using runtime dict input: '{runtime_input[:50]}...'")
                return runtime_input

        # Fallback: empty string (should not happen in normal flow)
        print(f"[TEMPLATE] ReactAgent: No user input found, using empty string")
        return ""

    def _create_agent(self, llm: BaseLanguageModel, tools_list: list, memory: Any = None, user_inputs: Dict[str, Any] = None) -> CompiledStateGraph:
        """Create the React agent using a compact prompt (system_prompt only)."""
        agent_prompt = self._create_agent_prompt(tools_list, user_inputs)
        
        # Create checkpointer for memory if memory is provided
        checkpointer = None
        if memory is not None:
            try:
                checkpointer = MemorySaver()
                print("   [MEMORY] Using MemorySaver checkpointer")
            except Exception as e:
                print(f"   [MEMORY] Failed to create checkpointer ({str(e)}), proceeding without memory")
        
        # Create the agent using new API
        agent_graph = create_react_agent(
            model=llm,
            tools=tools_list,
            prompt=agent_prompt,
            checkpointer=checkpointer,
            version="v2"
        )
        
        return agent_graph

    def _validate_memory(self, memory: Any) -> bool:
        """Validate memory component for graph-based execution."""
        try:
            if hasattr(memory, 'load_memory_variables'):
                test_vars = memory.load_memory_variables({})
                print("   [MEMORY] Valid memory object found")
                return True
            else:
                print("   [MEMORY] Invalid memory object, proceeding without memory")
                return False
        except Exception as e:
            print(f"   [MEMORY] Failed to validate ({str(e)}), proceeding without memory")
            return False

    def _prepare_final_input_for_graph(self, user_input: str, memory: Any) -> Dict[str, Any]:
        """Prepare the final input dictionary for graph execution using new state format."""
        # Load conversation history as a list of message objects
        messages = self._load_conversation_history(memory)

        # Always add user input as HumanMessage
        # The _extract_user_input_from_templated_inputs method now correctly returns:
        # - For Chat mode: the templated user_prompt_template (e.g., "bana baklava tarifi")
        # - For StartNode mode: the connected input value
        if user_input and user_input.strip():
            print(f"[AGENT] Adding HumanMessage: '{user_input[:50]}...'")
            messages.append(HumanMessage(content=user_input))
        else:
            print(f"[AGENT] Warning: No user input to add as HumanMessage")

        return {
            "messages": messages
        }

    def _load_conversation_history(self, memory: Any) -> List[BaseMessage]:
        """Load and return conversation history from memory as a list of messages."""
        print(f"[AGENT MEMORY DEBUG] Starting memory history load")
        
        if memory is None:
            print("[AGENT MEMORY DEBUG] Memory object is None")
            return []

        try:
            # Try to load memory variables
            print(f"[AGENT MEMORY DEBUG] Attempting to load memory variables...")
            memory_vars = memory.load_memory_variables({})
            
            if not memory_vars:
                print("[AGENT MEMORY DEBUG] Memory variables are empty or None")
                return []

            # Identify the memory key from the memory object, fallback to session_id or 'memory'
            memory_key = getattr(memory, 'memory_key', self.session_id or 'memory')
            history_content = memory_vars.get(memory_key, [])
            
            if isinstance(history_content, list):
                print(f"   [MEMORY] Loaded {len(history_content)} messages from history")
                # Ensure the messages are in a clean list of BaseMessage objects
                messages = []
                for msg in history_content:
                    if isinstance(msg, BaseMessage):
                        messages.append(msg)
                    elif isinstance(msg, dict):
                        m_type = msg.get('type', 'human')
                        m_content = msg.get('content', '')
                        if m_type == 'human':
                            messages.append(HumanMessage(content=m_content))
                        elif m_type == 'ai':
                            messages.append(AIMessage(content=m_content))
                return messages
            
            return []

        except Exception as memory_error:
            print(f"   [WARNING] Failed to load memory variables: {memory_error}")
            return []

    def _format_conversation_history(self, history_content: Any) -> str:
        """Format conversation history into readable string."""
        if isinstance(history_content, list):
            formatted_history = []
            for msg in history_content:
                if hasattr(msg, 'type') and hasattr(msg, 'content'):
                    role = "Human" if msg.type == "human" else "Assistant"
                    formatted_history.append(f"{role}: {msg.content}")
                elif isinstance(msg, dict):
                    role = "Human" if msg.get('type') == 'human' else "Assistant"
                    formatted_history.append(f"{role}: {msg.get('content', '')}")

            if formatted_history:
                conversation_history = "\n".join(formatted_history[-10:])  # Last 10 messages
                print(f"   [MEMORY] Loaded conversation history: {len(formatted_history)} messages")
                return conversation_history

        elif isinstance(history_content, str) and history_content.strip():
            print(f"   [MEMORY] Loaded conversation history: {len(history_content)} chars")
            return history_content

        return ""

    def _execute_graph_with_error_handling(self, agent_graph: CompiledStateGraph, final_input: Dict[str, Any], memory: Any, user_input: str = None) -> Dict[str, Any]:
        """Execute the agent graph with comprehensive error handling."""
        try:

            result = agent_graph.invoke(final_input)
            
            # Extract the final message content from the result
            if 'messages' in result and result['messages']:
                last_ai_message = result['messages'][-1]
                output_content = last_ai_message.content if hasattr(last_ai_message, 'content') else str(last_ai_message)
                print(f"[AGENT OUTPUT] {output_content}")
                # Debug: Check memory after execution and save to database
                if memory:
                    try:
                        print("   [PERSIST] Persisting conversation to database via memory node...")
                        # Ensure we use the correct IDs for persistent storage
                        session_id = self.session_id
                        user_id = getattr(self, 'user_id', None)
                        chatflow_id = getattr(self, 'workflow_id', None)
                        
                        # Prepare messages to persist (Human + AI)
                        messages_to_save = []
                        if user_input and user_input.strip():
                            from langchain_core.messages import HumanMessage
                            messages_to_save.append(HumanMessage(content=user_input))
                        
                        messages_to_save.append(last_ai_message)
                        
                        # Save to database using BufferMemoryNode's persistent method
                        BufferMemoryNode().save_messages(session_id=session_id, messages=messages_to_save, user_id=user_id, chatflow_id=chatflow_id)
                        
                    except Exception as e:
                        print(f"   [ERROR] Failed to persist memory via _persist_to_database: {e}")


                return {"output": output_content}
            else:
                fallback_output = str(result)
                print(f"[AGENT OUTPUT] {fallback_output}")
                return {"output": fallback_output}

        except UnicodeEncodeError as unicode_error:
            print(f"[ERROR] Unicode encoding error: {unicode_error}")
            return self._handle_unicode_error(unicode_error)

        except Exception as e:
            error_msg = f"Agent graph execution failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {"error": error_msg}

    def _handle_unicode_error(self, unicode_error: UnicodeEncodeError) -> Dict[str, Any]:
        """Handle Unicode encoding errors with locale-specific fallback."""
        try:
            return {
                "error": f"Character encoding error: {str(unicode_error)}",
                "suggestion": "Please ensure characters are properly encoded or check system language settings."
            }
        except:
            return {"error": "Unicode encoding error occurred"}

    def _prepare_tools(self, tools_to_process: Any) -> list[BaseTool]:
        """Universal tool preparation using auto-discovery."""
        if not tools_to_process:
            return []
        
        tools_list = []
        tools_dict=tools_to_process
        if not isinstance(tools_to_process, dict):
            tools_dict=dict((key,d[key]) for d in tools_to_process for key in d)

        for tool_input in tools_dict:
            if isinstance(tools_dict[tool_input]['tool'], BaseTool):
                tools_list.append(tools_dict[tool_input]['tool'])
            else:
                # Use auto-discovery system
                converted_tool = self.auto_tool_manager.converter.convert_to_tool(tool_input)
                if converted_tool:
                    tools_list.append(converted_tool)
                    print(f"[TOOL] Auto-converted {type(tool_input).__name__} to tool: {converted_tool.name}")
        
        return tools_list

    def _create_prompt(self, tools: list[BaseTool]) -> ChatPromptTemplate:
        """Legacy method for backward compatibility."""
        return self._create_agent_prompt(tools)

    def _create_agent_prompt(self, tools: list[BaseTool], user_inputs: Dict[str, Any] = None) -> ChatPromptTemplate:
        """Create a compact agent prompt: fixed header + user system_prompt."""
        custom_instructions = ""
        if user_inputs and isinstance(user_inputs, dict):
            custom_instructions = (user_inputs.get("system_prompt") or "").strip()
        if not custom_instructions:
            custom_instructions = (self.user_data.get("system_prompt") or "").strip()
        if not custom_instructions:
            custom_instructions = "You are a helpful assistant."

        system_content = self._build_compact_system_prompt(
            custom_instructions=custom_instructions,
            has_tools=bool(tools)
        )

        return ChatPromptTemplate.from_messages([
            ("system", system_content),
            ("placeholder", "{messages}")
        ])

    def _build_compact_system_prompt(self, custom_instructions: str, has_tools: bool) -> str:
        """Build a compact system prompt.

        - No multilingual enforcement/detection.
        - No `User Input:` injection (user input is always a HumanMessage).
        - Escapes single { } to avoid template conflicts.
        """
        def escape_braces(text: str) -> str:
            if not text:
                return text
            result = []
            i = 0
            while i < len(text):
                if text[i:i + 2] == "{{":
                    result.append(text[i:i + 2])
                    i += 2
                elif text[i:i + 2] == "}}":
                    result.append(text[i:i + 2])
                    i += 2
                elif text[i] == "{":
                    result.append("{{")
                    i += 1
                elif text[i] == "}":
                    result.append("}}")
                    i += 1
                else:
                    result.append(text[i])
                    i += 1
            return "".join(result)

        custom_instructions = escape_braces(custom_instructions)
        header = "You are an agent running inside KAI-Fusion."
        tool_rule = (
            "Use tools when needed. If no tools are available, answer directly."
            if has_tools
            else "Answer directly (no tools connected)."
        )

        return f"{header}\n{tool_rule}\n\n{custom_instructions}".strip()

    def _save_conversation_to_database(self, session_id: str, user_content: str, ai_content: str, user_id: str):
        """Save conversation to database through memory service"""
        try:
            # Import database service
            from app.services.memory import db_memory_store
            
            if db_memory_store:
                result = db_memory_store.save_session_memory(
                    session_id=session_id,
                    user_input=user_content,
                    ai_response=ai_content,
                    user_id=user_id,
                    metadata={
                        'source': 'react_agent',
                        'agent_type': 'react_agent_node',
                        'timestamp': str(__import__('datetime').datetime.now())
                    }
                )
                if result:
                    print(f"   [SUCCESS] Database save successful: {result[:8]}...")
                else:
                    print(f"   [ERROR] Database save failed: empty result")
            else:
                print(f"   [WARNING] Database store not available")
                
        except Exception as e:
            print(f"   [WARNING] Database save exception: {e}")

# Alias for frontend compatibility
ToolAgentNode = ReactAgentNode
