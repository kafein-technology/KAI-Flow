import json
import logging
import os
from typing import Dict, Any, List, Optional

from langchain_core.runnables import Runnable
from ..base import (
    ProcessorNode, NodeInput, NodeOutput, NodeProperty,
    NodePropertyType, NodePosition, NodeType,
)

# Reuse attack resolution and Jinja helper from the existing Red Team node
from .llm_red_team_node import ATTACK_MAP, _resolve_attacks, _is_unresolved_jinja

logger = logging.getLogger(__name__)

# ============================================================================
# AGENTIC VULNERABILITY MAP — types verified against DeepTeam source
# ============================================================================
# Each entry: "UIName" -> (ClassName, [default_types] | None)
# types=None means the class will be instantiated with its own built-in defaults.

AGENTIC_VULNERABILITY_MAP = {
    # Goal Theft
    "GoalTheft":       ("GoalTheft",       ["escalating_probing", "cooperative_dialogue", "social_engineering"]),
    "Goal Theft":      ("GoalTheft",       ["escalating_probing", "cooperative_dialogue", "social_engineering"]),

    # Recursive Hijacking
    "RecursiveHijacking":  ("RecursiveHijacking",  ["self_modifying_goals", "recursive_objective_chaining", "goal_propagation_attacks"]),
    "Recursive Hijacking": ("RecursiveHijacking",  ["self_modifying_goals", "recursive_objective_chaining", "goal_propagation_attacks"]),

    # Excessive Agency
    "ExcessiveAgency":  ("ExcessiveAgency",  ["functionality", "permissions", "autonomy"]),
    "Excessive Agency": ("ExcessiveAgency",  ["functionality", "permissions", "autonomy"]),

    # Robustness
    "Robustness":       ("Robustness",       ["input_overreliance", "hijacking"]),

    # Indirect Instruction
    "IndirectInstruction":  ("IndirectInstruction",  ["rag_injection", "tool_output_injection", "document_embedded_instructions", "cross_context_injection"]),
    "Indirect Instruction": ("IndirectInstruction",  ["rag_injection", "tool_output_injection", "document_embedded_instructions", "cross_context_injection"]),

    # Tool Orchestration Abuse
    "ToolOrchestrationAbuse":   ("ToolOrchestrationAbuse",  ["recursive_tool_calls", "unsafe_tool_composition", "tool_budget_exhaustion", "cross_tool_state_leakage"]),
    "Tool Orchestration Abuse": ("ToolOrchestrationAbuse",  ["recursive_tool_calls", "unsafe_tool_composition", "tool_budget_exhaustion", "cross_tool_state_leakage"]),

    # Agent Identity & Trust Abuse
    "AgentIdentityAbuse":   ("AgentIdentityAbuse",  ["agent_impersonation", "identity_inheritance", "cross_agent_trust_abuse"]),
    "Agent Identity Abuse": ("AgentIdentityAbuse",  ["agent_impersonation", "identity_inheritance", "cross_agent_trust_abuse"]),

    # Insecure Inter-Agent Communication
    "InsecureInterAgentCommunication": ("InsecureInterAgentCommunication", ["message_spoofing", "message_injection", "agent_in_the_middle"]),
    "Inter-Agent Communication":       ("InsecureInterAgentCommunication", ["message_spoofing", "message_injection", "agent_in_the_middle"]),

    # Autonomous Agent Drift
    "AutonomousAgentDrift":   ("AutonomousAgentDrift",  ["goal_drift", "reward_hacking", "agent_collusion", "runaway_autonomy"]),
    "Autonomous Agent Drift": ("AutonomousAgentDrift",  ["goal_drift", "reward_hacking", "agent_collusion", "runaway_autonomy"]),

    # Exploit Tool Agent
    "ExploitToolAgent":   ("ExploitToolAgent",  ["privilege_escalation", "financial_manipulation", "data_destruction"]),
    "Exploit Tool Agent": ("ExploitToolAgent",  ["privilege_escalation", "financial_manipulation", "data_destruction"]),

    # External System Abuse
    "ExternalSystemAbuse":   ("ExternalSystemAbuse",  ["data_exfiltration", "communications_spam", "internal_spoofing"]),
    "External System Abuse": ("ExternalSystemAbuse",  ["data_exfiltration", "communications_spam", "internal_spoofing"]),

    # Cross Context Retrieval
    "CrossContextRetrieval":   ("CrossContextRetrieval",  ["tenant", "user", "role"]),
    "Cross Context Retrieval": ("CrossContextRetrieval",  ["tenant", "user", "role"]),

    # Tool Metadata Poisoning
    "ToolMetadataPoisoning":   ("ToolMetadataPoisoning",  ["schema_manipulation", "description_deception", "permission_misrepresentation", "registry_poisoning"]),
    "Tool Metadata Poisoning": ("ToolMetadataPoisoning",  ["schema_manipulation", "description_deception", "permission_misrepresentation", "registry_poisoning"]),

    # Debug Access
    "DebugAccess":  ("DebugAccess",  ["debug_mode_bypass", "development_endpoint_access", "administrative_interface_exposure"]),
    "Debug Access": ("DebugAccess",  ["debug_mode_bypass", "development_endpoint_access", "administrative_interface_exposure"]),

    # System Reconnaissance
    "SystemReconnaissance":   ("SystemReconnaissance",  ["file_metadata", "database_schema", "retrieval_config"]),
    "System Reconnaissance":  ("SystemReconnaissance",  ["file_metadata", "database_schema", "retrieval_config"]),
}


