import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AI_BUILDER = ROOT / "app" / "services" / "ai_builder"


def test_ai_rules_use_current_node_names():
    rules = runpy.run_path(AI_BUILDER / "ai_rules_registry.py")["AI_RULES_REGISTRY"]

    deprecated_names = {
        "CohereReranker",
        "ConversationMemory",
        "HttpClient",
        "KafkaTrigger",
        "ReactAgent",
        "StringInput",
    }
    current_names = {
        "Agent",
        "BufferMemory",
        "CohereRerankerProvider",
        "CryptographyNode",
        "ErrorTrigger",
        "HttpRequest",
        "JsonParserNode",
        "KafkaConsumer",
        "MarkItDownTool",
        "OpenAICompatibleNode",
        "StringInputNode",
    }

    assert deprecated_names.isdisjoint(rules)
    assert current_names <= set(rules)


def test_ai_builder_templates_do_not_reference_removed_nodes():
    removed_node_names = {"LLMChain", "PromptTemplate", "TavilySearchNode"}

    used = set()
    for path in (AI_BUILDER / "ai_builder_templates").glob("*.json"):
        workflow = json.loads(path.read_text(encoding="utf-8"))["workflow"]
        used.update(node["type"] for node in workflow["nodes"])

    assert removed_node_names.isdisjoint(used)


if __name__ == "__main__":
    test_ai_rules_use_current_node_names()
    test_ai_builder_templates_do_not_reference_removed_nodes()
