import os
import json
import logging
from typing import Dict, Any, List
from app.core.node_registry import node_registry
from app.services.ai_builder.state import AIBuilderState
from app.services.ai_builder.utils import extract_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert AI assistant integrating with KAI-Flow, a visual workflow builder.
Your task is to analyze the user's request and design a workflow by selecting the appropriate nodes and connecting them correctly.

AVAILABLE NODES & TOPOLOGY RULES:
{node_catalog}

RULES:
1. ONLY use nodes from the AVAILABLE NODES list.
2. Check `inputs` and `outputs` to match connection types. A node can connect if its output type matches the target's input type.
3. ALWAYS obey any `ai Rule` specified for individual nodes in the catalog.
4. Use EXACTLY the handle names (`name`) provided when connecting nodes.
5. Return ONLY valid JSON.
6. For `StartNode` and `EndNode`, ALWAYS set their `data.name` to exactly "Start" and "End".
7. DATA PASSING & NAMING (CRITICAL): For all other nodes, ALWAYS set `data.name` to a GENERIC snake_case version of its type (e.g. `agent`, `agent_1`, `webhook_trigger`). NEVER invent domain-specific descriptive names like `researcher_agent`. If the user asks for a persona or rules, put those instructions ENTIRELY into the `system_prompt` field.
8. TEMPLATE VARIABLES MATCHING (CRITICAL): When passing data using `${{{{name}}}}` templates (like in RespondToWebhook's response_body), the name inside the template MUST EXACTLY MATCH the `data.name` of the upstream node. If the upstream node has `"data": {{"name": "code_node"}}`, you MUST use `${{{{code_node}}}}`, NOT `${{{{code_node_1}}}}` or anything else. NEVER use `${{{{Start}}}}` or `${{{{start_node}}}}`. When an Agent node needs to reference the user's chat message in the `user_prompt` field, you MUST use exactly `${{{{input}}}}`.
9. STRICT 1-TO-1 CONNECTION RULE (CRITICAL): ALL node connections MUST be strictly 1-to-1.
   - An input handle can receive EXACTLY ONE edge.
   - An output handle can send EXACTLY ONE edge.
   - You CANNOT connect multiple output handles to the same target input handle. If multiple branches need to trigger the same action, you MUST DUPLICATE the target node (e.g. `RespondToWebhook_1`, `RespondToWebhook_2`).
10. PYTHON EXECUTIONS (CodeNode): Write standard multi-line Python code. Do NOT double-escape newlines. Let standard JSON serialization handle line breaks natively.
11. ARCHITECTURE DECISION (CRITICAL): Choose the correct pattern based on the user's intent:
    - "search the internet / find info online / research a topic" -> Use Agent + TavilySearch (tool) + OpenAIChat (llm). Do NOT build a RAG pipeline for this.
    - "load my documents / process my files / build a knowledge base" -> Use DocumentLoader/WebScraper -> ChunkSplitter -> VectorStoreOrchestrator (RAG pipeline).
    - "query my existing knowledge base / search my documents" -> Use RetrieverProvider + Agent.
    - Provider nodes (OpenAIChat, OpenAIEmbeddingsProvider, TavilySearch, CohereRerankerProvider) are SIDE inputs; they connect BOTTOM->TOP to the main chain, NEVER part of the LEFT->RIGHT main processing flow.
12. CONDITION & AGENT OVERUSE (CRITICAL):
    - Do NOT use an Agent node for simple text matching or keyword routing. Connect the data source DIRECTLY to a ConditionNode.
    - If you need to check MULTIPLE keywords (OR logic), do NOT chain multiple ConditionNodes. Use ONE ConditionNode with operation='regex' and value2='word1|word2'.

TOPOLOGY PATTERNS (CRITICAL - How to wire nodes together):
{topology_patterns}

EXAMPLES:
{examples}
"""

TOPOLOGY_PATTERNS = """
1. AGENT TOPOLOGY & MULTI-AGENT SYSTEMS:
   - Agents (Agent) are central processors requiring dependency modules to function.
   - You MUST connect an LLM node (e.g., OpenAIChat output: 'llm') into the Agent's 'llm' input handle.
   - You MUST connect a Memory node (e.g., BufferMemory output: 'memory') into the Agent's 'memory' input handle.
   - MULTI-AGENT CHAINING: Connect the 'output' of one Agent to the 'input' of another Agent to create sequential specialized task agents.
   - SHARED RESOURCES: Due to the 1-to-1 rule, a single LLM/Memory node CANNOT serve multiple Agents. Create SEPARATE LLM and Memory nodes for EACH Agent.

2. RAG & ADVANCED RETRIEVERS (Tool-based Retrieval):
   - Ingestion Pipeline: WebScraper (output: 'documents') -> ChunkSplitter (input: 'documents', output: 'chunks') -> VectorStoreOrchestrator (input: 'documents').
   - Embedding: An OpenAIEmbeddingsProvider node MUST connect its 'embedder' output into VectorStoreOrchestrator's 'embedder' input handle.
   - AGENT-DRIVEN RAG (Retriever Tools): To give an Agent access to vector search, use a RetrieverProvider. Connect its 'retriever_tool' output into the Agent's 'tools' input. Connect OpenAIEmbeddingsProvider's 'embedder' into RetrieverProvider's 'embedder' input.
   - You can also connect a CohereRerankerProvider output 'reranker' to the RetrieverProvider's 'reranker' input to improve results.

3. LOGIC, WEBHOOKS, & DATA PROCESSING:
   - API/Event workflows start with WebhookTrigger instead of StartNode.
   - WebhookTrigger outputs 'webhook_data'. This can be formatted via a StringInputNode or CodeNode before going into an Agent's 'input'.
   - CodeNode takes 'input' (from Agents/Triggers) and outputs 'output'. Used heavily to validate or format data.
   - CONDITIONAL ROUTING: A ConditionNode takes 'input' and routes to either 'true_output' or 'false_output' handles based on logic.
   - Webhook flows ALWAYS end with a RespondToWebhook node (input: 'input'), NEVER an EndNode. Return early here to respond to the caller.

4. DATA STREAMING (Kafka):
   - Kafka pipelines begin with KafkaConsumer (output: 'kafka_data').
   - They usually process the data (via CodeNode or Agent) and then push the result into a KafkaProducer (input: 'input').
   - KafkaProducer outputs 'output' which must always connect into an EndNode (input: 'target').

5. VARIABLES, DATA PASSING, AND SYSTEM PROMPTS (CRITICAL):
   - You MUST use ONLY default, generic snake_case names for a node's `data.name` property, such as "agent", "agent_1", "webhook_trigger", "respond_to_webhook", etc. NEVER invent descriptive, domain-specific names.
   - If the user asks for the Agent to have a "persona", "behavior", "name", or "rules", put those instructions ENTIRELY into the `system_prompt` field. DO NOT alter the `data.name`.
   - IMPORTANT DATA ROUTING: To pass data implicitly between connected nodes, the downstream node MUST use the upstream node's EXACT `data.name` inside a ${{name}} template.
   - CRITICAL STEP: DO NOT use the user's descriptive names for ${{}} interpolations (e.g., if the user asked for an "arastirmaci_ajan", DO NOT use ${{arastirmaci_ajan}}). Look at the generic `data.name` you assigned to the upstream node (e.g., "agent_1") and copy that exactly into ${{}} (e.g., ${{agent_1}}).
   - Examples of dynamic data passing:
     * An Agent reading from a Webhook where the webhook's data.name="webhook_trigger": The agent MUST have "user_prompt_template": "${{webhook_trigger}}".
     * A RespondToWebhook reading from an Agent where the agent's data.name="agent": The webhook MUST have "response_body": "${{agent}}".
     * A CodeNode reading from an Agent where the agent's data.name="agent_1": The code MUST have "code": "print('${{{{agent_1}}}}')". Do not use variable assignment.
   - NEVER assume edge connections magically pass data strings. YOU MUST explicitly write the ${{data_name}} template.

6. AGENT TOOLS & CAPABILITIES:
   - If the user asks for an agent that can "browse the web" or "search the internet", you MUST include a TavilySearch and connect its 'search_tool' output to the Agent's 'tools' input handle.
   - For an agent or workflow to fetch data from APIs, use HttpRequest and connect the needed output ('response', 'content', or 'documents') downstream.
   - If multiple tools are required, each tool MUST have its own dedicated connection to the Agent's 'tools' input (1-to-1 rule applies).

7. CONDITIONAL ROUTING (ConditionNode):
   - When the user asks for branching logic ("if X then Y else Z"), you MUST use a ConditionNode.
   - Set the `data` properties to define the check. Example: "data": {"name": "condition", "operation": "contains", "value2": "spam"}.
   - Connect the ConditionNode's 'true_output' handle to the node that executes when the condition is met.
   - Connect the 'false_output' handle to the fallback node.

8. DYNAMIC CODE EXECUTION (CodeNode):
   - If the user explicitly asks to run custom code, perform math, calculate a sum, or manipulate strings, you MUST use a CodeNode.
   - You MUST write the actual Python code and place it inside the `data.code` property of the CodeNode.
   - CRITICAL: The CodeNode executes as a script, NOT a function. You CANNOT use the `return` statement (it will cause a SyntaxError). You MUST use `print(...)` to output your final result!
   - CRITICAL FORMATTING: When writing the "code" string in JSON, use standard `\\n` for line breaks. Do NOT over-escape (never use `\\\\n`). The CodeNode editor needs actual line breaks to render properly.
"""

FORMAT_INSTRUCTIONS = """
Respond with ONLY JSON. No markdown formatting.
Format:
{
  "nodes": [
    {
      "id": "<generate_unique_id>",
      "type": "<NodeTypeName_from_catalog>",
      "data": { "name": "<snake_case_version_of_type>" }
    }
  ],
  "edges": [
    {
      "source": "<source_node_id>",
      "target": "<target_node_id>",
      "sourceHandle": "<output_handle_name>",
      "targetHandle": "<input_handle_name>"
    }
  ]
}
"""


from openai import AsyncOpenAI

class BuilderProcessor:
    def __init__(self):
        pass

    def _build_catalog(self, selected_nodes: List[str] = None) -> str:
        from app.services.ai_builder.ai_rules_registry import AI_RULES_REGISTRY
        all_nodes = node_registry.get_all_nodes()
        nodes = all_nodes

        # If selection provided, filter nodes. If empty, fallback to all nodes.
        if selected_nodes and len(selected_nodes) > 0:
            nodes = [n for n in all_nodes if n.name in selected_nodes] or all_nodes
            # Always ensure basic control nodes are available just in case the selector missed them
            essential_nodes = ["StartNode", "EndNode", "ConditionNode"]
            for ess in essential_nodes:
                if ess not in [n.name for n in nodes]:
                    ess_node = next((n for n in all_nodes if n.name == ess), None)
                    if ess_node:
                        nodes.append(ess_node)

        catalog = []
        for n in nodes:
            inputs = [f"{h.name} (type: {h.type})" for h in (n.inputs or []) if getattr(h, 'is_connection', False)]
            outputs = [f"{h.name} (type: {h.type})" for h in (n.outputs or []) if getattr(h, 'is_connection', False)]
            properties = [f"{p.name} (type: {p.type.value if hasattr(p.type, 'value') else getattr(p, 'type', type(p).__name__)})" for p in (n.properties or [])]
            ai_rules = AI_RULES_REGISTRY.get(n.name, '')
            node_str = f"- {n.name}: {n.description}\n  Inputs: {inputs}\n  Outputs: {outputs}\n  Properties (editable in data): {properties}"
            if ai_rules:
                node_str += f"\n  -> AI Rule: {ai_rules}"
            catalog.append(node_str)
        return "\n\n".join(catalog)

    def _build_examples(self) -> str:
        """Load ALL templates directly into the prompt context (Context Stuffing)."""
        templates_dir = os.path.join(os.path.dirname(__file__), "..", "ai_builder_templates")
        examples = []
        if os.path.exists(templates_dir):
            for filename in sorted(os.listdir(templates_dir)):
                if filename.endswith(".json"):
                    try:
                        filepath = os.path.join(templates_dir, filename)
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        examples.append(
                            f"User: {data.get('description', '')}\n"
                            f"JSON:\n{json.dumps(data.get('workflow', {}), indent=2)}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to load template {filename}: {e}")

        if not examples:
            return "No examples available. Use catalog."
        return "\n\n".join(examples)

    def _calculate_positions(self, nodes: List[Dict[str, Any]]):
        # Only assign positions to nodes that don't already have one
        for i, node in enumerate(nodes):
            if "position" not in node:
                node["position"] = {"x": 250 + (i * 300), "y": 250}

    async def process(self, state: AIBuilderState) -> Dict[str, Any]:
        api_key = state.get("api_key")
        model_name = state.get("model_name", "gpt-4o")
        base_url = state.get("base_url")

        if not api_key:
            raise ValueError("No API key provided. Cannot generate workflow.")

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        client = AsyncOpenAI(**kwargs)

        messages = list(state.get("messages", []))
        is_edit = state.get("mode", "build") == "edit"

        if not messages:
            catalog_str = self._build_catalog(selected_nodes=state.get("selected_nodes", []))
            prompt = SYSTEM_PROMPT.format(
                node_catalog=catalog_str,
                topology_patterns=TOPOLOGY_PATTERNS,
                examples=self._build_examples()
            ) + "\n\n" + FORMAT_INSTRUCTIONS

            user_content = state["question"]
            if is_edit and state.get("original_workflow"):
                original_workflow = state.get("original_workflow", {})
                node_summary = "\n".join([f"- {n['type']} (id: {n['id']})" for n in original_workflow.get("nodes", [])])
                user_content = (
                    f"EXISTING NODES IN THIS WORKFLOW:\n{node_summary}\n\n"
                    f"FULL WORKFLOW JSON:\n"
                    f"{json.dumps(original_workflow, ensure_ascii=False)}\n\n"
                    f"USER'S EDIT REQUEST: {state.get('question', '')}\n\n"
                    f"EDIT MODE RULES (CRITICAL):\n"
                    f"1. FIRST, check if the user's request is actually about editing/modifying this workflow. If the request is completely unrelated to workflow building (e.g. casual conversation, random questions, jokes), you MUST respond with ONLY: {{\"invalid_request\": true, \"message\": \"Your request does not appear to be a workflow edit. Please describe what you want to change in the workflow.\"}}\n"
                    f"2. If the request IS a valid edit, identify WHICH node(s) the user is referring to from the node list above.\n"
                    f"3. You MAY add, delete, or change the type of a node if the user explicitly asks for a structural change OR if their intent requires a different topology (e.g., if they say 'I want to trigger this manually', replace WebhookTrigger with StartNode).\n"
                    f"4. IF you make any structural changes (adding, deleting, or changing node types), you MUST add a field `\"structural_change_made\": true` to the root of your JSON response. Otherwise, omit it.\n"
                    f"5. If the request is just an edit, ONLY modify the `data` block of that specific node. You may safely add missing properties listed in the catalog.\n"
                    f"6. Copy every other untouched node and edge EXACTLY as-is, byte-for-byte. Keep all code blocks, Turkish characters ('ı', 'ş', 'ğ', 'ö', 'ü', 'ç'), and formatting intact.\n"
                    f"7. Return the COMPLETE updated workflow JSON with all nodes and edges intact."
                )

            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content}
            ]
        else:
            errors = state.get("validation_errors", [])
            error_message = "The generated JSON had the following validation errors:\n"
            for err in errors:
                error_message += f"- {err}\n"
            error_message += "\nPlease fix these errors and regenerate the JSON exactly according to the format instructions."
            messages.append({"role": "user", "content": error_message})

        iteration = state.get("iteration", 0)
        logger.info(f"\n" + "="*50)
        logger.info(f"🚀 AI BUILDER: ITERATION {iteration + 1} - {'EDITING' if is_edit else 'BUILDING'} WORKFLOW WITH {model_name}")
        logger.info(f"❓ Request: {state.get('question', '')[:100]}...")
        logger.info(f"="*50 + "\n")

        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.2 if is_edit else 0.7,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        messages.append({"role": "assistant", "content": content})

        workflow_dict = {}
        validation_errors = []
        import re
        try:
            result = extract_json(content)

            # Check if LLM flagged this as an invalid/irrelevant request
            if result.get("invalid_request"):
                reject_msg = result.get("message", "Your request does not appear to be a workflow edit.")
                logger.info(f"🚫 [AI BUILDER] Invalid request rejected: {reject_msg}")
                return {
                    "messages": messages,
                    "current_workflow": state.get("original_workflow", {}) if is_edit else {},
                    "validation_errors": [],
                    "iteration": iteration + 1,
                    "invalid_request": True,
                    "invalid_request_message": reject_msg
                }

            nodes = result.get("nodes", [])

            # Post-processing to robustly filter LLM hallucinations
            for n in nodes:
                data = n.get("data", {})

                # 1. Fix double-escaped newlines in CodeNodes & Strip quotes
                if n.get("type", "").endswith("CodeNode") and "code" in data:
                    if isinstance(data["code"], str):
                        data["code"] = data["code"].replace("\\n", "\n")
                        # Strip explicitly any single/double quotes around template variables
                        data["code"] = re.sub(r'''["'](\${{.*?}})["']''', r'\1', data["code"])

                # 2. Force ${{input}} template instead of ${{Start}} in Agents
                if n.get("type", "").endswith("Agent"):
                    for key in ["user_prompt_template", "system_prompt"]:
                        if key in data and isinstance(data[key], str):
                            data[key] = data[key].replace("${{Start}}", "${{input}}").replace("${{start_node}}", "${{input}}")

            self._calculate_positions(nodes)
            workflow_dict = {"nodes": nodes, "edges": result.get("edges", [])}
        except Exception as e:
            validation_errors = [f"Failed to parse LLM response: {str(e)}"]

        return {
            "messages": messages,
            "current_workflow": workflow_dict,
            "validation_errors": validation_errors,
            "iteration": iteration + 1
        }
