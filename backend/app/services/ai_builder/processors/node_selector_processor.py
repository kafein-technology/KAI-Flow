import logging
from typing import Dict, Any, List
from openai import AsyncOpenAI
from app.core.node_registry import node_registry
from app.services.ai_builder.state import AIBuilderState
from app.services.ai_builder.utils import extract_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert mapping assistant for KAI-Flow, a visual workflow builder.
Your ONLY task is to look at the user's request and determine WHICH of the available nodes are necessary to build the workflow.

AVAILABLE NODES:
{node_menu}

RULES:
1. ONLY return a JSON object with a single key "selected_nodes" containing a list of strings.
2. The strings must EXACTLY match the names of the nodes in the AVAILABLE NODES list.
3. If the user wants to fetch data from the internet/search, include TavilySearch.
4. If the user wants to scrape a specific URL, include WebScraper.
5. If the user wants to use AI/LLMs/agents, include Agent, BufferMemory, and OpenAIChat.
6. If the user wants to run code, include CodeNode.
7. Any workflow that triggers on an event/API must include WebhookTrigger and RespondToWebhook.
8. If the user wants to split documents for RAG, include ChunkSplitter.
9. If the user wants OpenRouter, Groq, DeepSeek, Ollama, LocalAI, vLLM, or a custom OpenAI-compatible endpoint, include OpenAICompatibleNode instead of OpenAIChat.
10. If the user wants to call a REST API, include HttpRequest. If they want to parse JSON/YAML, include JsonParserNode.
11. If the user wants encryption, decryption, signing, verification, or key generation, include CryptographyNode.
12. If the user wants Kafka, include KafkaConsumer for consuming/listening and KafkaProducer for publishing/sending.
13. If the user wants scheduled/timer execution, include TimerStart. If they want error handling for failed workflows, include ErrorTrigger.
14. If the user wants document conversion from MinIO/S3 to Markdown for an agent, include MarkItDownTool.
15. If the user wants red-team/security testing, include LLMRedTeam, CustomRedTeam, or AgenticRedTeam based on the request.
16. If you are unsure, err on the side of including a node so the Builder can decide whether to use it.
"""

FORMAT_INSTRUCTIONS = """
Respond with ONLY JSON. No markdown formatting.
Format:
{
  "selected_nodes": ["NodeName1", "NodeName2"]
}
"""


class NodeSelectorProcessor:
    def __init__(self):
        pass

    def _build_menu(self) -> str:
        nodes = node_registry.get_all_nodes()
        menu = []
        for n in nodes:
            # We only provide Name and a very brief Description. No schemas, no heavy rules.
            menu.append(f"- {n.name}: {n.description}")
        return "\n".join(menu)

    async def process(self, state: AIBuilderState) -> Dict[str, Any]:
        # If we are in edit mode, editing an existing workflow, we should probably
        # gather ALL nodes used in the existing workflow + any new ones.
        # But to keep it simple, the NodeSelector just reads the intent.

        api_key = state.get("api_key")
        if not api_key:
            logger.error("API key missing. Cannot select nodes.")
            return {"selected_nodes": []}

        # If we already have selected_nodes (e.g. from a loopback), don't re-run this to save tokens.
        selected = state.get("selected_nodes", [])
        if selected and len(selected) > 0:
            return {"selected_nodes": selected}

        prompt = SYSTEM_PROMPT.format(node_menu=self._build_menu()) + "\n\n" + FORMAT_INSTRUCTIONS

        user_content = state["question"]
        if state.get("mode", "build") == "edit" and state.get("original_workflow"):
            user_content = f"The user is EDITING an existing workflow. Edit request: {state['question']}"

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content}
        ]

        logger.info(f"NodeSelector generating necessary node list for request: '{state['question']}'")

        kwargs = {"api_key": api_key}
        if state.get("base_url"):
            kwargs["base_url"] = state["base_url"]
        client = AsyncOpenAI(**kwargs)

        response = await client.chat.completions.create(
            model=state.get("model_name") or "gpt-4o-mini",
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        result_nodes = []
        try:
            result = extract_json(content)
            result_nodes = result.get("selected_nodes", [])
            if state.get("mode", "build") == "edit":
                existing = [
                    n.get("type")
                    for n in state.get("original_workflow", {}).get("nodes", [])
                    if n.get("type")
                ]
                result_nodes = sorted(set(result_nodes + existing))
            logger.info(f"NodeSelector chose: {result_nodes}")
        except Exception as e:
            logger.error(f"Failed to parse NodeSelector response: {e}")

        return {"selected_nodes": result_nodes}
