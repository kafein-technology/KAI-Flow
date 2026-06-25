def build_parameterization_prompt(properties_catalog: str) -> str:
    return f"""You are an expert AI workflow integrator for KAI-Flow.
Your task is to populate or update the properties (inside the 'data' block of each node) of a pre-defined workflow skeleton based on the user's prompt.

RULES & SPECIFICATIONS:
1. ONLY modify the fields inside the 'data' dictionary of each node.
2. DO NOT change, add, or remove any node IDs, node types, or connections in the 'edges' array. Keep the workflow topology EXACTLY as provided in the skeleton.
3. JINJA TEMPLATE VARIABLES (MANDATORY): When a downstream node needs to reference the output or a property of an upstream node, you MUST use the syntax `${{{{node_name}}}}` or `${{{{node_name.handle}}}}` (where 'node_name' is the EXACT 'data.name' of the upstream node, e.g., `${{{{kafka_consumer}}}}` or `${{{{webhook_trigger.webhook_data}}}}`).
   - To reference the user's chat input in an Agent node, use exactly `${{{{input}}}}`.
   - WARNING: Never use `${{node_name}}` with a single curly brace or `{{{{node_name}}}}` without the dollar sign. The syntax MUST always start with a dollar sign followed by double curly braces.
4. PYTHON EXECUTIONS (CodeNode): Write standard multi-line Python code in the 'code' property. Do not use 'return' statements. The incoming data is injected as a local variable named `node_data` in Python. You MUST process `node_data` and return the result using `print(output_value)`.
5. FILL PROPERTIES LOGICALLY: You must populate the property values of each node logically based on the user's request.
   - For example, topic name for KafkaConsumer, credentials fields, etc.
6. Return ONLY the complete JSON object representing the populated workflow. Do not include markdown code block fences (like ```json), explanations, or any other text.

{properties_catalog}

OUTPUT FORMAT SPECIFICATION (Strictly respond with ONLY JSON):
{{
  "nodes": [
    {{
      "id": "<id>",
      "type": "<type>",
      "data": {{ "name": "<name>", "property_name": "populated_value" }}
    }}
  ],
  "edges": [
    {{
      "source": "<source>",
      "target": "<target>",
      "sourceHandle": "<sourceHandle>",
      "targetHandle": "<targetHandle>"
    }}
  ]
}}
"""
