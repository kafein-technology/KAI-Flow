import os
import logging
from typing import Dict, Any, Optional, List
from ..base import NodeProperty, ProviderNode, NodeInput, NodeOutput, NodeType, NodePosition, NodePropertyType
from app.models.node import NodeCategory
from langchain_tavily import TavilySearch
from langchain_core.tools import Tool

logger = logging.getLogger(__name__)

# ================================================================================
# TAVILY SEARCH NODE - ENTERPRISE WEB INTELLIGENCE PROVIDER
# ================================================================================

class TavilySearchNode(ProviderNode):    
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "TavilySearch",
            "display_name": "Tavily Web Search",
            "description": "Performs a web search using the Tavily API.",
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {"name": "tavily_search", "path": "icons/tavily_search.svg", "alt": "tavilysearchicons"},
            "colors": ["blue-500", "cyan-600"],
            "inputs": [
                NodeInput(name="max_results", type="int", default=5, description="The maximum number of results to return."),
                NodeInput(name="search_depth", type="str", default="basic", choices=["basic", "advanced"], description="The depth of the search."),
                NodeInput(name="include_domains", type="str", description="A comma-separated list of domains to include in the search.", required=False, default=""),
                NodeInput(name="exclude_domains", type="str", description="A comma-separated list of domains to exclude from the search.", required=False, default=""),
                NodeInput(name="include_answer", type="bool", default=True, description="Whether to include a direct answer in the search results."),
                NodeInput(name="include_raw_content", type="bool", default=False, description="Whether to include the raw content of the web pages in the search results."),
                NodeInput(name="include_images", type="bool", default=False, description="Whether to include images in the search results."),
            ],
            "outputs": [
                NodeOutput(
                    name="search_tool",
                    displayName="Search Tool",
                    type="BaseTool",
                    description="A configured Tavily search tool ready for use with agents.",
                    direction= NodePosition.TOP,
                    is_connection=True
                )
            ],
            "properties": [
                NodeProperty(
                    name="search_type",
                    displayName= "Search Type",
                    type= NodePropertyType.SELECT,
                    default= "basic",
                    options= [{"label": "Basic Search", "value": "basic"}, {"label": "Advanced Search", "value": "advanced"}],
                    required= True,
                ),
                NodeProperty(
                    name="credential_id",
                    displayName= "Credential",
                    type= NodePropertyType.CREDENTIAL_SELECT,
                    placeholder= "Select Credential",
                    required= True,
                    serviceType="tavily_search",
                ),
                NodeProperty(
                    name="max_results",
                    displayName= "Max Results",
                    default= 5,
                    type= NodePropertyType.NUMBER,
                    min= 1,
                    max= 20,
                    required= False
                ),
                NodeProperty(
                    name="search_depth",
                    displayName= "Search Depth",
                    type= NodePropertyType.SELECT,
                    default= "basic",
                    options= [{"label": "Basic", "value": "basic"}, {"label": "Moderate", "value": "moderate"}, {"label": "Advanced", "value": "advanced"}],
                    required= True,
                ),
                NodeProperty(
                    name="include_answer",
                    displayName= "Include Answer",
                    type= NodePropertyType.CHECKBOX,
                    hint= "Include direct answers from Tavily"
                ),
                NodeProperty(
                    name="include_raw_content",
                    displayName= "Include Raw Content",
                    type= NodePropertyType.CHECKBOX,
                    hint= "Include raw HTML content from pages"
                ),
                NodeProperty(
                    name="include_images",
                    displayName= "Include Images",
                    type= NodePropertyType.CHECKBOX,
                    hint= "Include image URLs in search results"
                ),
            ]
        }
    
    def get_required_packages(self) -> List[str]:
        """
        DYNAMIC METHOD: Bu node'un ihtiyaç duyduğu Python packages'ini döndür.
        
        Bu method dynamic export sisteminin çalışması için kritik!
        Yeni node eklendiğinde bu method tanımlanmalı.
        """
        return [
            "langchain-tavily>=0.2.0",  # Tavily LangChain integration
            "tavily-python>=0.3.0",     # Tavily Python SDK
            "httpx>=0.25.0",            # HTTP client for API calls
            "pydantic>=2.5.0"           # Data validation
        ]
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Create Tavily search tool with agent-optimized formatting.

        Following the RetrieverProvider pattern for consistent tool creation.
        """
        logger.info("\nTAVILY SEARCH SETUP")

        try:
            # Get API key from user configuration (database/UI) or kwargs
            api_key = None
            credential_id = kwargs.get("credential_id") or self.user_data.get("credential_id")
            if credential_id:
                cred = self.get_credential(credential_id)
                if cred and cred.get('secret'):
                    api_key = cred.get('secret').get('api_key')
                        
            if not api_key:
                api_key = os.getenv("TAVILY_API_KEY")
            
            logger.info(f"   API Key: {'Found' if api_key else 'Missing'}")
            if api_key:
                logger.info(f"   Source: {'User Config' if credential_id else 'Environment'}")
            
            if not api_key:
                raise ValueError(
                    "Tavily API key is required. Please provide it in the node configuration "
                    "or set TAVILY_API_KEY environment variable."
                )

            # 2. Get all other parameters from kwargs or user data with defaults.
            max_results_val = kwargs.get("max_results")
            if max_results_val is None:
                max_results_val = self.user_data.get("max_results", 5)
            max_results = int(max_results_val)
            
            search_depth = kwargs.get("search_depth") or self.user_data.get("search_depth", "basic")
            
            include_answer_val = kwargs.get("include_answer")
            if include_answer_val is None:
                include_answer_val = self.user_data.get("include_answer", True)
            if isinstance(include_answer_val, str):
                include_answer = include_answer_val.lower() in ("true", "1", "yes")
            else:
                include_answer = bool(include_answer_val)
                
            include_raw_content_val = kwargs.get("include_raw_content")
            if include_raw_content_val is None:
                include_raw_content_val = self.user_data.get("include_raw_content", False)
            if isinstance(include_raw_content_val, str):
                include_raw_content = include_raw_content_val.lower() in ("true", "1", "yes")
            else:
                include_raw_content = bool(include_raw_content_val)
                
            include_images_val = kwargs.get("include_images")
            if include_images_val is None:
                include_images_val = self.user_data.get("include_images", False)
            if isinstance(include_images_val, str):
                include_images = include_images_val.lower() in ("true", "1", "yes")
            else:
                include_images = bool(include_images_val)

            # 3. Safely parse domain lists.
            include_domains_str = kwargs.get("include_domains") or self.user_data.get("include_domains", "")
            exclude_domains_str = kwargs.get("exclude_domains") or self.user_data.get("exclude_domains", "")
            
            if isinstance(include_domains_str, list):
                include_domains = [str(d).strip() for d in include_domains_str if str(d).strip()]
            else:
                include_domains = [d.strip() for d in str(include_domains_str).split(",") if d.strip()]
                
            if isinstance(exclude_domains_str, list):
                exclude_domains = [str(d).strip() for d in exclude_domains_str if str(d).strip()]
            else:
                exclude_domains = [d.strip() for d in str(exclude_domains_str).split(",") if d.strip()]

            # 4. Build search configuration
            search_config = {
                "max_results": max_results,
                "search_depth": search_depth,
                "include_answer": include_answer,
                "include_raw_content": include_raw_content,
                "include_images": include_images,
                "include_domains": include_domains,
                "exclude_domains": exclude_domains
            }

            # 5. Create Tavily search instance
            tavily_search = self._create_tavily_search(api_key, search_config)

            # 6. Test the API connection
            try:
                test_result = tavily_search.run("test query")
                logger.info(f"   API Test: Success ({len(str(test_result))} chars)")
            except Exception as test_error:
                logger.error(f"   API Test: Failed ({str(test_error)[:50]}...)")

            # 7. Create agent-ready tool
            search_tool = self._create_search_tool(tavily_search, search_config)

            logger.info(f"   Tool Created: {search_tool.name} | Max Results: {max_results} | Depth: {search_depth}")

            return {
                "taviliy_web_search": {"tool": search_tool}
            }

        except Exception as e:
            error_msg = f"TavilySearchNode execution failed: {str(e)}"
            logger.error(f"{error_msg}")
            raise ValueError(error_msg) from e

    def _create_tavily_search(self, api_key: str, search_config: Dict[str, Any]) -> TavilySearch:
        """Create Tavily search instance with configuration."""
        try:
            # Build tool parameters
            tool_params = {
                "tavily_api_key": api_key,
                "max_results": search_config["max_results"],
                "search_depth": search_config["search_depth"],
                "include_answer": search_config["include_answer"],
                "include_raw_content": search_config["include_raw_content"],
                "include_images": search_config["include_images"],
            }
            
            # Only add domain filters if they contain actual domains
            if search_config["include_domains"]:
                tool_params["include_domains"] = search_config["include_domains"]
            if search_config["exclude_domains"]:
                tool_params["exclude_domains"] = search_config["exclude_domains"]
                
            return TavilySearch(**tool_params)

        except Exception as e:
            raise ValueError(f"Failed to create Tavily search instance: {str(e)}") from e

    def _create_search_tool(self, tavily_search: TavilySearch, search_config: Dict[str, Any]) -> Tool:
        """Create LangChain Tool with agent-optimized formatting."""

        def tavily_web_search(query: str) -> str:
            """Web search function that agents will call."""
            try:
                logger.info(f"Agent performing web search for: {query}")

                # Perform search using Tavily
                raw_results = tavily_search.run(query)

                # Handle empty results
                if not raw_results or (isinstance(raw_results, str) and not raw_results.strip()):
                    return f"""WEB SEARCH RESULTS - Tavily