def _resolve_agentic_vulnerabilities(
    names: List[str],
    type_overrides: Optional[Dict[str, List[str]]] = None,
) -> list:
    """Resolve agentic vulnerability names to DeepTeam class instances.

    Unlike the generic LLMRedTeamNode resolver, this function supports
    the ``types`` parameter for granular sub-type selection.

    Args:
        names: Vulnerability names (from comma-separated UI input).
        type_overrides: Optional ``{VulnName: [selected_types]}`` dict
            for restricting which sub-types to test. When *None* or when
            a vulnerability is not present in the dict, all default
            types are used.

    Returns:
        A list of instantiated DeepTeam vulnerability objects.
    """
    import deepteam.vulnerabilities as m

    result = []
    for name in names:
        key = name.strip()
        entry = AGENTIC_VULNERABILITY_MAP.get(key)
        if not entry:
            logger.warning(f"AgenticRedTeam: Unknown agentic vulnerability '{key}'. Skipping.")
            continue

        cls_name, default_types = entry
        cls = getattr(m, cls_name, None)
        if cls is None:
            logger.warning(f"AgenticRedTeam: Class '{cls_name}' not found in deepteam.vulnerabilities. Skipping.")
            continue

        # Determine which types to use
        selected_types = (type_overrides or {}).get(key, default_types)
        kwargs = {}
        if selected_types is not None:
            kwargs["types"] = selected_types

        result.append(cls(**kwargs))
    return result


# ============================================================================
# AGENTIC RED TEAM NODE
# ============================================================================

