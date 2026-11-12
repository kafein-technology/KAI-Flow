"""A client for System One compatible decision APIs."""

from __future__ import annotations

import math
import re
from typing import Any, Dict

import httpx

from ...core.decision_api import (
    decision_endpoint, decision_models_endpoint, selected_endpoint_path,
)

from ..base import (
    NodeInput, NodeOutput, NodePosition, NodeProperty, NodePropertyType,
    NodeType, ProcessorNode,
)


def build_question(operation: str, instructions: Any, configuration: Dict[str, Any]) -> Dict[str, Any]:
    if operation not in ("noul", "choice", "score"):
        raise ValueError("Decision operation must be Noul (Yes/No), Choice, or Score.")
    if not isinstance(instructions, (str, dict, list)) or not instructions:
        raise ValueError("Decision instructions are required.")
    if isinstance(instructions, str) and not instructions.strip():
        raise ValueError("Decision instructions are required.")
    question: Dict[str, Any] = {"type": operation, "instructions": instructions}
    if operation == "noul":
        criteria = {}
        for key, property_name in (("true", "true_criterion"), ("false", "false_criterion")):
            value = str(configuration.get(property_name) or "").strip()
            if value:
                criteria[key] = value
        if criteria:
            question["criteria"] = criteria
    elif operation == "choice":
        rows = configuration.get("choice_criteria")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 255:
            raise ValueError("Choice requires between 1 and 255 options.")
        criteria = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Each choice must contain a name and description.")
            name = str(row.get("name") or "").strip()
            if not name or name in criteria or len(name) > 255:
                raise ValueError("Choice names must be unique and between 1 and 255 characters.")
            description = str(row.get("description") or "").strip()
            if len(description) > 255:
                raise ValueError("Choice descriptions must be 255 characters or fewer.")
            criteria[name] = description
        question["criteria"] = criteria
    else:
        levels = configuration.get("score_criteria")
        if not isinstance(levels, list) or not 2 <= len(levels) <= 10:
            raise ValueError("Score requires between 2 and 10 ordered levels.")
        criteria = [str(level).strip() for level in levels]
        if any(not level for level in criteria):
            raise ValueError("Every score level needs a description.")
        question["criteria"] = criteria
    return question


def build_questions(operation: str, instructions: Any, configuration: Dict[str, Any]) -> Dict[str, Any]:
    questions = {"decision": build_question(operation, instructions, configuration)}
    if operation != "noul":
        return questions
    additional = configuration.get("additional_questions", [])
    if not isinstance(additional, list):
        raise ValueError("Additional Noul questions must be a list.")
    for index, row in enumerate(additional, start=2):
        if not isinstance(row, dict):
            raise ValueError(f"Noul question {index} must contain instructions.")
        name = row.get("id", f"decision_{index}")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) or name in questions:
            raise ValueError("Noul question IDs must be unique and contain only letters, numbers, dots, underscores, or hyphens.")
        try:
            questions[name] = build_question("noul", row.get("instructions"), row)
        except ValueError as exc:
            raise ValueError(f"Noul question {index}: {exc}") from exc
    return questions


def _probability(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"Decision API returned an invalid {name}.")
    return float(value)


def parse_answer(response: Any, operation: str, question_name: str, threshold: float) -> Dict[str, Any]:
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise ValueError("Decision API response has no answers object.")
    answer = response["answers"].get(question_name)
    if not isinstance(answer, dict) or answer.get("type") != operation:
        raise ValueError("Decision API response does not contain the requested answer type.")
    if operation == "noul":
        probability = _probability(answer.get("noul"), "noul probability")
        value: Any = probability >= threshold
    elif operation == "choice":
        value = answer.get("choice")
        if not isinstance(value, str) or not value:
            raise ValueError("Decision API returned an invalid choice.")
    else:
        value = answer.get("score")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Decision API returned an invalid score.")
    result = {
        "type": operation,
        "value": value,
        "answer": answer,
        "model": response.get("model"),
        "usage": response.get("usage"),
    }
    if operation == "noul":
        result["probability"] = probability
        result["threshold"] = threshold
    else:
        if "confidence" in answer:
            result["confidence"] = _probability(answer["confidence"], "confidence")
        if "probabilities" in answer:
            result["probabilities"] = answer["probabilities"]
    return result


