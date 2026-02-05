"""
KAI-Fusion Condition Node - Conditional Workflow Routing Engine
================================================================

This module implements a Condition Node for the KAI-Fusion platform,
providing conditional routing capabilities for workflow execution.
Similar to n8n and Flowise condition nodes, this node evaluates
string conditions and routes the workflow to True or False outputs.

ARCHITECTURAL OVERVIEW:
======================

The Condition Node serves as a conditional branching point in workflows,
allowing users to define conditions that determine the execution path.

┌─────────────────────────────────────────────────────────────────┐
│                  Condition Node Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input Data → [Source Selection] → [Value Extraction]          │
│       ↓               ↓                    ↓                    │
│  [Operation Select] → [Condition Evaluation] → [Routing]       │
│       ↓               ↓                    ↓                    │
│  [True Output] ←────────────────────→ [False Output]           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

SUPPORTED OPERATIONS:
====================

1. **Contains**: Check if value1 contains value2
2. **Ends With**: Check if value1 ends with value2
3. **Equal**: Check if value1 equals value2
4. **Not Contains**: Check if value1 does not contain value2
5. **Not Equal**: Check if value1 does not equal value2
6. **Regex**: Check if value1 matches regex pattern in value2
7. **Starts With**: Check if value1 starts with value2
8. **Is Empty**: Check if value1 is empty or None
9. **Not Empty**: Check if value1 is not empty

AUTHORS: KAI-Fusion Development Team
VERSION: 1.0.0
LICENSE: Proprietary - KAI-Fusion Platform
"""

import re
import logging
from typing import Dict, Any, Optional

from ..base import ProcessorNode, NodeInput, NodeOutput, NodeType, NodeProperty, NodePropertyType, NodePosition

logger = logging.getLogger(__name__)


