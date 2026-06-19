import logging
from typing import Dict, Any
from app.core.node_registry import node_registry
from app.core.graph_builder.validation import ValidationEngine
from app.services.ai_builder.state import AIBuilderState

logger = logging.getLogger(__name__)


class ValidationProcessor:
    def __init__(self):
        self.validator = ValidationEngine(node_registry)

    def process(self, state: AIBuilderState) -> Dict[str, Any]:
        if state.get("validation_errors", []):
            return {"validation_errors": state.get("validation_errors", [])}

        workflow_dict = state.get("current_workflow", {})
        try:
            result = self.validator.validate_workflow(workflow_dict)
            errors = []

            if hasattr(result, 'errors'):
                for err in result.errors:
                    errors.append(str(err))
            elif isinstance(result, list):
                errors.extend([str(e) for e in result])

            nodes_by_id = {n.get("id"): n for n in workflow_dict.get("nodes", [])}
            edges = workflow_dict.get("edges", [])
            node_types = [n.get("type") for n in workflow_dict.get("nodes", [])]

            # RULE 1: Webhook Trigger must not have an EndNode
            if "WebhookTrigger" in node_types and "EndNode" in node_types:
                errors.append(
                    "TOPOLOGY ERROR: Workflows starting with WebhookTrigger MUST NOT use EndNode. "
                    "They must ALWAYS use RespondToWebhook as their termination node. Replace EndNode with RespondToWebhook."
                )

            # RULE 2: Agent MUST have LLM connected and Memory
            agents = [n for n in workflow_dict.get("nodes", []) if n.get("type") == "Agent"]
            for agent in agents:
                has_llm = False
                has_memory = False
                for edge in edges:
                    if edge.get("target") == agent.get("id"):
                        src_node = nodes_by_id.get(edge.get("source"))
                        if not src_node:
                            continue
                        src_type = src_node.get("type", "")

                        if edge.get("targetHandle") == "llm" and ("OpenAI" in src_type or "LLM" in src_type or "Model" in src_type):
                            has_llm = True
                        elif edge.get("targetHandle") == "memory" and "Memory" in src_type:
                            has_memory = True

                if not has_llm:
                    errors.append(f"TOPOLOGY ERROR: Agent '{agent.get('id')}' is missing a valid LLM connection. Connect an OpenAIChat/OpenAICompatibleNode to its 'llm' input.")
                if not has_memory:
                    errors.append(f"TOPOLOGY ERROR: Agent '{agent.get('id')}' is missing a valid Memory connection. Connect BufferMemory to its 'memory' input.")

            # RULE 3: Mutually Exclusive Entrypoints
            entrypoint_types = ["StartNode", "WebhookTrigger", "KafkaConsumer", "TimerStart", "ErrorTrigger"]
            entrypoints = [n.get("type") for n in workflow_dict.get("nodes", []) if n.get("type") in entrypoint_types]
            if len(entrypoints) > 1 and "StartNode" in entrypoints and any(t in entrypoints for t in entrypoint_types if t != "StartNode"):
                errors.append(
                    f"TOPOLOGY ERROR: You cannot mix 'StartNode' with event triggers like 'WebhookTrigger', 'KafkaConsumer', 'TimerStart', or 'ErrorTrigger'. "
                    f"Found: {entrypoints}. Keep ONLY ONE type of entrypoint."
                )

            # RULE 4: VectorStores and Retrievers MUST have an Embedder
            rag_nodes = [n for n in workflow_dict.get("nodes", []) if n.get("type") in ["VectorStoreOrchestrator", "RetrieverProvider"]]
            for rag_node in rag_nodes:
                has_embedder = False
                for edge in edges:
                    if edge.get("target") == rag_node.get("id") and edge.get("targetHandle") == "embedder":
                        src_node = nodes_by_id.get(edge.get("source"))
                        if src_node and "Embeddings" in src_node.get("type", ""):
                            has_embedder = True
                            break
                if not has_embedder:
                    errors.append(
                        f"TOPOLOGY ERROR: The node '{rag_node.get('type')}' ({rag_node.get('id')}) REQUIRES an 'OpenAIEmbeddingsProvider'. Connect it to the 'embedder' input."
                    )

            # RULE 5: ChunkSplitter and VectorStores MUST have an incoming Document connection
            document_consumers = [n for n in workflow_dict.get("nodes", []) if "Splitter" in str(n.get("type", "")) or n.get("type") == "VectorStoreOrchestrator"]
            for consumer in document_consumers:
                has_documents = False
                for edge in edges:
                    if edge.get("target") == consumer.get("id") and edge.get("targetHandle") == "documents":
                        src_node = nodes_by_id.get(edge.get("source"))
                        if src_node and ("Scraper" in src_node.get("type", "") or "Loader" in src_node.get("type", "") or "Splitter" in src_node.get("type", "")):
                            has_documents = True
                            break
                if not has_documents:
                    errors.append(
                        f"TOPOLOGY ERROR: '{consumer.get('type')}' ({consumer.get('id')}) MUST receive actual 'documents'. Connect it from a DocumentLoader, WebScraper, or ChunkSplitter."
                    )

            # RULE 6: RespondToWebhook MUST have an incoming connection from a processing node
            responders = [n for n in workflow_dict.get("nodes", []) if n.get("type") == "RespondToWebhook"]
            response_sources = ["Agent", "ConditionNode", "CodeNode", "StringInputNode", "JsonParserNode", "CryptographyNode", "HttpRequest"]
            for responder in responders:
                has_input = False
                for edge in edges:
                    if edge.get("target") == responder.get("id"):
                        src_node = nodes_by_id.get(edge.get("source"))
                        if src_node and src_node.get("type") in response_sources:
                            has_input = True
                            break
                if not has_input:
                    errors.append(
                        f"TOPOLOGY ERROR: 'RespondToWebhook' MUST have an incoming connection from a processing node (Agent, CodeNode, ConditionNode, JsonParserNode, CryptographyNode, HttpRequest)."
                    )

            # RULE 7: KafkaProducer MUST connect its output to EndNode
            producers = [n for n in workflow_dict.get("nodes", []) if n.get("type") == "KafkaProducer"]
            for producer in producers:
                has_end_target = False
                for edge in edges:
                    if edge.get("source") == producer.get("id"):
                        target_id = edge.get("target")
                        target_node = next((n for n in workflow_dict.get("nodes", []) if n.get("id") == target_id), None)
                        if target_node and target_node.get("type") == "EndNode":
                            has_end_target = True
                            break
                if not has_end_target:
                    errors.append(
                        f"TOPOLOGY ERROR: 'KafkaProducer' ({producer.get('id')}) outputs stream data and MUST connect its output to an 'EndNode'."
                    )

            if errors:
                logger.warning(f"❌ [VALIDATION GUARD] Found {len(errors)} errors. Forcing LLM self-correction loop.")
                for e in errors:
                    logger.warning(f"  -> {e[:150]}...")
            else:
                logger.info(f"✅ [VALIDATION GUARD] Workflow topology is flawless! Proceeding.")

            return {"validation_errors": errors}
        except Exception as e:
            logger.error(f"❌ [VALIDATION GUARD] CRASH: {str(e)}")
            return {"validation_errors": [f"Validation exception: {str(e)}"]}