class AgenticRedTeamNode(ProcessorNode):
    """Agentic Red Team Scanner — Adversarial security testing for AI agents.

    Focuses exclusively on DeepTeam's agentic vulnerability categories
    (Goal Theft, Recursive Hijacking, Excessive Agency, etc.) with full
    ``types`` sub-parameter support for granular testing.
    """

    def __init__(self):
        super().__init__()
        self._metadata = self._build_metadata()

    # ----------------------------------------------------------------
    # METADATA
    # ----------------------------------------------------------------

    def _build_metadata(self) -> Dict[str, Any]:
        return {
            "name": "AgenticRedTeam",
            "display_name": "Agentic Red Team Scanner",
            "description": (
                "Automated adversarial security testing for AI agents "
                "using DeepTeam agentic vulnerabilities."
            ),
            "category": "Security",
            "node_type": NodeType.PROCESSOR,
            "colors": ["red-500", "rose-600"],
            "icon": {"name": "redteaming_agentic", "path": "icons/redteaming_agentic.svg", "alt": None},
            "inputs": self._build_inputs(),
            "outputs": self._build_outputs(),
            "properties": self._build_properties(),
        }

    def _build_inputs(self) -> List[NodeInput]:
        return [
            NodeInput(
                name="input", displayName="Input", type="string",
                is_connection=True, required=True,
                description="Input from trigger node.",
            ),
            NodeInput(
                name="simulator_llm", displayName="Simulator LLM",
                type="BaseLanguageModel", is_connection=True, required=True,
                direction=NodePosition.BOTTOM,
                description="Generates adversarial attack prompts.",
            ),
            NodeInput(
                name="evaluator_llm", displayName="Evaluator LLM",
                type="BaseLanguageModel", is_connection=True, required=True,
                direction=NodePosition.BOTTOM,
                description="Judges whether attacks succeeded.",
            ),
        ]

    def _build_outputs(self) -> List[NodeOutput]:
        return [
            NodeOutput(
                name="output", displayName="Scan Results", type="string",
                is_connection=True, description="Agentic risk assessment JSON report.",
            ),
        ]

    def _build_properties(self) -> List[NodeProperty]:
        # Build a readable hint listing all available vulnerability names
        vuln_names = sorted({v[0] for v in AGENTIC_VULNERABILITY_MAP.values()})
        vuln_hint = ", ".join(vuln_names)

        return [
            # ── Target ──
            NodeProperty(
                name="target_base_url", displayName="Target Base URL",
                type=NodePropertyType.TEXT, default="",
                hint="OpenAI-compatible base URL. Supports Jinja: ${{ webhook_trigger.target_base_url }}",
                placeholder="https://api.openai.com/v1", required=True,
            ),
            NodeProperty(
                name="target_model_name", displayName="Target Model Name",
                type=NodePropertyType.TEXT, default="",
                hint="Model identifier. Supports Jinja: ${{ webhook_trigger.target_model_name }}",
                placeholder="gpt-4o-mini", required=True,
            ),
            NodeProperty(
                name="target_api_key", displayName="Target API Key",
                type=NodePropertyType.TEXT, default="",
                hint="API key. Supports Jinja: ${{ webhook_trigger.target_api_key }}",
                placeholder="sk-... or ${{ webhook_trigger.target_api_key }}", required=True,
            ),
            # ── Agent Context ──
            NodeProperty(
                name="target_purpose", displayName="Target Agent Purpose",
                type=NodePropertyType.TEXT_AREA,
                default="Autonomous customer-support agent with tool access",
                hint="Describe the agent's purpose. REQUIRED for agentic tests — directly influences attack scenario generation.",
                required=True,
            ),
            NodeProperty(
                name="target_system_prompt", displayName="Target System Prompt",
                type=NodePropertyType.TEXT_AREA, default="",
                hint="System prompt of the target agent.", required=False,
            ),
            # ── Scan Config ──
            NodeProperty(
                name="vulnerabilities", displayName="Agentic Vulnerabilities",
                type=NodePropertyType.TEXT_AREA,
                default="GoalTheft, RecursiveHijacking, ExcessiveAgency, IndirectInstruction, AutonomousAgentDrift",
                hint=f"Comma-separated. Available: {vuln_hint}",
                required=True,
            ),
            NodeProperty(
                name="vulnerability_types", displayName="Vulnerability Type Overrides",
                type=NodePropertyType.TEXT_AREA, default="",
                hint=(
                    'Optional JSON to restrict sub-types per vulnerability. '
                    'E.g: {"GoalTheft": ["escalating_probing"], "ExcessiveAgency": ["permissions"]}. '
                    'Leave empty to use all default types.'
                ),
                required=False,
            ),
            NodeProperty(
                name="attacks", displayName="Attack Vectors",
                type=NodePropertyType.TEXT_AREA,
                default="Prompt Injection, Jailbreaking, Roleplay",
                hint="Comma-separated. Supports Jinja: ${{ webhook_trigger.attacks }}. E.g: Prompt Injection, Jailbreaking, ROT13, Roleplay",
                required=True,
            ),
            NodeProperty(
                name="attacks_per_vuln_type", displayName="Attacks Per Vulnerability",
                type=NodePropertyType.TEXT, default="3",
                hint="Number of attack attempts per vulnerability type. Supports Jinja: ${{ webhook_trigger.attacks_per_vuln_type }}",
                placeholder="3", required=True,
            ),
            # ── Advanced ──
            NodeProperty(
                name="max_concurrent", displayName="Max Concurrent",
                type=NodePropertyType.NUMBER, default=1, min=1, max=20,
                hint="Maximum concurrent attack tasks.",
                tabName="advanced", required=False,
            ),
            NodeProperty(
                name="enable_owasp_asi", displayName="Use OWASP ASI 2026",
                type=NodePropertyType.CHECKBOX, default=False,
                hint="Use OWASP Agentic Security Initiative 2026 framework instead of custom selection.",
                tabName="advanced", required=False,
            ),
            NodeProperty(
                name="owasp_asi_categories", displayName="OWASP ASI Categories",
                type=NodePropertyType.TEXT_AREA, default="",
                hint="Comma-separated ASI IDs. E.g: ASI_01, ASI_05. Leave empty for all 10.",
                tabName="advanced",
                displayOptions={"show": {"enable_owasp_asi": True}},
                required=False,
            ),
            NodeProperty(
                name="verify_ssl", displayName="SSL Certificate Verification",
                type=NodePropertyType.CHECKBOX, default=True,
                hint="Enable SSL certificate verification. Disable this only when connecting to servers with self-signed certificates.",
                tabName="advanced", required=False,
            ),
            NodeProperty(
                name="strip_reasoning", displayName="Strip Reasoning/Thinking Tags",
                type=NodePropertyType.CHECKBOX, default=False,
                hint="Automatically remove <think>...</think> or <thought>...</thought> tags and their contents from the target model's output.",
                tabName="advanced", required=False,
            ),
            NodeProperty(
                name="extra_body_params", displayName="Extra Body Parameters (JSON)",
                type=NodePropertyType.TEXT_AREA, default="",
                placeholder='{"thinking_mode": false}',
                hint="Additional parameters to inject directly into the request body of target model (e.g. for Groq thinking configuration).",
                tabName="advanced", required=False,
            ),
        ]

    # ----------------------------------------------------------------
    # EXECUTION
    # ----------------------------------------------------------------

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Runnable]) -> Dict[str, Any]:
        # Suppress noisy LangSmith 403 warnings when no API key is configured
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGCHAIN_TRACING"] = "false"

        from openai import OpenAI
        from deepteam import red_team
        from deepteam.test_case import RTTurn
        from deepeval.models import DeepEvalBaseLLM

        # ── Property fallback from self.user_data ──
        for key in [
            "target_base_url", "target_model_name", "target_api_key",
            "target_purpose", "target_system_prompt", "vulnerabilities",
            "vulnerability_types", "attacks", "attacks_per_vuln_type",
            "max_concurrent", "enable_owasp_asi", "owasp_asi_categories", "verify_ssl",
            "strip_reasoning", "extra_body_params",
        ]:
            if key not in inputs and isinstance(self.user_data, dict) and key in self.user_data:
                inputs[key] = self.user_data[key]

        # SSL verification
        verify_ssl_val = inputs.get("verify_ssl", True)
        if isinstance(verify_ssl_val, str):
            verify_ssl = verify_ssl_val.lower() not in ("false", "0", "no")
        else:
            verify_ssl = bool(verify_ssl_val)

        # Strip Reasoning/Thinking Tags
        strip_reasoning_val = inputs.get("strip_reasoning")
        if strip_reasoning_val is None:
            strip_reasoning_val = False
        if isinstance(strip_reasoning_val, str):
            strip_reasoning = strip_reasoning_val.lower() in ("true", "1", "yes", "on")
        else:
            strip_reasoning = bool(strip_reasoning_val)

        # Extra Body Parameters (JSON)
        extra_body_json = inputs.get("extra_body_params") or ""
        extra_body_data = {}
        if extra_body_json:
            try:
                extra_body_data = json.loads(extra_body_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse extra_body_params JSON: {e}")

        # ── Validate & extract target params ──
        target_base_url      = inputs.get("target_base_url", "").strip()
        target_model_name    = inputs.get("target_model_name", "").strip()
        target_api_key       = inputs.get("target_api_key", "").strip() or "sk-no-key"
        target_system_prompt = inputs.get("target_system_prompt", "").strip()
        target_purpose       = inputs.get("target_purpose", "").strip()
        
        # Convert attacks_per_vuln_type from string to int (supports Jinja)
        attacks_per_vuln_raw = inputs.get("attacks_per_vuln_type", "3")
        try:
            attacks_per_vuln = int(str(attacks_per_vuln_raw).strip())
            if attacks_per_vuln < 1 or attacks_per_vuln > 50:
                logger.warning(f"attacks_per_vuln_type out of range ({attacks_per_vuln}). Clamping to 1-50.")
                attacks_per_vuln = max(1, min(50, attacks_per_vuln))
        except (ValueError, TypeError):
            logger.warning(f"Invalid attacks_per_vuln_type: {attacks_per_vuln_raw}. Using default: 3")
            attacks_per_vuln = 3

        if not target_base_url or not target_model_name:
            raise ValueError(
                f"target_base_url and target_model_name are required. "
                f"Got: base_url='{target_base_url}', model='{target_model_name}'"
            )
        if not target_purpose:
            raise ValueError(
                "target_purpose is required for agentic red teaming. "
                "Describe what the target agent does (e.g. 'Customer support agent with database access')."
            )

        logger.info(f"AgenticRedTeam: target={target_model_name} @ {target_base_url}")

        # ── Build raw OpenAI client for target ──
        import httpx
        client_kwargs = {
            "base_url": target_base_url,
            "api_key": target_api_key,
        }
        if not verify_ssl:
            logger.warning("SSL certificate verification is DISABLED for the target client. Use only for trusted internal endpoints.")
            client_kwargs["http_client"] = httpx.Client(verify=False)

        target_client = OpenAI(**client_kwargs)

        # ── model_callback — async function (official docs pattern) ──
        async def model_callback(input: str, turns=None) -> RTTurn:
            messages = []

            if target_system_prompt:
                messages.append({"role": "system", "content": target_system_prompt})

            # Replay multi-turn history for jailbreaking attacks
            if turns:
                for turn in turns:
                    role    = getattr(turn, "role", "user")
                    content = getattr(turn, "content", None) or getattr(turn, "data", str(turn))
                    messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": input})

            try:
                create_kwargs = {
                    "model": target_model_name,
                    "messages": messages,
                    "temperature": 0.0,
                }
                if extra_body_data:
                    create_kwargs["extra_body"] = extra_body_data

                resp = target_client.chat.completions.create(**create_kwargs)
                content = resp.choices[0].message.content or "[ERROR] No content returned."
                
                # Apply reasoning strip if enabled
                if strip_reasoning and isinstance(content, str):
                    import re
                    content = re.sub(r"<think>[\s\S]*?</think>", "", content)
                    content = re.sub(r"<thought>[\s\S]*?</thought>", "", content)
                    content = content.strip()
            except Exception as e:
                logger.warning(f"AgenticRedTeam: target_callback error — {type(e).__name__}: {e}")
                content = f"[ERROR] {e}"

            logger.info(
                f"AgenticRedTeam: callback prompt[:80]='{input[:80]}' → response[:80]='{content[:80]}'"
            )
            return RTTurn(role="assistant", content=content)

        # ── Wrap canvas LangChain LLMs → DeepEvalBaseLLM ──
        def _make_deepeval_wrapper(langchain_llm, name_hint: str) -> DeepEvalBaseLLM:
            class _Wrapper(DeepEvalBaseLLM):
                def __init__(self):
                    self.model = langchain_llm

                def load_model(self):
                    return self.model

                def generate(self, prompt: str, schema: Any = None, *args, **kwargs) -> Any:
                    if schema is not None:
                        try:
                            structured_model = self.model.with_structured_output(schema)
                            return structured_model.invoke(prompt)
                        except Exception as e:
                            logger.warning(
                                f"AgenticRedTeam: Failed to get structured output from {name_hint} model via langchain: {e}. "
                                "Falling back to raw string generation and manual parsing."
                            )
                            resp = self.model.invoke(prompt)
                            content = resp.content if hasattr(resp, "content") else str(resp)
                            return _Wrapper.parse_json_to_schema(content, schema)
                    else:
                        resp = self.model.invoke(prompt)
                        return resp.content if hasattr(resp, "content") else str(resp)

                async def a_generate(self, prompt: str, schema: Any = None, *args, **kwargs) -> Any:
                    if schema is not None:
                        try:
                            structured_model = self.model.with_structured_output(schema)
                            return await structured_model.ainvoke(prompt)
                        except Exception as e:
                            logger.warning(
                                f"AgenticRedTeam: Failed to get structured output from {name_hint} model via langchain: {e}. "
                                "Falling back to raw string generation and manual parsing."
                            )
                            resp = await self.model.ainvoke(prompt)
                            content = resp.content if hasattr(resp, "content") else str(resp)
                            return _Wrapper.parse_json_to_schema(content, schema)
                    else:
                        resp = await self.model.ainvoke(prompt)
                        return resp.content if hasattr(resp, "content") else str(resp)

                def get_model_name(self) -> str:
                    return getattr(self.model, "model_name", name_hint)

                @staticmethod
                def parse_json_to_schema(text: str, schema: Any) -> Any:
                    import re
                    text_str = text.strip()
                    try:
                        if hasattr(schema, "model_validate_json"):
                            return schema.model_validate_json(text_str)
                        else:
                            return schema.parse_raw(text_str)
                    except Exception:
                        pass

                    # Regex 1: Markdown kod bloklarının (```json ... ```) içerisindeki JSON kısmını yakalama
                    json_block_match = re.search(r"```json\s*(.*?)\s*```", text_str, re.DOTALL)
                    if json_block_match:
                        try:
                            clean_content = json_block_match.group(1).strip()
                            if hasattr(schema, "model_validate_json"):
                                return schema.model_validate_json(clean_content)
                            else:
                                return schema.parse_raw(clean_content)
                        except Exception:
                            pass

                    # Regex 2: Metin içinde süslü parantezler { ... } arasına sıkışmış olan JSON'ı yakalama
                    braces_match = re.search(r"(\{.*\})", text_str, re.DOTALL)
                    if braces_match:
                        try:
                            clean_content = braces_match.group(1).strip()
                            if hasattr(schema, "model_validate_json"):
                                return schema.model_validate_json(clean_content)
                            else:
                                return schema.parse_raw(clean_content)
                        except Exception:
                            pass

                    # Son çare
                    if hasattr(schema, "model_validate_json"):
                        return schema.model_validate_json(text_str)
                    else:
                        return schema.parse_raw(text_str)

            return _Wrapper()

        # ── Validate & wrap canvas LLMs ──
        sim_llm  = connected_nodes.get("simulator_llm")
        eval_llm = connected_nodes.get("evaluator_llm")
        if sim_llm is None:
            raise ValueError("Simulator LLM is required. Connect a node to the 'Simulator LLM' port.")
        if eval_llm is None:
            raise ValueError("Evaluator LLM is required. Connect a node to the 'Evaluator LLM' port.")

        simulator_model = _make_deepeval_wrapper(sim_llm,  "simulator")
        evaluator_model = _make_deepeval_wrapper(eval_llm, "evaluator")

        logger.info(
            f"AgenticRedTeam: simulator={simulator_model.get_model_name()}, "
            f"evaluator={evaluator_model.get_model_name()}"
        )

        # ── Build attacks & vulnerabilities ──
        enable_owasp_asi = inputs.get("enable_owasp_asi", False)

        if enable_owasp_asi:
            # OWASP ASI 2026 — Agentic Security Initiative framework
            try:
                from deepteam.frameworks import OWASP_ASI_2026

                raw_cats   = inputs.get("owasp_asi_categories", "").strip()
                categories = [c.strip() for c in raw_cats.split(",") if c.strip()] or None
                owasp_asi       = OWASP_ASI_2026(categories=categories) if categories else OWASP_ASI_2026()
                attacks         = owasp_asi.attacks
                vulnerabilities = owasp_asi.vulnerabilities
                logger.info(f"AgenticRedTeam: OWASP ASI 2026 mode — categories={categories}")
            except (ImportError, AttributeError) as e:
                logger.warning(
                    f"AgenticRedTeam: OWASP_ASI_2026 not available ({e}). "
                    f"Falling back to manual agentic vulnerability selection."
                )
                enable_owasp_asi = False  # trigger the manual path below

        if not enable_owasp_asi:
            raw_vulns   = inputs.get("vulnerabilities", "") or ""
            raw_attacks = inputs.get("attacks", "") or ""

            # Jinja safety-net
            if _is_unresolved_jinja(raw_vulns):
                logger.warning(
                    f"AgenticRedTeam: 'vulnerabilities' contains unresolved Jinja token "
                    f"('{raw_vulns}'). Falling back to defaults."
                )
                raw_vulns = "GoalTheft, RecursiveHijacking, ExcessiveAgency, IndirectInstruction, AutonomousAgentDrift"
            if _is_unresolved_jinja(raw_attacks):
                logger.warning(
                    f"AgenticRedTeam: 'attacks' contains unresolved Jinja token "
                    f"('{raw_attacks}'). Falling back to defaults."
                )
                raw_attacks = "Prompt Injection, Jailbreaking, Roleplay"

            vuln_names   = [v.strip() for v in raw_vulns.split(",") if v.strip()]
            attack_names = [a.strip() for a in raw_attacks.split(",") if a.strip()]

            # Parse optional type overrides (JSON)
            type_overrides = None
            raw_type_overrides = inputs.get("vulnerability_types", "").strip()
            if raw_type_overrides:
                try:
                    type_overrides = json.loads(raw_type_overrides)
                    if not isinstance(type_overrides, dict):
                        logger.warning(
                            f"AgenticRedTeam: vulnerability_types must be a JSON object. "
                            f"Got {type(type_overrides).__name__}. Ignoring."
                        )
                        type_overrides = None
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"AgenticRedTeam: Failed to parse vulnerability_types JSON: {e}. "
                        f"Using all default types."
                    )

            vulnerabilities = _resolve_agentic_vulnerabilities(vuln_names, type_overrides)
            attacks         = _resolve_attacks(attack_names)

            if not vulnerabilities:
                available = sorted({v[0] for v in AGENTIC_VULNERABILITY_MAP.values()})
                raise ValueError(
                    f"No valid agentic vulnerabilities resolved from: {vuln_names}. "
                    f"Valid options: {', '.join(available)}"
                )
            if not attacks:
                raise ValueError(
                    f"No valid attacks resolved from: {attack_names}. "
                    f"Valid options include: Prompt Injection, Jailbreaking, ROT13, Roleplay, "
                    f"LinearJailbreaking, TreeJailbreaking, CrescendoJailbreaking, etc."
                )

        logger.info(
            f"AgenticRedTeam: vulns={[type(v).__name__ for v in vulnerabilities]}, "
            f"attacks={[type(a).__name__ for a in attacks]}, per_vuln={attacks_per_vuln}"
        )

        # ── Run DeepTeam scan ──
        try:
            results = red_team(
                model_callback=model_callback,
                simulator_model=simulator_model,
                evaluation_model=evaluator_model,
                vulnerabilities=vulnerabilities,
                attacks=attacks,
                attacks_per_vulnerability_type=attacks_per_vuln,
                target_purpose=target_purpose,
            )
        except Exception as e:
            logger.error(f"AgenticRedTeam: Scan failed — {type(e).__name__}: {e}")
            raise RuntimeError(f"Agentic red team scan failed: {e}") from e

        # ── Build & return report ──
        from deepteam.red_teamer.risk_assessment import EnumEncoder

        logger.info(
            f"AgenticRedTeam: results type={type(results).__name__}, "
            f"has_model_dump={hasattr(results, 'model_dump')}, "
            f"has_test_cases={hasattr(results, 'test_cases')}, "
            f"test_cases_count={len(results.test_cases) if hasattr(results, 'test_cases') else 'N/A'}"
        )

        report = self._build_report(results, inputs)
        logger.info(
            f"AgenticRedTeam: Scan complete — total_tests={report['scan_metadata']['total_tests']}"
        )
        return {"output": json.dumps(report, ensure_ascii=False, cls=EnumEncoder)}

    # ----------------------------------------------------------------
    # REPORT BUILDER
    # ----------------------------------------------------------------

    @staticmethod
    def _build_report(results, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DeepTeam results into a structured JSON report.

        Uses RiskAssessment.model_dump() + DeepTeam's own EnumEncoder —
        exactly the same serialization path as LLMRedTeamNode, extended
        with agentic-specific metadata fields.
        """
        from deepteam.red_teamer.risk_assessment import EnumEncoder

        # ── Normalise: unwrap legacy (DataFrame, RiskAssessment) tuple ──
        if isinstance(results, tuple):
            _, results = results

        # ── Primary path: RiskAssessment is a Pydantic BaseModel ──
        if hasattr(results, "model_dump"):
            raw = results.model_dump(by_alias=True)
            overview = raw.get("overview", {})
            detailed_results = raw.get("test_cases", [])
        # ── Fallback: unexpected shape ──
        else:
            logger.warning(
                f"AgenticRedTeam._build_report: unexpected results type "
                f"({type(results)}). Falling back to repr serialization."
            )
            overview = {}
            detailed_results = []
            try:
                overview = {
                    k: v for k, v in results.__dict__.items()
                    if not k.startswith("_")
                }
            except Exception:
                pass

        return {
            "overview": overview,
            "detailed_results": detailed_results,
            "scan_metadata": {
                "target_model":                   inputs.get("target_model_name", ""),
                "target_purpose":                 inputs.get("target_purpose", ""),
                "vulnerabilities_tested":         inputs.get("vulnerabilities", ""),
                "vulnerability_types_used":       inputs.get("vulnerability_types", ""),
                "attacks_used":                   inputs.get("attacks", ""),
                "attacks_per_vulnerability_type":  inputs.get("attacks_per_vuln_type", 3),
                "owasp_asi_mode":                 inputs.get("enable_owasp_asi", False),
                "agentic_scan":                   True,
                "total_tests":                    len(detailed_results),
            },
        }
