import logging
from typing import Dict, Any
from app.services.ai_builder.ai_builder_graph import generate_workflow as core_generate_workflow

logger = logging.getLogger(__name__)

class AIBuilderService:
    """
    Facade for the AI Builder service, wrapping the new LangGraph modular implementation.
    This maintains backward compatibility for any existing code calling AIBuilderService.
    """
    def __init__(self):
        # Dependencies like OpenAI API key and Validation engines are now managed
        # directly within their respective modular processors.
        pass

    async def generate_workflow(self, question: str, api_key: str, model_name: str = "gpt-4o", base_url: str = None, mode: str = "build", existing_workflow: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Delegates the AI workflow building to the modular LangGraph package.
        """
        logger.info(f"AIBuilderService wrapper called for mode: {mode}")
        return await core_generate_workflow(question, api_key, model_name, base_url, mode, existing_workflow)