class ConditionNode(ProcessorNode):
    """
    Condition Node for Conditional Workflow Routing
    ================================================

    This node evaluates string conditions and routes workflow execution
    to either the True or False output based on the condition result.

    CORE CAPABILITIES:
    =================

    1. **String Condition Evaluation**:
       - Multiple comparison operations
       - Regex pattern matching support
       - Empty/Not Empty checks

    2. **Flexible Input Sources**:
       - Connected node output
       - Direct value input

    3. **Dual Output Routing**:
       - True output for successful conditions
       - False output for failed conditions
    """

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "ConditionNode",
            "display_name": "Condition",
            "description": (
                "Evaluate string conditions and route workflow execution. "
                "Supports operations like Contains, Equal, Regex, and more."
            ),
            "category": "Processing",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "Condition", "path": "icons/condition.svg", "alt": "condition"},
            "colors": ["yellow-500", "orange-500"],

            # Single connection input
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="string",
                    description="Input data from connected node to evaluate condition against",
                    is_connection=True,
                    required=False,
                    direction=NodePosition.LEFT
                ),
            ],

            # Two outputs for conditional routing
            "outputs": [
                NodeOutput(
                    name="true_output",
                    displayName="True",
                    type="any",
                    description="Output when condition evaluates to True",
                    is_connection=True,
                    direction=NodePosition.RIGHT
                ),
                NodeOutput(
                    name="false_output",
                    displayName="False",
                    type="any",
                    description="Output when condition evaluates to False",
                    is_connection=True,
                    direction=NodePosition.RIGHT
                ),
            ],

            # UI Properties - 4 sections as specified
            "properties": [
                # 1. Data Type dropdown - accepts only string
                NodeProperty(
                    name="data_type",
                    displayName="Data Type",
                    type=NodePropertyType.SELECT,
                    description="Select the data type for condition evaluation",
                    default="string",
                    required=True,
                    options=[
                        {"label": "String", "value": "string"},
                    ],
                    tabName="basic"
                ),

                # 2. Value1 - text input
                NodeProperty(
                    name="value1",
                    displayName="Value 1",
                    type=NodePropertyType.TEXT,
                    description="First value for comparison. Use {{node_name}} for Jinja templating to access connected node output.",
                    default="",
                    required=True,
                    placeholder="Enter value or use {{node_name}}",
                    tabName="basic"
                ),

                # 3. Operation dropdown
                NodeProperty(
                    name="operation",
                    displayName="Operation",
                    type=NodePropertyType.SELECT,
                    description="Select the comparison operation to perform",
                    default="equal",
                    required=True,
                    options=[
                        {"label": "Contains", "value": "contains", "hint": "Check if value contains the specified text"},
                        {"label": "Ends With", "value": "ends_with", "hint": "Check if value ends with the specified text"},
                        {"label": "Equal", "value": "equal", "hint": "Check if values are exactly equal"},
                        {"label": "Not Contains", "value": "not_contains", "hint": "Check if value does not contain the specified text"},
                        {"label": "Not Equal", "value": "not_equal", "hint": "Check if values are not equal"},
                        {"label": "Regex", "value": "regex", "hint": "Check if value matches regex pattern"},
                        {"label": "Starts With", "value": "starts_with", "hint": "Check if value starts with the specified text"},
                        {"label": "Is Empty", "value": "is_empty", "hint": "Check if value is empty or None"},
                        {"label": "Not Empty", "value": "not_empty", "hint": "Check if value is not empty"},
                    ],
                    tabName="basic"
                ),

                # 4. Value2 - text input
                NodeProperty(
                    name="value2",
                    displayName="Value 2",
                    type=NodePropertyType.TEXT,
                    description="Second value for comparison (not used for Is Empty/Not Empty operations)",
                    default="",
                    required=True,
                    placeholder="Enter comparison value",
                    tabName="basic"
                ),

                # Advanced: Case sensitivity option
                NodeProperty(
                    name="case_sensitive",
                    displayName="Case Sensitive",
                    type=NodePropertyType.CHECKBOX,
                    description="Enable case-sensitive comparison (default: case-insensitive)",
                    default=False,
                    required=False,
                    tabName="advanced"
                ),
            ]
        }

        logger.info("Condition Node initialized")

    def _evaluate_condition(
        self, 
        value1: str, 
        operation: str, 
        value2: str, 
        case_sensitive: bool = False
    ) -> bool:
        """
        Evaluate the condition based on the selected operation.

        Args:
            value1: The value to test
            operation: The comparison operation to perform
            value2: The value to compare against
            case_sensitive: Whether the comparison should be case-sensitive

        Returns:
            Boolean result of the condition evaluation
        """
        try:
            # Convert to strings and handle None
            v1 = str(value1) if value1 is not None else ""
            v2 = str(value2) if value2 is not None else ""

            # Apply case sensitivity
            if not case_sensitive:
                v1 = v1.lower()
                v2 = v2.lower()

            logger.debug(f"Evaluating condition: '{v1}' {operation} '{v2}'")

            if operation == "contains":
                return v2 in v1
            
            elif operation == "ends_with":
                return v1.endswith(v2)
            
            elif operation == "equal":
                return v1 == v2
            
            elif operation == "not_contains":
                return v2 not in v1
            
            elif operation == "not_equal":
                return v1 != v2
            
            elif operation == "regex":
                try:
                    # For regex, use original value1 to preserve case if needed
                    original_v1 = str(value1) if value1 is not None else ""
                    flags = 0 if case_sensitive else re.IGNORECASE
                    pattern = re.compile(value2, flags)
                    return bool(pattern.search(original_v1))
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{value2}': {e}")
                    return False
            
            elif operation == "starts_with":
                return v1.startswith(v2)
            
            elif operation == "is_empty":
                # Check original value before lowercase conversion
                original_v1 = str(value1) if value1 is not None else ""
                return original_v1.strip() == "" or value1 is None
            
            elif operation == "not_empty":
                # Check original value before lowercase conversion
                original_v1 = str(value1) if value1 is not None else ""
                return original_v1.strip() != "" and value1 is not None
            
            else:
                logger.warning(f"Unknown operation: {operation}")
                return False

        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

    def _extract_primary_output(self, input_data: Any) -> Any:
        """
        Extract primary output value from node output.
        
        Uses the SAME logic as Jinja templating (_get_primary_output_for_node)
        to ensure consistent behavior between:
        - Connection-based input (when value1 is empty)
        - Jinja templating ({{node_name}})
        
        Priority Order:
        1. LangChain Document object (page_content attribute)
        2. "output" key
        3. "page_content" key (serialized Document)
        4. "content" key  
        5. If dict has single key, return that value
        6. Otherwise return entire input
        
        Args:
            input_data: Raw input from connected node
            
        Returns:
            Extracted primary output value
        """
        if input_data is None:
            return None
        
        # Handle LangChain Document objects directly
        if hasattr(input_data, 'page_content'):
            return input_data.page_content
            
        if isinstance(input_data, dict):
            # Priority 1: "output" key (most common - StringInputNode, CodeNode, etc.)
            if "output" in input_data:
                return input_data["output"]
            
            # Priority 2: "page_content" key (serialized Document object)
            if "page_content" in input_data:
                return input_data["page_content"]
            
            # Priority 3: "content" key (HttpClientNode, etc.)
            if "content" in input_data:
                return input_data["content"]
            
            # Priority 4: Single key dict - return that value
            if len(input_data) == 1:
                return next(iter(input_data.values()))
            
            # Priority 5: Return entire dict for complex structures
            return input_data
        
        # Handle list of Document objects
        if isinstance(input_data, list) and len(input_data) > 0:
            first_item = input_data[0]
            if hasattr(first_item, 'page_content'):
                # Join all page_contents from documents
                return "\n\n".join(doc.page_content for doc in input_data if hasattr(doc, 'page_content'))
            if isinstance(first_item, dict) and "page_content" in first_item:
                return "\n\n".join(doc["page_content"] for doc in input_data if "page_content" in doc)
        
        # For non-dict types (str, int, etc.), return as-is
        return input_data

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the condition node with the provided inputs and context.

        Args:
            inputs: User-provided configuration from properties
            connected_nodes: Connected node outputs

        Returns:
            Dict with condition result and routed outputs
        """
        logger.info("Executing Condition Node")

        # Get configuration from inputs (properties)
        data_type = inputs.get("data_type", "string")
        value1 = inputs.get("value1", "")
        operation = inputs.get("operation", "equal")
        value2 = inputs.get("value2", "")
        case_sensitive = inputs.get("case_sensitive", False)

        logger.info(f"CONDITION CONFIG: DataType={data_type}, Operation={operation}, CaseSensitive={case_sensitive}")

        # Get value to evaluate - use value1 from properties directly
        # Jinja templating will already be resolved by the time we get here
        actual_value = value1
        raw_input = None
        
        # If value1 is empty, try to get from connected input
        if actual_value is None or (isinstance(actual_value, str) and not actual_value.strip()):
            input_data = connected_nodes.get("input", "")
            raw_input = input_data  # Store raw input for type validation
            
            # DEBUG: Log what we received from connected node
            logger.info(f"RAW connected_nodes: {connected_nodes}")
            logger.info(f"RAW input_data type: {type(input_data)}")
            logger.info(f"RAW input_data: {str(input_data)[:500]}")
            if isinstance(input_data, dict):
                logger.info(f"input_data keys: {list(input_data.keys())}")
            
            # Extract primary output using same logic as Jinja templating
            # This ensures consistent behavior between {{node}} and connection
            actual_value = self._extract_primary_output(input_data)
            logger.info(f"EXTRACTED actual_value: {str(actual_value)[:200]}")
        
        # Data type validation
        if data_type == "string":
            # Validate that the value is a string or can be converted to string
            if actual_value is None:
                raise ValueError(
                    f"ConditionNode received None value. "
                    f"Data type 'String' requires a valid string input."
                )
            
            if isinstance(actual_value, (list, dict)):
                raise ValueError(
                    f"ConditionNode received {type(actual_value).__name__} type but 'String' data type is selected. "
                    f"Please ensure the input node returns a string value, not {type(actual_value).__name__}. "
                    f"Received: {str(actual_value)[:100]}..."
                )
            
            # Convert to string if it's a simple type
            if not isinstance(actual_value, str):
                logger.warning(f"Converting {type(actual_value).__name__} to string for comparison")
                actual_value = str(actual_value)

        logger.info(f"Evaluating value: '{actual_value[:100] if len(str(actual_value)) > 100 else actual_value}'")
        logger.info(f"Comparing with: '{value2}'")

        # Evaluate the condition
        condition_result = self._evaluate_condition(
            actual_value, 
            operation, 
            value2, 
            case_sensitive
        )

        logger.info(f"Condition result: {condition_result}")

        # Return results with routing information
        # For conditional routing, we set the result in a special way
        # that the graph builder can use to determine the path
        return {
            "condition_result": condition_result,
            "evaluated_value": actual_value,
            "operation": operation,
            "comparison_value": value2,
            # Route output based on condition
            "true_output": actual_value if condition_result else None,
            "false_output": actual_value if not condition_result else None,
            # Add output key for default routing
            "output": actual_value,
            # Control flow indicator
            "_route": "true_output" if condition_result else "false_output"
        }
