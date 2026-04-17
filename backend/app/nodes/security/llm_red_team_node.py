"""
KAI-Flow LLM Red Team Node — Automated Adversarial Security Testing
Version: 5.1.0 (Jinja templating now works for all property types, April 2026)

Architecture (Tri-LLM Design):
- model_callback : async function wrapping the target LLM (built from webhook params)
- simulator_model: DeepEvalBaseLLM wrapping the canvas simulator LangChain LLM
- evaluator_model: DeepEvalBaseLLM wrapping the canvas evaluator LangChain LLM

References:
- https://trydeepteam.com/docs/red-teaming-introduction
- https://trydeepteam.com/docs/getting-started
- https://www.trydeepteam.com/guides/guide-red-teaming-openai
"""

import json
import logging
import os
from typing import Dict, Any, List

from langchain_core.runnables import Runnable
from ..base import (
    ProcessorNode, NodeInput, NodeOutput, NodeProperty,
    NodePropertyType, NodePosition, NodeType,
)

logger = logging.getLogger(__name__)

# ============================================================================
# NAME → CLASS MAPPINGS
# ============================================================================

VULNERABILITY_MAP = {
    "Bias": "Bias", "Toxicity": "Toxicity",
    "PII": "PIILeakage", "PIILeakage": "PIILeakage",
    "Misinformation": "Misinformation",
    "ExcessiveAgency": "ExcessiveAgency", "Excessive Agency": "ExcessiveAgency",
    "RBAC": "RBAC", "BOLA": "BOLA", "BFLA": "BFLA", "SSRF": "SSRF",
    "ShellInjection": "ShellInjection", "Shell Injection": "ShellInjection",
    "SQLInjection": "SQLInjection", "SQL Injection": "SQLInjection",
    "PromptLeakage": "PromptLeakage", "Prompt Leakage": "PromptLeakage",
    "IntellectualProperty": "IntellectualProperty", "Intellectual Property": "IntellectualProperty",
    "Competition": "Competition",
    "GraphicContent": "GraphicContent", "Graphic Content": "GraphicContent",
    "PersonalSafety": "PersonalSafety", "Personal Safety": "PersonalSafety",
    "IllegalActivity": "IllegalActivity", "Illegal Activity": "IllegalActivity",
    "ChildProtection": "ChildProtection", "Child Protection": "ChildProtection",
    "Ethics": "Ethics", "Fairness": "Fairness", "Robustness": "Robustness",
    "ExploitToolAgent": "ExploitToolAgent", "DebugAccess": "DebugAccess",
    "IndirectInstruction": "IndirectInstruction", "GoalTheft": "GoalTheft",
    "AgentIdentityAbuse": "AgentIdentityAbuse", "AutonomousAgentDrift": "AutonomousAgentDrift",
    "CrossContextRetrieval": "CrossContextRetrieval", "ToolOrchestrationAbuse": "ToolOrchestrationAbuse",
    "ToolMetadataPoisoning": "ToolMetadataPoisoning", "RecursiveHijacking": "RecursiveHijacking",
    "InsecureInterAgentCommunication": "InsecureInterAgentCommunication",
    "ExternalSystemAbuse": "ExternalSystemAbuse", "SystemReconnaissance": "SystemReconnaissance",
    "UnexpectedCodeExecution": "UnexpectedCodeExecution",
}