Query: No web results found for '{query}'.

SEARCH SUMMARY:
- Search completed but no relevant web pages were found
- You may try using different search terms or be more specific
- Search Engine: Tavily
- Search Depth: {search_config['search_depth']}
- Max Results: {search_config['max_results']}"""

                # Format results for agent consumption
                result_parts = [
                    "WEB SEARCH RESULTS - Tavily",
                    f"Query: {query}",
                    f"Search Depth: {search_config['search_depth']}",
                    f"Max Results: {search_config['max_results']}",
                    ""
                ]

                # Parse and format results
                if isinstance(raw_results, str):
                    # If results are already formatted as string
                    result_parts.extend([
                        "SEARCH RESULTS:",
                        raw_results,
                        "",
                    ])
                elif isinstance(raw_results, list):
                    # If results are in list format
                    result_parts.append(f"Total results found: {len(raw_results)}")
                    result_parts.append("")
                    
                    for i, result in enumerate(raw_results[:5], 1):  # Limit to 5 results
                        if isinstance(result, dict):
                            title = result.get('title', 'No title')
                            url = result.get('url', 'No URL')
                            content = result.get('content', result.get('snippet', 'No content'))
                            
                            # Smart content truncation
                            if len(content) > 400:
                                content = content[:400] + "..."
                                
                            result_parts.extend([
                                f"=== RESULT {i} ===",
                                f"Title: {title}",
                                f"URL: {url}",
                                f"Content: {content}",
                                "",
                                "---",
                                ""
                            ])
                        else:
                            result_parts.extend([
                                f"=== RESULT {i} ===",
                                str(result),
                                "",
                                "---",
                                ""
                            ])
                else:
                    # Handle other formats
                    result_parts.extend([
                        "SEARCH RESULTS:",
                        str(raw_results),
                        "",
                    ])

                result_parts.extend([
                    "",
                    "SEARCH SUMMARY:",
                    f"- These web search results are the most relevant for the query '{query}'",
                    f"- Search Engine: Tavily API",
                    f"- Search Depth: {search_config['search_depth']} (higher depth = more comprehensive results)",
                    f"- Domain Filtering: {'Yes' if search_config['include_domains'] or search_config['exclude_domains'] else 'None'}",
                    f"- Results are ranked by relevance and recency"
                ])

                return "\n".join(result_parts)

            except Exception as e:
                error_msg = str(e)
                return f"""WEB SEARCH RESULTS - Tavily
Query: A technical issue occurred while searching for '{query}'.

ERROR DETAILS:
{error_msg}

SEARCH SUMMARY:
- Web search could not be completed due to technical issues
- Search Engine: Tavily API
- Please try again with different search terms"""

        # Create tool with descriptive name and description
        return Tool(
            name="tavily_web_search",
            description="Search the web for current information, news, and real-time data using Tavily's advanced search API. Use this tool when you need up-to-date information that may not be in your training data.",
            func=tavily_web_search
        )

# Alias for frontend compatibility
TavilyNode = TavilySearchNode