class DecisionModelNode(ProcessorNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "DecisionModelNode",
            "display_name": "Decision Model",
            "description": "Evaluate state with a configured decision model.",
            "category": "LLM",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": None, "path": "icons/decision.svg", "alt": "Decision Model"},
            "colors": ["blue-500", "cyan-600"],
            "inputs": [NodeInput(name="input", displayName="State", type="any", description="Fallback state when the node's State field is empty. Accepts text, an object, or an array.", is_connection=True, required=False, direction=NodePosition.LEFT)],
            "outputs": [NodeOutput(name="output", displayName="Decision", type="any", description="Decision value, complete answer, model, and usage. Multiple Noul questions also return a decisions object keyed by question ID.", is_connection=True, direction=NodePosition.RIGHT)],
            "properties": [
                NodeProperty(name="credential_id", displayName="Decision credential", type=NodePropertyType.CREDENTIAL_SELECT, serviceType="decision_model", description="Select a decision endpoint credential and model.", required=True),
                NodeProperty(name="state", displayName="State", type=NodePropertyType.TEXT_AREA, description="Content to evaluate. When empty, the connected State input is used. Supports workflow variables.", placeholder="Enter content or connect a node to State", default="", required=True, rows=5),
                NodeProperty(name="operation", displayName="Decision type", type=NodePropertyType.SELECT, description="Select the question and answer format.", default="noul", required=True, options=[{"label": "Noul (Yes/No)", "value": "noul"}, {"label": "Choice", "value": "choice"}, {"label": "Score", "value": "score"}]),
                NodeProperty(name="instructions", displayName="Instructions", type=NodePropertyType.TEXT_AREA, description="Question or statement to evaluate. Supports workflow variables.", placeholder="Is this message about billing?", default="", required=True, rows=4),
                NodeProperty(name="true_criterion", displayName="Yes / true means", type=NodePropertyType.TEXT, description="Optional clarification of what counts as yes or true.", default="", required=False, displayOptions={"show": {"operation": "noul"}}),
                NodeProperty(name="false_criterion", displayName="No / false means", type=NodePropertyType.TEXT, description="Optional clarification of what counts as no or false.", default="", required=False, displayOptions={"show": {"operation": "noul"}}),
                NodeProperty(name="additional_questions", displayName="Noul questions", type=NodePropertyType.DECISION_QUESTIONS, description="Ask one or more Yes/No questions about the same State. Each question returns its own decision.", default=[], required=False, displayOptions={"show": {"operation": "noul"}}),
                NodeProperty(name="choice_criteria", displayName="Choices", type=NodePropertyType.DECISION_CRITERIA, description="Each choice has a unique name and an optional description.", default=[{"name": "", "description": ""}], required=True, displayOptions={"show": {"operation": "choice"}}),
                NodeProperty(name="score_criteria", displayName="Score levels", type=NodePropertyType.DECISION_CRITERIA, description="Two to ten ordered levels, scored from 0 upward.", default=["", ""], required=True, displayOptions={"show": {"operation": "score"}}),
                NodeProperty(name="threshold", displayName="Yes threshold", type=NodePropertyType.NUMBER, description="A Yes / No probability at or above this value returns true.", default=0.5, min=0, max=1, step=0.01, required=True, displayOptions={"show": {"operation": "noul"}}),
            ],
        }

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        credential_id = inputs.get("credential_id")
        credential = self.get_credential(str(credential_id)) if credential_id else None
        if not credential or credential.get("service_type") != "decision_model":
            raise ValueError("Select a valid Decision Model credential.")
        secret = credential.get("secret")
        if not isinstance(secret, dict):
            raise ValueError("Decision Model credential is invalid.")
        endpoint = decision_endpoint(secret)
        model = str(secret.get("model_name") or inputs.get("model") or "").strip()
        if not model:
            raise ValueError("Select a model in the Decision Model credential.")
        connected_state = connected_nodes.get("input")
        if isinstance(connected_state, dict) and all(key in connected_state for key in ("nodeId", "success", "output")):
            connected_state = connected_state["output"]
        instructions = inputs.get("instructions")
        # Explicit input envelope permits a previous node to supply both dynamic values.
        if isinstance(connected_state, dict) and "state" in connected_state and "instructions" in connected_state:
            instructions = connected_state["instructions"]
            connected_state = connected_state["state"]
        configured_state = inputs.get("state")
        state = configured_state if configured_state is not None and (not isinstance(configured_state, str) or configured_state.strip()) else connected_state
        if not isinstance(state, (str, dict, list)) or (isinstance(state, str) and not state.strip()):
            raise ValueError("Enter State in the node or connect a State input.")
        operation = str(inputs.get("operation") or "noul")
        questions = build_questions(operation, instructions, inputs)
        try:
            threshold = float(inputs.get("threshold", 0.5))
        except (TypeError, ValueError):
            raise ValueError("Yes threshold must be between 0 and 1.") from None
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("Yes threshold must be between 0 and 1.")
        api_key = str(secret.get("api_key") or "").strip()
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                response = client.post(endpoint, headers=headers, json={"model": model, "state": state, "questions": questions})
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"Decision API returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise ValueError(f"Decision API connection failed: {type(exc).__name__}.") from exc
        except ValueError as exc:
            raise ValueError("Decision API returned invalid JSON.") from exc
        output = parse_answer(payload, operation, "decision", threshold)
        if len(questions) > 1:
            output["decisions"] = {
                name: parse_answer(payload, operation, name, threshold) for name in questions
            }
        return {"output": output}