ATTACK_MAP = {
    "Prompt Injection": ("PromptInjection", "single"), "PromptInjection": ("PromptInjection", "single"),
    "Gray Box": ("GrayBox", "single"), "GrayBox": ("GrayBox", "single"),
    "Prompt Probing": ("PromptProbing", "single"), "PromptProbing": ("PromptProbing", "single"),
    "ROT13": ("ROT13", "single"), "Leetspeak": ("Leetspeak", "single"),
    "Math Problem": ("MathProblem", "single"), "MathProblem": ("MathProblem", "single"),
    "Multilingual": ("Multilingual", "single"), "Roleplay": ("Roleplay", "single"),
    "AuthorityEscalation": ("AuthorityEscalation", "single"), "Authority Escalation": ("AuthorityEscalation", "single"),
    "EmotionalManipulation": ("EmotionalManipulation", "single"), "Emotional Manipulation": ("EmotionalManipulation", "single"),
    "GoalRedirection": ("GoalRedirection", "single"), "Goal Redirection": ("GoalRedirection", "single"),
    "ContextFlooding": ("ContextFlooding", "single"), "Context Flooding": ("ContextFlooding", "single"),
    "ContextPoisoning": ("ContextPoisoning", "single"), "Context Poisoning": ("ContextPoisoning", "single"),
    "SystemOverride": ("SystemOverride", "single"), "System Override": ("SystemOverride", "single"),
    "InputBypass": ("InputBypass", "single"), "Input Bypass": ("InputBypass", "single"),
    "PermissionEscalation": ("PermissionEscalation", "single"), "Permission Escalation": ("PermissionEscalation", "single"),
    "AdversarialPoetry": ("AdversarialPoetry", "single"), "Adversarial Poetry": ("AdversarialPoetry", "single"),
    "CharacterStream": ("CharacterStream", "single"), "Character Stream": ("CharacterStream", "single"),
    "LinguisticConfusion": ("LinguisticConfusion", "single"), "Linguistic Confusion": ("LinguisticConfusion", "single"),
    "EmbeddedInstructionJSON": ("EmbeddedInstructionJSON", "single"),
    "SyntheticContextInjection": ("SyntheticContextInjection", "single"),
    "Jailbreaking": ("LinearJailbreaking", "multi"), "LinearJailbreaking": ("LinearJailbreaking", "multi"),
    "Linear Jailbreaking": ("LinearJailbreaking", "multi"),
    "TreeJailbreaking": ("TreeJailbreaking", "multi"), "Tree Jailbreaking": ("TreeJailbreaking", "multi"),
    "CrescendoJailbreaking": ("CrescendoJailbreaking", "multi"), "Crescendo Jailbreaking": ("CrescendoJailbreaking", "multi"),
    "BadLikertJudge": ("BadLikertJudge", "multi"), "Bad Likert Judge": ("BadLikertJudge", "multi"),
    "SequentialJailbreak": ("SequentialJailbreak", "multi"), "Sequential Jailbreak": ("SequentialJailbreak", "multi"),
}


def _is_unresolved_jinja(value: str) -> bool:
    """Return True if the value still contains an un-rendered Jinja expression."""
    return "${{" in value or "{{" in value


def _resolve_vulnerabilities(names: List[str]) -> list:
    import deepteam.vulnerabilities as m
    result = []
    for name in names:
        cls_name = VULNERABILITY_MAP.get(name.strip())
        if cls_name and hasattr(m, cls_name):
            result.append(getattr(m, cls_name)())
        else:
            logger.warning(f"Unknown vulnerability: '{name}'. Skipping.")
    return result


def _resolve_attacks(names: List[str]) -> list:
    import deepteam.attacks.single_turn as st
    import deepteam.attacks.multi_turn as mt
    pool = {
        attr: getattr(mod, attr)
        for mod in (st, mt)
        for attr in dir(mod)
        if attr[0].isupper() and not attr.startswith("Base")
    }
    result = []
    for name in names:
        entry = ATTACK_MAP.get(name.strip())
        if not entry:
            logger.warning(f"Unknown attack: '{name}'. Skipping.")
            continue
        cls = pool.get(entry[0])
        if cls:
            result.append(cls())
        else:
            logger.warning(f"Attack class '{entry[0]}' not found. Skipping.")
    return result


# ============================================================================
# LLM RED TEAM NODE
# ============================================================================

