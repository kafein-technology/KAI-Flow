"""
KAI-Flow JSON Parser Node - JSON Processing & Extraction
=========================================================

Parses, cleans, and extracts data from raw JSON strings.
Particularly useful for handling messy LLM outputs that contain
escaped characters, markdown code blocks, or extra quotes.

Authors: KAI-Flow Development Team
Version: 1.0.0
"""

import json
import logging
import re
from typing import Any, Dict

from ..base import (
    NodeInput,
    NodeOutput,
    NodePosition,
    NodeProperty,
    NodePropertyType,
    NodeType,
    ProcessorNode,
)

logger = logging.getLogger(__name__)


class JsonParserNode(ProcessorNode):
    """
    JSON Parser Node - Parse, clean, and extract data from JSON strings.

    Handles common issues with LLM-generated JSON:
    - Escaped newlines and quotes
    - Markdown code block wrappers
    - Nested key extraction via dot notation
    """

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "JsonParserNode",
            "display_name": "JSON Parser",
            "description": (
                "Parse and clean raw JSON strings from LLM outputs or API responses. "
                "Supports automatic cleanup of escaped characters, markdown code blocks, "
                "and nested key extraction using dot notation."
            ),
            "category": "Processing",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": None, "path": "icons/json.svg", "alt": "json"},
            "colors": ["emerald-500", "teal-600"],
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="string",
                    description="Raw JSON data from a connected node",
                    is_connection=True,
                    required=False,
                    direction=NodePosition.LEFT,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Output",
                    type="any",
                    description="Parsed and cleaned JSON output",
                    is_connection=True,
                    direction=NodePosition.RIGHT,
                ),
            ],
            "properties": [
                NodeProperty(
                    name="json_input",
                    displayName="JSON Input",
                    type=NodePropertyType.TEXT_AREA,
                    description=(
                        "Raw JSON string to parse. "
                        "Leave empty to use connected node input."
                    ),
                    default="",
                    required=False,
                    placeholder='{"key": "value"}',
                    rows=8,
                    tabName="basic",
                ),
                NodeProperty(
                    name="parse_mode",
                    displayName="Parse Mode",
                    type=NodePropertyType.SELECT,
                    description="How to parse the input JSON",
                    default="auto",
                    required=True,
                    options=[
                        {
                            "label": "Auto",
                            "value": "auto",
                            "hint": "Clean up common issues and parse",
                        },
                        {
                            "label": "Strict",
                            "value": "strict",
                            "hint": "Parse as-is without cleanup",
                        },
                        {
                            "label": "Extract",
                            "value": "extract",
                            "hint": "Parse and extract a specific key",
                        },
                    ],
                    tabName="basic",
                ),
                NodeProperty(
                    name="extract_key",
                    displayName="Extract Key",
                    type=NodePropertyType.TEXT,
                    description=(
                        "Dot-notation path to extract a nested value. "
                        "Example: data.results[0].name"
                    ),
                    default="",
                    required=False,
                    placeholder="data.results[0].name",
                    tabName="basic",
                ),
                NodeProperty(
                    name="clean_output",
                    displayName="Clean Output",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Remove escaped newlines, extra quotes, "
                        "and markdown code block wrappers before parsing"
                    ),
                    default=True,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="pretty_print",
                    displayName="Pretty Print",
                    type=NodePropertyType.CHECKBOX,
                    description="Format the output JSON with indentation",
                    default=False,
                    required=False,
                    tabName="advanced",
                ),
            ],
        }

        logger.info("JSON Parser Node initialized")

    def _extract_primary_output(self, input_data: Any) -> Any:
        """
        Extract the primary output value from a connected node.

        Follows the same priority as Jinja templating to keep
        behavior consistent across connection-based and template-based inputs.
        """
        if input_data is None:
            return None

        if hasattr(input_data, "page_content"):
            return input_data.page_content

        if isinstance(input_data, dict):
            if "output" in input_data:
                return input_data["output"]
            if "page_content" in input_data:
                return input_data["page_content"]
            if "content" in input_data:
                return input_data["content"]
            if len(input_data) == 1:
                return next(iter(input_data.values()))
            return input_data

        if isinstance(input_data, list) and len(input_data) > 0:
            first = input_data[0]
            if hasattr(first, "page_content"):
                return "\n\n".join(
                    doc.page_content
                    for doc in input_data
                    if hasattr(doc, "page_content")
                )
            if isinstance(first, dict) and "page_content" in first:
                return "\n\n".join(
                    doc["page_content"]
                    for doc in input_data
                    if "page_content" in doc
                )

        return input_data

    def _strip_wrappers(self, raw: str) -> str:
        """
        Remove markdown code fences and surrounding quotes without
        touching escape sequences. This is safe to run before json.loads().
        """
        text = raw.strip()

        # Strip markdown code blocks
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text)
        if match:
            text = match.group(1).strip()

        # Remove wrapping double-quotes around the whole JSON object/array
        if (
            len(text) >= 2
            and text[0] == '"'
            and text[-1] == '"'
            and (text[1] in "{[" or text[-2] in "}]")
        ):
            try:
                inner = json.loads(text)
                if isinstance(inner, str):
                    text = inner
            except (json.JSONDecodeError, ValueError):
                pass

        return text.strip()

    def _unescape_and_parse(self, text: str) -> Any:
        """
        Fallback parser for double-escaped LLM output.

        Only called when the initial json.loads() fails, so we know the
        input is not valid JSON as-is. Replacing literal \\n / \\t here
        is safe because the original parse already failed.
        """
        unescaped = text.replace("\\n", "\n").replace("\\t", "\t")
        return json.loads(unescaped)

    def _extract_by_key(self, data: Any, key_path: str) -> Any:
        """
        Extract a nested value using dot-notation with array index support.

        Examples:
            "name"              -> data["name"]
            "data.items"        -> data["data"]["items"]
            "data.items[0]"     -> data["data"]["items"][0]
            "results[0].title"  -> data["results"][0]["title"]
        """
        current = data
        tokens = re.split(r"\.", key_path)

        for token in tokens:
            if not token:
                continue

            # Check for array index: e.g. "items[0]"
            idx_match = re.match(r"^(\w+)\[(\d+)\]$", token)
            if idx_match:
                key_part = idx_match.group(1)
                index = int(idx_match.group(2))
                if isinstance(current, dict) and key_part in current:
                    current = current[key_part]
                else:
                    raise KeyError(
                        f"Key '{key_part}' not found in {type(current).__name__}"
                    )
                if isinstance(current, list) and index < len(current):
                    current = current[index]
                else:
                    raise IndexError(
                        f"Index {index} out of range for '{key_part}' "
                        f"(length {len(current) if isinstance(current, list) else 'N/A'})"
                    )
            elif isinstance(current, dict) and token in current:
                current = current[token]
            else:
                raise KeyError(
                    f"Key '{token}' not found in {type(current).__name__}"
                )

        return current

    def execute(
        self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse, clean, and optionally extract data from JSON input.
        """
        logger.info("Executing JSON Parser Node")

        json_input = inputs.get("json_input", "")
        parse_mode = inputs.get("parse_mode", "auto")
        extract_key = inputs.get("extract_key", "")
        clean_output = inputs.get("clean_output", True)
        pretty_print = inputs.get("pretty_print", False)

        # Resolve input source
        raw_text = json_input
        if not raw_text or (isinstance(raw_text, str) and not raw_text.strip()):
            connected = connected_nodes.get("input")
            if connected is not None:
                extracted = self._extract_primary_output(connected)
                if isinstance(extracted, str):
                    raw_text = extracted
                elif isinstance(extracted, (dict, list)):
                    # Already parsed - skip the string->parse roundtrip
                    raw_text = extracted
                else:
                    try:
                        raw_text = json.dumps(extracted, ensure_ascii=False)
                    except (TypeError, ValueError) as e:
                        logger.warning(
                            f"Connected node output is not JSON-serializable: {e}"
                        )
                        return {
                            "output": None,
                            "parsed_data": None,
                            "is_valid": False,
                            "error": (
                                f"Connected node output is not JSON-serializable: {e}"
                            ),
                        }

        if not raw_text or (isinstance(raw_text, str) and not raw_text.strip()):
            return {
                "output": None,
                "parsed_data": None,
                "is_valid": False,
                "error": "No input provided. Connect a node or enter JSON manually.",
            }

        # If input is already a dict/list, skip parsing
        if isinstance(raw_text, (dict, list)):
            parsed = raw_text
        else:
            text_to_parse = raw_text

            # Step 1: strip wrappers (code fences, outer quotes) - always safe
            if clean_output and parse_mode != "strict":
                text_to_parse = self._strip_wrappers(raw_text)

            # Step 2: try parsing the cleaned text first
            try:
                parsed = json.loads(text_to_parse)
            except json.JSONDecodeError:
                # Step 3: fallback - unescape double-escaped sequences and retry
                if clean_output and parse_mode != "strict":
                    try:
                        parsed = self._unescape_and_parse(text_to_parse)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON parse error: {e}")
                        return {
                            "output": raw_text,
                            "parsed_data": None,
                            "is_valid": False,
                            "error": f"Invalid JSON: {e}",
                        }
                else:
                    logger.warning("JSON parse error in strict mode")
                    return {
                        "output": raw_text,
                        "parsed_data": None,
                        "is_valid": False,
                        "error": "Invalid JSON in strict mode",
                    }

        # Extract specific key if requested
        if parse_mode == "extract" and extract_key:
            try:
                parsed = self._extract_by_key(parsed, extract_key)
            except (KeyError, IndexError, TypeError) as e:
                logger.warning(f"Key extraction error: {e}")
                return {
                    "output": None,
                    "parsed_data": parsed,
                    "is_valid": False,
                    "error": f"Extraction failed: {e}",
                }

        # Format output
        if isinstance(parsed, (dict, list)):
            indent = 2 if pretty_print else None
            output_str = json.dumps(parsed, ensure_ascii=False, indent=indent)
        else:
            output_str = str(parsed)

        logger.info(f"JSON parsed successfully (mode={parse_mode})")

        return {
            "output": output_str,
            "parsed_data": parsed,
            "is_valid": True,
            "error": None,
        }