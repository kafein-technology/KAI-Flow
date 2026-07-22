import os
import logging
from typing import Dict, Any, List
from ..base import NodeProperty, ProviderNode, NodeInput, NodeOutput, NodeType, NodePosition, NodePropertyType
from app.models.node import NodeCategory
from serpdive import SerpDive
from langchain_core.tools import Tool

logger = logging.getLogger(__name__)

# ================================================================================
# SERPDIVE SEARCH NODE - ANSWER-READY WEB SEARCH PROVIDER
# ================================================================================
# SERPdive returns extracted, answer-ready page content instead of a list of
# links, so the agent reads the sentences that answer the query rather than
# fetching and cleaning pages itself. Two models: "mako" (fast, key sentences)
# and "moby" (full readable page text). Mirrors the TavilySearchNode shape.


class SerpdiveSearchNode(ProviderNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "SerpdiveSearch",
            "display_name": "SERPdive Web Search",
            "description": "Performs a web search using the SERPdive API, returning extracted, answer-ready page content.",
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {"name": "serpdive_search", "path": "icons/serpdive_search.svg", "alt": "serpdivesearchicon"},
            "colors": ["teal-500", "cyan-600"],
            "inputs": [
                NodeInput(name="max_results", type="int", default=5, description="The maximum number of results to return (1-10)."),
                NodeInput(name="model", type="str", default="mako", choices=["mako", "moby"], description="Retrieval depth: 'mako' (fast, key sentences) or 'moby' (full page text)."),
                NodeInput(name="answer", type="bool", default=True, description="Whether to include a written answer built from the sources."),
            ],
            "outputs": [
                NodeOutput(
                    name="search_tool",
                    displayName="Search Tool",
                    type="BaseTool",
                    description="A configured SERPdive search tool ready for use with agents.",
                    direction=NodePosition.TOP,
                    is_connection=True
                )
            ],
            "properties": [
                NodeProperty(
                    name="credential_id",
                    displayName="Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    placeholder="Select Credential",
                    required=True,
                    serviceType="serpdive_search",
                ),
                NodeProperty(
                    name="model",
                    displayName="Model",
                    type=NodePropertyType.SELECT,
                    default="mako",
                    options=[{"label": "Mako (fast, key sentences)", "value": "mako"}, {"label": "Moby (full page text)", "value": "moby"}],
                    required=True,
                ),
                NodeProperty(
                    name="max_results",
                    displayName="Max Results",
                    default=5,
                    type=NodePropertyType.NUMBER,
                    min=1,
                    max=10,
                    required=False
                ),
                NodeProperty(
                    name="answer",
                    displayName="Include Answer",
                    type=NodePropertyType.CHECKBOX,
                    hint="Include a written answer built from the sources"
                ),
            ]
        }

    def get_required_packages(self) -> List[str]:
        """Python packages this node needs, for the dynamic export system."""
        return [
            "serpdive>=0.1.1",   # SERPdive Python SDK
            "pydantic>=2.5.0",   # Data validation
        ]

    def execute(self, **kwargs) -> Dict[str, Any]:
        """Create a SERPdive search tool, following the TavilySearchNode pattern."""
        logger.info("\nSERPDIVE SEARCH SETUP")

        try:
            # 1. Resolve the API key from the credential store or the environment.
            api_key = None
            credential_id = kwargs.get("credential_id") or self.user_data.get("credential_id")
            if credential_id:
                cred = self.get_credential(credential_id)
                if cred and cred.get("secret"):
                    api_key = cred.get("secret").get("api_key")

            if not api_key:
                api_key = os.getenv("SERPDIVE_API_KEY")

            logger.info(f"   API Key: {'Found' if api_key else 'Missing'}")
            if api_key:
                logger.info(f"   Source: {'User Config' if credential_id else 'Environment'}")

            if not api_key:
                raise ValueError(
                    "SERPdive API key is required. Please provide it in the node configuration "
                    "or set the SERPDIVE_API_KEY environment variable. Free key at "
                    "https://serpdive.com/dashboard/keys"
                )

            # 2. Read the remaining parameters from kwargs or user data.
            max_results_val = kwargs.get("max_results")
            if max_results_val is None:
                max_results_val = self.user_data.get("max_results", 5)
            max_results = int(max_results_val)

            model = kwargs.get("model") or self.user_data.get("model", "mako")

            answer_val = kwargs.get("answer")
            if answer_val is None:
                answer_val = self.user_data.get("answer", True)
            if isinstance(answer_val, str):
                answer = answer_val.lower() in ("true", "1", "yes")
            else:
                answer = bool(answer_val)

            search_config = {"max_results": max_results, "model": model, "answer": answer}

            # 3. Create the client and a quick connection test.
            client = SerpDive(api_key=api_key, timeout=80.0)
            try:
                test_result = client.search("test query", max_results=1)
                logger.info(f"   API Test: Success ({len(test_result.results)} results)")
            except Exception as test_error:
                logger.error(f"   API Test: Failed ({str(test_error)[:50]}...)")

            # 4. Create the agent-ready tool.
            search_tool = self._create_search_tool(client, search_config)

            logger.info(f"   Tool Created: {search_tool.name} | Max Results: {max_results} | Model: {model}")

            return {
                "serpdive_web_search": {"tool": search_tool}
            }

        except Exception as e:
            error_msg = f"SerpdiveSearchNode execution failed: {str(e)}"
            logger.error(f"{error_msg}")
            raise ValueError(error_msg) from e

    def _create_search_tool(self, client: SerpDive, search_config: Dict[str, Any]) -> Tool:
        """Create a LangChain Tool with agent-optimized formatting."""

        def serpdive_web_search(query: str) -> str:
            """Web search function that agents will call."""
            try:
                logger.info(f"Agent performing web search for: {query}")

                response = client.search(
                    query,
                    model=search_config["model"],
                    answer=search_config["answer"],
                    max_results=search_config["max_results"],
                )

                if not response.results:
                    return f"""WEB SEARCH RESULTS - SERPdive
Query: No web results found for '{query}'.

SEARCH SUMMARY:
- Search completed but no relevant web pages were found
- You may try using different search terms or be more specific
- Search Engine: SERPdive
- Model: {search_config['model']}
- Max Results: {search_config['max_results']}"""

                result_parts = [
                    "WEB SEARCH RESULTS - SERPdive",
                    f"Query: {query}",
                    f"Model: {search_config['model']}",
                    f"Max Results: {search_config['max_results']}",
                    "",
                ]

                if response.answer:
                    result_parts.extend(["ANSWER:", response.answer, ""])

                result_parts.append(f"Total results found: {len(response.results)}")
                result_parts.append("")

                for i, result in enumerate(response.results, 1):
                    content = result.content or "No content"
                    if len(content) > 400:
                        content = content[:400] + "..."
                    lines = [
                        f"=== RESULT {i} ===",
                        f"Title: {result.title or 'No title'}",
                        f"URL: {result.url}",
                    ]
                    if getattr(result, "date", None):
                        lines.append(f"Date: {result.date}")
                    lines.extend([f"Content: {content}", "", "---", ""])
                    result_parts.extend(lines)

                result_parts.extend([
                    "",
                    "SEARCH SUMMARY:",
                    f"- These web search results are the most relevant for the query '{query}'",
                    "- Search Engine: SERPdive API",
                    f"- Model: {search_config['model']} (mako = key sentences, moby = full page text)",
                    "- Content is extracted, answer-ready page text, not just links",
                ])

                return "\n".join(result_parts)

            except Exception as e:
                error_msg = str(e)
                return f"""WEB SEARCH RESULTS - SERPdive
Query: A technical issue occurred while searching for '{query}'.

ERROR DETAILS:
{error_msg}

SEARCH SUMMARY:
- Web search could not be completed due to technical issues
- Search Engine: SERPdive API
- Please try again with different search terms"""

        return Tool(
            name="serpdive_web_search",
            description="Search the web for current information, news, and real-time data using SERPdive. Returns extracted, answer-ready page content instead of links. Use this tool when you need up-to-date information that may not be in your training data.",
            func=serpdive_web_search
        )


# Alias for frontend compatibility
SerpdiveNode = SerpdiveSearchNode
