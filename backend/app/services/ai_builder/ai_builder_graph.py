import os
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from app.services.ai_builder.state import AIBuilderState, AIBuilderStateBuilder
from app.services.ai_builder.processors import (
    BuilderProcessor,
    EditGuardProcessor,
    ValidationProcessor,
    NodeSelectorProcessor,
    WorkflowChecker,
)

logger = logging.getLogger(__name__)

# ─── Singleton Compiled Graph ──────────────────────────────────
# Compiled once on first use, reused for all subsequent requests.
# This avoids re-instantiating processors and re-compiling the graph
# on every API call, matching the efficiency of the original architecture.

_compiled_graph = None
_node_selector_processor = None
_builder_processor = None
_edit_guard_processor = None
_validation_processor = None


def _build_graph():
    """
    Constructs and compiles the AI Builder workflow graph using LangGraph.
    Processor instances are created once and reused via module-level singletons.
    """
    global _node_selector_processor, _builder_processor, _edit_guard_processor, _validation_processor

    _node_selector_processor = NodeSelectorProcessor()
    _builder_processor = BuilderProcessor()
    _edit_guard_processor = EditGuardProcessor()
    _validation_processor = ValidationProcessor()

    workflow = StateGraph(AIBuilderState)

    # With TypedDict state, LangGraph passes plain dicts directly.
    # No BaseModel conversion needed — processors receive and return dicts.
    async def node_selector_node(state: AIBuilderState) -> Dict[str, Any]:
        return await _node_selector_processor.process(state)

    async def builder_node(state: AIBuilderState) -> Dict[str, Any]:
        return await _builder_processor.process(state)

    def edit_guard_node(state: AIBuilderState) -> Dict[str, Any]:
        return _edit_guard_processor.process(state)

    def validator_node(state: AIBuilderState) -> Dict[str, Any]:
        return _validation_processor.process(state)

    workflow.add_node("node_selector", node_selector_node)
    workflow.add_node("builder", builder_node)
    workflow.add_node("edit_guard", edit_guard_node)
    workflow.add_node("validator", validator_node)

    workflow.set_entry_point("node_selector")
    workflow.add_edge("node_selector", "builder")
    workflow.add_edge("builder", "edit_guard")
    workflow.add_edge("edit_guard", "validator")

    workflow.add_conditional_edges(
        "validator",
        WorkflowChecker.route_validation,
        {"builder": "builder", "end": END}
    )

    return workflow.compile()


def get_compiled_graph():
    """Returns the singleton compiled graph, building it on first call."""
    global _compiled_graph
    if _compiled_graph is None:
        logger.info("Compiling AI Builder LangGraph (one-time initialization)...")
        _compiled_graph = _build_graph()
        logger.info("AI Builder LangGraph compiled successfully.")
    return _compiled_graph


async def generate_workflow(question: str, api_key: str, model_name: str = "gpt-4o", base_url: str = None, mode: str = "build", existing_workflow: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Entrypoint function that initializes the state and invokes the LangGraph pipeline.
    """
    # Configure LangSmith tracing if available
    ls_api_key = os.getenv("LANGCHAIN_API_KEY")
    if ls_api_key:
        os.environ["LANGCHAIN_API_KEY"] = ls_api_key
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "KAI")
        os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    compiled_graph = get_compiled_graph()
    initial_state = AIBuilderStateBuilder.create_initial_state(question, api_key, model_name, base_url, mode, existing_workflow)

    # TypedDict state is a plain dict — LangGraph handles it natively, no conversion needed.
    final_state = await compiled_graph.ainvoke(initial_state)

    # Check if the request was flagged as invalid/irrelevant
    if final_state.get("invalid_request"):
        return {
            "invalid_request": True,
            "message": final_state.get("invalid_request_message", "Your request does not appear to be a workflow edit."),
            "nodes": [],
            "edges": []
        }

    return final_state.get("current_workflow", {"nodes": [], "edges": []})
