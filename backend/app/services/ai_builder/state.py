from typing import TypedDict, Dict, Any, List


class AIBuilderState(TypedDict):
    """
    TypedDict-based state for the AI Builder LangGraph.
    TypedDict is used instead of Pydantic BaseModel for native LangGraph compatibility,
    as LangGraph's state management is optimized for TypedDict/dict-based state objects.
    """
    question: str
    iteration: int
    current_workflow: Dict[str, Any]
    original_workflow: Dict[str, Any]
    mode: str
    validation_errors: List[str]
    messages: List[Dict[str, str]]
    selected_nodes: List[str]
    api_key: str
    model_name: str
    base_url: str
    invalid_request: bool
    invalid_request_message: str


class AIBuilderStateBuilder:
    """
    Builder class responsible for standardizing the initialization of the state graph.
    """
    @staticmethod
    def create_initial_state(question: str, api_key: str, model_name: str = "gpt-4o", base_url: str = None, mode: str = "build", existing_workflow: Dict[str, Any] = None) -> AIBuilderState:
        return {
            "question": question,
            "mode": mode,
            "original_workflow": existing_workflow or {},
            "iteration": 0,
            "current_workflow": {},
            "validation_errors": [],
            "messages": [],
            "selected_nodes": [],
            "api_key": api_key,
            "model_name": model_name,
            "base_url": base_url or ""
        }