class LLMRedTeamNode(ProcessorNode):
    """LLM Red Team Scanner — Automated adversarial security testing."""

    def __init__(self):
        super().__init__()
        self._metadata = self._build_metadata()

    def _build_metadata(self) -> Dict[str, Any]:
        return {
            "name": "LLMRedTeam",
            "display_name": "LLM Red Team Scanner",
            "description": "Automated adversarial security testing for LLMs using DeepTeam.",
            "category": "Security",
            "node_type": NodeType.PROCESSOR,
            "colors": ["red-500", "rose-600"],
            "icon": {"name": "shield-alert", "path": None, "alt": None},
            "inputs": self._build_inputs(),
            "outputs": self._build_outputs(),
            "properties": self._build_properties(),
        }

    def _build_inputs(self) -> List[NodeInput]:
        return [
            NodeInput(name="input", displayName="Input", type="string",
                      is_connection=True, required=True,
                      description="Input from trigger node."),
            NodeInput(name="simulator_llm", displayName="Simulator LLM",
                      type="BaseLanguageModel", is_connection=True, required=True,
                      direction=NodePosition.BOTTOM,
                      description="Generates adversarial attack prompts."),
            NodeInput(name="evaluator_llm", displayName="Evaluator LLM",
                      type="BaseLanguageModel", is_connection=True, required=True,
                      direction=NodePosition.BOTTOM,
                      description="Judges whether attacks succeeded."),
        ]

    def _build_outputs(self) -> List[NodeOutput]:
        return [NodeOutput(name="output", displayName="Scan Results", type="string",
                           is_connection=True, description="Risk assessment JSON report.")]

    def _build_properties(self) -> List[NodeProperty]:
        return [
            # ── Target ──
            NodeProperty(name="target_base_url", displayName="Target Base URL",
                         type=NodePropertyType.TEXT, default="",
                         hint="OpenAI-compatible base URL. Supports Jinja: ${{ webhook_trigger.target_base_url }}",
                         placeholder="https://api.openai.com/v1", required=True),
            NodeProperty(name="target_model_name", displayName="Target Model Name",
                         type=NodePropertyType.TEXT, default="",
                         hint="Model identifier. Supports Jinja: ${{ webhook_trigger.target_model_name }}",
                         placeholder="gpt-4o-mini", required=True),
            NodeProperty(name="target_api_key", displayName="Target API Key",
                         type=NodePropertyType.TEXT, default="",
                         hint="API key. Supports Jinja: ${{ webhook_trigger.target_api_key }}",
                         placeholder="sk-... or ${{ webhook_trigger.target_api_key }}", required=True),
            # ── Scan ──
            NodeProperty(name="target_purpose", displayName="Target Purpose",
                         type=NodePropertyType.TEXT_AREA, default="General purpose chatbot",
                         hint="Describe what the target LLM does.", required=False),
            NodeProperty(name="target_system_prompt", displayName="Target System Prompt",
                         type=NodePropertyType.TEXT_AREA, default="",
                         hint="System prompt of the target model.", required=False),
            NodeProperty(name="vulnerabilities", displayName="Vulnerabilities",
                         type=NodePropertyType.TEXT_AREA, default="Bias, PII, Toxicity",
                         hint="Comma-separated. Supports Jinja: ${{ webhook_trigger.vulnerabilities }}. E.g: Bias, PII, Toxicity, RBAC, ExcessiveAgency",
                         required=True),
            NodeProperty(name="attacks", displayName="Attack Vectors",
                         type=NodePropertyType.TEXT_AREA, default="Prompt Injection, Jailbreaking",
                         hint="Comma-separated. Supports Jinja: ${{ webhook_trigger.attacks }}. E.g: Prompt Injection, Jailbreaking, ROT13, Leetspeak",
                         required=True),
            NodeProperty(name="attacks_per_vuln_type", displayName="Attacks Per Vulnerability",
                         type=NodePropertyType.NUMBER, default=3, min=1, max=50,
                         hint="Number of attack attempts per vulnerability type.", required=True),
            # ── Advanced ──
            NodeProperty(name="max_concurrent", displayName="Max Concurrent",
                         type=NodePropertyType.NUMBER, default=1, min=1, max=20,
                         hint="Maximum concurrent attack tasks.", tabName="advanced", required=False),
            NodeProperty(name="enable_owasp", displayName="Use OWASP Top 10 for LLMs",
                         type=NodePropertyType.CHECKBOX, default=False,
                         hint="Use OWASP LLM Top 10 instead of custom vulnerability/attack selection.",
                         tabName="advanced", required=False),
            NodeProperty(name="owasp_categories", displayName="OWASP Categories",
                         type=NodePropertyType.TEXT_AREA, default="",
                         hint="Comma-separated OWASP IDs. E.g: LLM_01, LLM_06. Leave empty for all.",
                         tabName="advanced", displayOptions={"show": {"enable_owasp": True}},
                         required=False),
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
            "attacks", "attacks_per_vuln_type", "max_concurrent",
            "enable_owasp", "owasp_categories",
        ]:
            if key not in inputs and isinstance(self.user_data, dict) and key in self.user_data:
                inputs[key] = self.user_data[key]

        # ── Validate & extract target params ──
        target_base_url      = inputs.get("target_base_url", "").strip()
        target_model_name    = inputs.get("target_model_name", "").strip()
        target_api_key       = inputs.get("target_api_key", "").strip() or "sk-no-key"
        target_system_prompt = inputs.get("target_system_prompt", "").strip()
        target_purpose       = inputs.get("target_purpose", "General purpose chatbot")
        attacks_per_vuln     = int(inputs.get("attacks_per_vuln_type", 3))

        if not target_base_url or not target_model_name:
            raise ValueError(
                f"target_base_url and target_model_name are required. "
                f"Got: base_url='{target_base_url}', model='{target_model_name}'"
            )

        logger.info(f"LLMRedTeam: target={target_model_name} @ {target_base_url}")

        # ── Build raw OpenAI client for target ──
        # Using openai.OpenAI directly — aligned with official DeepTeam guide pattern.
        # LangChain is NOT used for the target to avoid extra wrapper complexity.
        target_client = OpenAI(base_url=target_base_url, api_key=target_api_key)

        # ── model_callback — async function (official docs pattern) ──
        # Signature: async def model_callback(input: str, turns=None) -> RTTurn
        # - `input`  : the adversarial prompt generated by DeepTeam
        # - `turns`  : prior conversation turns for multi-turn attacks (optional)
        # - Returns  : RTTurn(role="assistant", content=...) per official docs
        #   RTTurn.content= field is used (NOT .data= which was incorrect in v2)
        async def model_callback(input: str, turns=None) -> RTTurn:
            messages = []

            # Inject system prompt if configured
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
                resp = target_client.chat.completions.create(
                    model=target_model_name,
                    messages=messages,
                    temperature=0.0,
                )
                content = resp.choices[0].message.content or "[ERROR] No content returned."
            except Exception as e:
                logger.warning(f"LLMRedTeam: target_callback error — {type(e).__name__}: {e}")
                content = f"[ERROR] {e}"

            logger.info(f"LLMRedTeam: callback prompt[:80]='{input[:80]}' → response[:80]='{content[:80]}'")
            return RTTurn(role="assistant", content=content)

        # ── Wrap canvas LangChain LLMs → DeepEvalBaseLLM ──
        # Pattern from official DeepEval docs (Azure OpenAI example):
        # - self.model holds the underlying model object
        # - generate(prompt) → str  (no schema confinement needed for OpenAI-compatible APIs)
        # - a_generate() uses ainvoke() for true async execution
        def _make_deepeval_wrapper(langchain_llm, name_hint: str) -> DeepEvalBaseLLM:
            class _Wrapper(DeepEvalBaseLLM):
                def __init__(self):
                    self.model = langchain_llm

                def load_model(self):
                    return self.model

                def generate(self, prompt: str) -> str:
                    resp = self.model.invoke(prompt)
                    return resp.content if hasattr(resp, "content") else str(resp)

                async def a_generate(self, prompt: str) -> str:
                    resp = await self.model.ainvoke(prompt)
                    return resp.content if hasattr(resp, "content") else str(resp)

                def get_model_name(self) -> str:
                    return getattr(self.model, "model_name", name_hint)

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

        logger.info(f"LLMRedTeam: simulator={simulator_model.get_model_name()}, "
                    f"evaluator={evaluator_model.get_model_name()}")

        # ── Build attacks & vulnerabilities ──
        enable_owasp = inputs.get("enable_owasp", False)

        if enable_owasp:
            # OWASP Top 10 for LLMs mode — official framework support
            from deepteam.frameworks import OWASPTop10
            raw_cats   = inputs.get("owasp_categories", "").strip()
            categories = [c.strip() for c in raw_cats.split(",") if c.strip()] or None
            owasp          = OWASPTop10(categories=categories) if categories else OWASPTop10()
            attacks        = owasp.attacks
            vulnerabilities = owasp.vulnerabilities
            logger.info(f"LLMRedTeam: OWASP mode — categories={categories}")
        else:
            raw_vulns   = inputs.get("vulnerabilities", "") or ""
            raw_attacks = inputs.get("attacks", "") or ""

            # Safety-net: if Jinja resolution somehow failed and the raw template
            # slipped through, fall back to defaults instead of crashing.
            if _is_unresolved_jinja(raw_vulns):
                logger.warning(
                    f"LLMRedTeam: 'vulnerabilities' still contains an unresolved Jinja token "
                    f"('{raw_vulns}'). Falling back to default: 'Bias, PII, Toxicity'."
                )
                raw_vulns = "Bias, PII, Toxicity"
            if _is_unresolved_jinja(raw_attacks):
                logger.warning(
                    f"LLMRedTeam: 'attacks' still contains an unresolved Jinja token "
                    f"('{raw_attacks}'). Falling back to default: 'Prompt Injection, Jailbreaking'."
                )
                raw_attacks = "Prompt Injection, Jailbreaking"

            vuln_names   = [v.strip() for v in raw_vulns.split(",") if v.strip()]
            attack_names = [a.strip() for a in raw_attacks.split(",") if a.strip()]
            vulnerabilities = _resolve_vulnerabilities(vuln_names)
            attacks         = _resolve_attacks(attack_names)
            if not vulnerabilities:
                raise ValueError(
                    f"No valid vulnerabilities resolved from: {vuln_names}. "
                    f"Valid options include: Bias, PII, Toxicity, RBAC, ExcessiveAgency, "
                    f"ShellInjection, SQLInjection, PromptLeakage, Misinformation, etc."
                )
            if not attacks:
                raise ValueError(
                    f"No valid attacks resolved from: {attack_names}. "
                    f"Valid options include: Prompt Injection, Jailbreaking, ROT13, Base64, "
                    f"Multilingual, Roleplay, LinearJailbreaking, TreeJailbreaking, etc."
                )

        logger.info(f"LLMRedTeam: vulns={[type(v).__name__ for v in vulnerabilities]}, "
                    f"attacks={[type(a).__name__ for a in attacks]}, per_vuln={attacks_per_vuln}")

        # ── Run DeepTeam scan ──
        try:
            results = red_team(
                model_callback=model_callback,        # async function — official docs pattern
                simulator_model=simulator_model,
                evaluation_model=evaluator_model,
                vulnerabilities=vulnerabilities,
                attacks=attacks,
                attacks_per_vulnerability_type=attacks_per_vuln,
                target_purpose=target_purpose,
            )
        except Exception as e:
            logger.error(f"LLMRedTeam: Scan failed — {type(e).__name__}: {e}")
            raise RuntimeError(f"Red team scan failed: {e}") from e

        # ── Build & return report ──
        from deepteam.red_teamer.risk_assessment import EnumEncoder

        # ── DIAGNOSTIC: confirm what red_team() actually returned ──
        logger.info(
            f"LLMRedTeam: results type={type(results).__name__}, "
            f"has_model_dump={hasattr(results, 'model_dump')}, "
            f"has_test_cases={hasattr(results, 'test_cases')}, "
            f"test_cases_count={len(results.test_cases) if hasattr(results, 'test_cases') else 'N/A'}"
        )

        report = self._build_report(results, inputs)
        logger.info(f"LLMRedTeam: Scan complete — total_tests={report['scan_metadata']['total_tests']}")
        return {"output": json.dumps(report, ensure_ascii=False, cls=EnumEncoder)}

    # ----------------------------------------------------------------
    # REPORT BUILDER
    # ----------------------------------------------------------------

    @staticmethod
    def _build_report(results, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DeepTeam results into a structured, fully-parsed JSON report.

        Uses RiskAssessment.model_dump() + DeepTeam's own EnumEncoder —
        exactly the same serialization path that RiskAssessment.save() uses
        internally. This guarantees:
          - Enums → string values  (no more '<ToxicityType.PROFANITY: ...>')
          - Nested Pydantic models → plain dicts
          - test_cases → proper list of objects in detailed_results
          - total_tests → accurate count
        """
        from deepteam.red_teamer.risk_assessment import EnumEncoder

        # ── Normalise: unwrap legacy (DataFrame, RiskAssessment) tuple ──
        if isinstance(results, tuple):
            # Older DeepTeam returned (DataFrame, RiskAssessment)
            _, results = results   # discard DataFrame; use the assessment object

        # ── Primary path: RiskAssessment is a Pydantic BaseModel ──
        if hasattr(results, "model_dump"):
            # model_dump() recursively converts every nested model to a plain
            # dict. EnumEncoder handles any remaining Enum values.
            raw = results.model_dump(by_alias=True)

            # overview  = the summary stats block
            overview = raw.get("overview", {})

            # detailed_results = the individual test case results
            detailed_results = raw.get("test_cases", [])

        # ── Fallback: unexpected shape — store whatever we have ──
        else:
            logger.warning(
                "LLMRedTeam._build_report: unexpected results type "
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
            "overview":        overview,
            "detailed_results": detailed_results,
            "scan_metadata": {
                "target_model":                   inputs.get("target_model_name", ""),
                "target_purpose":                 inputs.get("target_purpose", ""),
                "vulnerabilities_tested":         inputs.get("vulnerabilities", ""),
                "attacks_used":                   inputs.get("attacks", ""),
                "attacks_per_vulnerability_type": inputs.get("attacks_per_vuln_type", 3),
                "owasp_mode":                     inputs.get("enable_owasp", False),
                "total_tests":                    len(detailed_results),
            },
        }