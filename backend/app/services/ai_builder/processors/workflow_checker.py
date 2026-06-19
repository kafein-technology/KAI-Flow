import logging
from app.services.ai_builder.state import AIBuilderState

logger = logging.getLogger(__name__)


class WorkflowChecker:
    @staticmethod
    def route_validation(state: AIBuilderState) -> str:
        """
        Conditional edge router for LangGraph.
        State is always a dict (TypedDict), no BaseModel conversion needed.
        """
        errors = state.get("validation_errors", [])
        iteration = state.get("iteration", 0)

        if not errors:
            logger.info("AI Builder Validation successful! No errors found.")
            return "end"

        if iteration >= 3:
            logger.warning(f"AI Builder Max retries reached (3). Returning with remaining errors: {errors}")
            return "end"

        logger.info(f"AI Builder Validation failed with {len(errors)} errors. Sending back for self-healing (Iteration {iteration})...")
        return "builder"
