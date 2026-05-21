"""
KAI-Flow JSON Parser Node
=========================

A resilient JSON parsing processing node designed to extract, clean, and reliably 
parse malformed/dirty JSON outputs from LLMs and external systems.
"""
import json
import yaml
import re
import ast
import logging
from typing import Dict, Any

from langchain_core.runnables import Runnable, RunnableLambda
from ..base import (
    ProcessorNode,
    NodeInput,
    NodeOutput,
    NodeType,
    NodeProperty,
    NodePropertyType,
    NodePosition,
)

logger = logging.getLogger(__name__)

class JsonParserNode(ProcessorNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "JsonParserNode",
            "display_name": "Parser",
            "description": (
                "Safely parse stringified or dirty JSON (e.g., from LLMs). "
                "Handles markdown code blocks, escapes, and malformed structures."
            ),
            "category": "Processing",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "custom_parser", "path": "icons/parser.svg", "alt": "Parser"},
            "colors": ["purple-400", "purple-600"],
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="any",
                    description="Input data to parse. If unlinked, reads from the Template property.",
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
                    description="Parsed JSON (Dict or List). If failed, returns an error dict object.",
                    is_connection=True,
                    direction=NodePosition.RIGHT,
                ),
            ],
            "properties": [
                NodeProperty(
                    name="format",
                    displayName="Output Format",
                    type=NodePropertyType.SELECT,
                    description="Select the output format. JSON returns a parsed dict/list, YAML returns a formatted YAML string.",
                    required=True,
                    default="json",
                    options=[
                        {"label": "JSON", "value": "json"},
                        {"label": "YAML", "value": "yaml"}
                    ]
                ),
                NodeProperty(
                    name="template",
                    displayName="Input",
                    type=NodePropertyType.TEXT_AREA,
                    description="Use Jinja to process input from other nodes (e.g., ${{agent}}). Leave empty to use direct input.",
                    required=True,
                    default="",
                    rows=4
                ),
            ],
        }

    def _extract_primary_output(self, input_data: Any) -> Any:
        """Extract primary output value from node output dynamically."""
        if input_data is None:
            return None
        
        # Handle LangChain Document
        if hasattr(input_data, 'page_content'):
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
            if hasattr(first, 'page_content'):
                return "\n\n".join(str(doc.page_content) for doc in input_data if hasattr(doc, 'page_content'))
            if isinstance(first, dict) and "page_content" in first:
                return "\n\n".join(str(doc.get("page_content", "")) for doc in input_data if "page_content" in doc)
        
        return input_data

    def _clean_json_string(self, text: Any) -> str:
        """Strip markdown blocks and find JSON boundaries to handle messy LLM output."""
        # Safe-cast to block external non-string types accessing string operators
        if not isinstance(text, str):
            text = str(text)
            
        text = text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```.*$", "", text, flags=re.DOTALL)
        
        text = text.strip()

        # Find first { or [
        start_dict = text.find("{")
        start_list = text.find("[")
        if start_dict == -1 and start_list == -1:
            return text
        
        # Determine the earliest valid start block
        if start_dict != -1 and start_list != -1:
            start_idx = min(start_dict, start_list)
        else:
            start_idx = max(start_dict, start_list)

        is_dict = (text[start_idx] == "{")
        end_char = "}" if is_dict else "]"

        # Find the last matching end character mapping
        end_idx = text.rfind(end_char)
        if end_idx != -1 and end_idx >= start_idx:
            text = text[start_idx:end_idx + 1]

        return text

    def _parse_json(self, raw_data: Any) -> Any:
        """Attempt multiple strategies to meticulously parse and fix JSON."""
        # Immediately return valid objects without execution
        if isinstance(raw_data, (dict, list)):
            return raw_data
        
        # Cast defensively into string to prevent proxy objects from leaking
        try:
            str_data = str(raw_data) if not isinstance(raw_data, str) else raw_data
        except Exception:
            return raw_data
        
        # Strategy 1: Direct JSON parse
        try:
            return json.loads(str_data)
        except Exception:
            pass

        # Strategy 2: Clean and parse (Strip Markdown)
        try:
            cleaned_str = self._clean_json_string(str_data)
            return json.loads(cleaned_str)
        except Exception:
            pass

        # Strategy 3: Fix trailing commas format issue (common LLM error)
        try:
            cleaned_str = self._clean_json_string(str_data)
            fixed_str = re.sub(r",\s*([\]}])", r"\1", cleaned_str)
            return json.loads(fixed_str)
        except Exception:
            pass

        # Strategy 4: Python ast.literal_eval (Handles missing quotes and True/False bindings)
        try:
            cleaned_str = self._clean_json_string(str_data)
            pythonic_str = cleaned_str.replace("true", "True").replace("false", "False").replace("null", "None")
            parsed = ast.literal_eval(pythonic_str)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass

        # Guard slice extraction with explicit strictly typed string conversions
        # This fixes 'unhashable type: slice' when objects respond to `[:N]` like dictionaries
        safe_prefix = str(str_data)[:150] if str_data else ""
        raise ValueError(f"Failed to parse JSON cleanly. Raw string prefix: {safe_prefix}...")

    def _clean_yaml_string(self, text: Any) -> str:
        """Strip markdown blocks to handle messy LLM YAML output."""
        if not isinstance(text, str):
            text = str(text)
            
        text = text.strip()
        
        # Robustly extract yaml payload if wrapped in markdown anywhere in the text
        match = re.search(r"```(?:yaml)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
        # Fallback for unclosed blocks starting at the beginning
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```.*$", "", text, flags=re.DOTALL)
            
        return text.strip()

    def _parse_yaml(self, raw_data: Any) -> Any:
        """Attempt multiple strategies to meticulously parse and fix YAML."""
        # Immediately return valid objects without execution
        if isinstance(raw_data, (dict, list)):
            return raw_data
        
        # Cast defensively into string
        try:
            str_data = str(raw_data) if not isinstance(raw_data, str) else raw_data
        except Exception:
            return raw_data
            
        # Strategy 1: Direct YAML parse
        try:
            parsed = yaml.safe_load(str_data)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass
            
        # Strategy 2: Clean and parse (Strip Markdown)
        try:
            cleaned_str = self._clean_yaml_string(str_data)
            parsed = yaml.safe_load(cleaned_str)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass
            
        # Strategy 3: Clean and fix common YAML issues (replace tabs with spaces)
        try:
            cleaned_str = self._clean_yaml_string(str_data)
            # PyYAML hates tabs for indentation. Replace them globally with 2 spaces.
            no_tabs_str = cleaned_str.replace('\t', '  ')
            parsed = yaml.safe_load(no_tabs_str)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass

        # Strategy 3.5: Handle YAML with Windows-style line endings
        try:
            cleaned_str = self._clean_yaml_string(str_data)
            normalized_str = cleaned_str.replace('\r\n', '\n').replace('\r', '\n')
            no_tabs_str = normalized_str.replace('\t', '  ')
            parsed = yaml.safe_load(no_tabs_str)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass

        # Strategy 4: Fallback to JSON parser if YAML completely fails but it looks like JSON
        # LLMs often output JSON when asked for YAML
        try:
            cleaned_str = self._clean_yaml_string(str_data)
            if '{' in cleaned_str or '[' in cleaned_str:
                return self._parse_json(cleaned_str)
        except Exception:
            pass
            
        safe_prefix = str(str_data)[:150] if str_data else ""
        raise ValueError(f"Failed to parse YAML cleanly. Raw string prefix: {safe_prefix}...")

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """Execute parsing and optional formatting based on desired target format."""
        logger.info("Executing JsonParserNode dynamically")
        
        # Read properties from inputs first (contains Jinja-rendered values from NodeExecutor),
        # fallback to user_data for backward compatibility (direct invocation / non-templated values)
        template_val = inputs.get("template", "") or getattr(self, "user_data", {}).get("template", "")
        format_type = inputs.get("format", "") or getattr(self, "user_data", {}).get("format", "json")
        
        logger.debug(f"JsonParserNode format_type={format_type}, template_val_len={len(str(template_val)) if template_val else 0}")
        
        # Dynamically determine the string/data stream to parse: priority template > fallback to connection input
        actual_value = template_val
        if actual_value is None or (isinstance(actual_value, str) and not actual_value.strip()):
            input_data = connected_nodes.get("input", None)
            actual_value = self._extract_primary_output(input_data)
            
        if actual_value is None or actual_value == "":
            logger.warning("JsonParserNode received entirely empty input.")
            return {
                "output": {},
                "success": False,
                "error": "Empty input provided to parser."
            }

        try:
            # Step 1: Parse input into a Python Dict/List
            if isinstance(actual_value, (dict, list)):
                parsed_result = actual_value
            else:
                # Parse based on selected format (try selected format first, then fallback)
                if format_type.lower() == "yaml":
                    try:
                        parsed_result = self._parse_yaml(actual_value)
                    except ValueError:
                        # Fallback: LLMs sometimes output JSON even when asked for YAML
                        parsed_result = self._parse_json(actual_value)
                else:
                    try:
                        parsed_result = self._parse_json(actual_value)
                    except ValueError:
                        parsed_result = self._parse_yaml(actual_value)
            
            # Step 2: Format output heavily based on user preference
            if format_type.lower() == "yaml":
                import yaml
                # Format python structure into beautiful structural YAML
                yaml_str = yaml.dump(
                    parsed_result, 
                    default_flow_style=False, 
                    sort_keys=False, 
                    allow_unicode=True
                )
                
                # Strip potential trailing newlines for clean output
                yaml_str = yaml_str.strip()
                
                return {
                    "output": yaml_str,
                    "success": True,
                    "is_json_valid": True
                }
            else:
                # Format as dynamic properties natively
                if isinstance(parsed_result, dict):
                    output_dict = {
                        "output": parsed_result,
                        "success": True,
                        "is_json_valid": True
                    }
                    # Unpack properties safely without overwriting structural keys
                    for k, v in parsed_result.items():
                        if k not in output_dict:
                            output_dict[k] = v
                    return output_dict
                
                # List format or primitive types after parse mapping
                return {
                    "output": parsed_result,
                    "success": True,
                    "is_json_valid": True
                }
        except ValueError as e:
            # Fallback output payload ensuring error visibility
            logger.error(f"JsonParserNode execution failed dynamically: {e}")
            return {
                "output": str(actual_value),  # Aggressively enforce string output on fails to avoid mapping leaks
                "success": False,
                "is_json_valid": False,
                "error": str(e)
            }
