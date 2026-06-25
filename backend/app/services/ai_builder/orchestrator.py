import json
import logging
import re
from typing import Dict, Any, Optional

from openai import AsyncOpenAI

from .types import WorkflowSnapshot, WorkflowNode, WorkflowEdge
from .schema_compiler import (
    compile_node_catalog,
    compile_connection_rules,
    compile_parameterization_schema
)
from .diff_engine import compute_changeset
from .validator import validate_structure, validate_topology
from .hydrator import hydrate_with_defaults
from .layout_engine import calculate_auto_layout
from .prompt_templates.skeleton_system import build_skeleton_prompt
from .prompt_templates.parameterization_system import build_parameterization_prompt

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    raise ValueError("No valid JSON object found in response.")


class AIBuilderOrchestrator:

    async def generate_workflow(
        self,
        question: str,
        api_key: str,
        model_name: str = "gpt-4o",
        base_url: str = None,
        mode: str = "build",
        existing_workflow: Dict[str, Any] = None,
        verify_ssl: bool = True,
        extra_body_params: Optional[str] = None,
        chat_history: Optional[list[Dict[str, str]]] = None
    ) -> Dict[str, Any]:

        logger.info(f"AIBuilderOrchestrator starting in '{mode}' mode using model: {model_name}")

        is_edit = (mode == "edit") and bool(existing_workflow)
        client = self._create_client(api_key, base_url, verify_ssl)
        extra_body = self._parse_extra_body(extra_body_params)

        # ─── Phase 1: Skeleton Generation ───
        logger.info("AI Builder Orchestrator: Generating workflow skeleton (Phase 1)...")
        skeleton = await self._generate_skeleton(
            client, model_name, question, is_edit, existing_workflow, extra_body, chat_history
        )
        if skeleton.get("invalid_request"):
            return skeleton

        # ─── Phase 2: Registry Hydration ───
        logger.info("AI Builder Orchestrator: Hydrating skeleton with registry defaults (Phase 2)...")
        hydrated = hydrate_with_defaults(skeleton)

        # ─── Phase 3 & 4: Parameterization + Validation Loop ───
        logger.info("AI Builder Orchestrator: Parameterizing and validating workflow (Phase 3 & 4)...")
        result = await self._parameterize_and_validate(
            client, model_name, hydrated, question, extra_body, existing_workflow
        )

        # ─── Phase 5: Layout ───
        logger.info("AI Builder Orchestrator: Calculating auto layout (Phase 5)...")
        result = calculate_auto_layout(result, existing_workflow)

        # ─── Phase 6: Post-processing ───
        result = self._post_process(result)

        # ─── Phase 7: Diff (edit mode) ───
        if is_edit and existing_workflow:
            try:
                base = WorkflowSnapshot.from_dict(existing_workflow)
                target = WorkflowSnapshot.from_dict(result)
                changeset = compute_changeset(base, target)
                logger.info(f"Edit changeset summary: {changeset.summary()}")
            except Exception as e:
                logger.error(f"Failed to compute changeset: {e}", exc_info=True)

        return result

    async def _generate_skeleton(
        self,
        client: AsyncOpenAI,
        model_name: str,
        question: str,
        is_edit: bool,
        existing_workflow: Optional[Dict[str, Any]],
        extra_body: Dict[str, Any],
        chat_history: Optional[list[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        node_catalog = compile_node_catalog()
        connection_rules = compile_connection_rules()

        system_prompt = build_skeleton_prompt(
            is_edit=is_edit,
            node_catalog=node_catalog,
            connection_rules=connection_rules
        )

        if is_edit and existing_workflow:
            # Minimal edit context to save tokens and avoid LLM confusion
            compact_nodes = []
            for node in existing_workflow.get("nodes", []):
                compact_nodes.append({
                    "id": node.get("id"),
                    "type": node.get("type"),
                    "data": {"name": node.get("data", {}).get("name", node.get("id"))}
                })
            compact_edges = []
            for edge in existing_workflow.get("edges", []):
                compact_edges.append({
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "sourceHandle": edge.get("sourceHandle"),
                    "targetHandle": edge.get("targetHandle")
                })
            edit_context = {
                "nodes": compact_nodes,
                "edges": compact_edges
            }

            user_content = (
                f"The user wants to EDIT an existing workflow.\n"
                f"CURRENT WORKFLOW SKELETON:\n"
                f"{json.dumps(edit_context, ensure_ascii=False, indent=2)}\n\n"
                f"USER EDIT REQUEST: {question}\n\n"
                f"EDIT INSTRUCTIONS:\n"
                f"1. Check if the request is actually a workflow edit. If completely irrelevant, respond with:\n"
                f"   {{\"invalid_request\": true, \"message\": \"Your request does not appear to be a workflow edit. Please describe what you want to change.\"}}\n"
                f"2. Modify the nodes skeleton list and/or edges connections accordingly. Keep untouched nodes and edges exactly as-is.\n"
                f"3. Return the COMPLETE updated skeleton JSON."
            )
        else:
            user_content = f"Generate a new workflow skeleton for: {question}"

        messages = [{"role": "system", "content": system_prompt}]
        if chat_history:
            for msg in chat_history:
                role = msg.get("role")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_content})

        create_kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2 if is_edit else 0.7,
            "response_format": {"type": "json_object"}
        }
        if extra_body:
            create_kwargs["extra_body"] = extra_body

        response = await client.chat.completions.create(**create_kwargs)
        content = response.choices[0].message.content
        return _extract_json(content)

    async def _parameterize_and_validate(
        self,
        client: AsyncOpenAI,
        model_name: str,
        hydrated: Dict[str, Any],
        question: str,
        extra_body: Dict[str, Any],
        existing_workflow: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        selected_types = list(set(n.get("type") for n in hydrated.get("nodes", [])))
        prop_schema = compile_parameterization_schema(selected_types)
        system_prompt = build_parameterization_prompt(prop_schema)

        user_content = (
            f"Here is the workflow skeleton we designed:\n"
            f"{json.dumps(hydrated, ensure_ascii=False, indent=2)}\n\n"
            f"User's request: {question}\n\n"
            f"Populate the node property values under the 'data' block for each node based on the request."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        result = {"nodes": [], "edges": []}
        iteration = 0

        while iteration < 3:
            logger.info(f"AI Builder: Parameterizing properties (Phase 3) - Iteration {iteration + 1}...")

            try:
                create_kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
                if extra_body:
                    create_kwargs["extra_body"] = extra_body

                response = await client.chat.completions.create(**create_kwargs)
                content = response.choices[0].message.content
                messages.append({"role": "assistant", "content": content})

                result = _extract_json(content)

                # Structure and Topology Validation
                structural_issues = validate_structure(result)
                topology_issues = validate_topology(result)
                all_issues = structural_issues + topology_issues

                if not all_issues:
                    logger.info("AI Builder: Workflow compiled, parameterized, and validated successfully!")
                    return result

                validation_errors = [str(issue) for issue in all_issues]
                logger.warning(f"AI Builder parameterization validation failed: {validation_errors}")

            except Exception as e:
                validation_errors = [f"Failed to process parameterizer response: {str(e)}"]
                logger.error(f"Error during parameterizer iteration: {e}", exc_info=True)

            feedback_text = (
                "The parameterized workflow JSON has the following validation errors. "
                "Please fix them and return the COMPLETE updated workflow JSON with corrected properties:\n"
                + "\n".join([f"- {err}" for err in validation_errors])
            )
            messages.append({"role": "user", "content": feedback_text})
            iteration += 1

        logger.warning("AI Builder: Max retry limit reached, returning latest output.")
        return result

    def _create_client(self, api_key: str, base_url: Optional[str], verify_ssl: bool) -> AsyncOpenAI:
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        if not verify_ssl:
            import httpx
            logger.info("AI Builder SSL verification disabled.")
            kwargs["http_client"] = httpx.AsyncClient(verify=False)

        return AsyncOpenAI(**kwargs)

    def _parse_extra_body(self, extra_body_params: Optional[str]) -> Dict[str, Any]:
        if not extra_body_params:
            return {}
        try:
            return json.loads(extra_body_params)
        except Exception as e:
            logger.error(f"Failed to parse extra_body_params JSON in AI Builder: {e}")
            return {}

    def _post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        for node in result.get("nodes", []):
            data = node.get("data", {})
            if node.get("type", "").endswith("CodeNode") and "code" in data:
                if isinstance(data["code"], str):
                    data["code"] = data["code"].replace("\\n", "\n")
                    data["code"] = re.sub(r'''["'](\${{.*?}})["']''', r'\1', data["code"])

            if node.get("type", "").endswith("Agent"):
                for key in ["user_prompt_template", "system_prompt"]:
                    if key in data and isinstance(data[key], str):
                        data[key] = data[key].replace("${{Start}}", "${{input}}").replace("${{start_node}}", "${{input}}")
        return result
