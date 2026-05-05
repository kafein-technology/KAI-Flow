"""
Cohere Reranker Provider Node
==============================

This module provides a simplified provider node that creates and configures
Cohere reranker compressor instances for use by other nodes in the workflow.
Unlike the full RerankerNode, this provider focuses solely on configuration
without processing documents or providing analytics.

The provider follows the KAI-Flow ProviderNode pattern, creating LangChain
objects from user inputs that can be consumed by other nodes in the workflow.

Key Features:
- Minimal configuration surface for ease of use
- Direct integration with LangChain CohereRerank
- Secure API key handling with environment variable support
- Model selection with validation
- Configurable top_n and max_chunks_per_doc parameters
"""

from typing import Dict, Any
try:
    from langchain_cohere import CohereRerank
except ImportError:
    # Fallback to legacy import if langchain_cohere is not working
    from langchain_cohere import CohereRerank
from langchain_core.runnables import Runnable

from ..base import ProviderNode, NodeType, NodeInput, NodeOutput, NodeProperty, NodePosition, NodePropertyType
import os


class CohereRerankerNode(ProviderNode):
    """
    Provider Node for Cohere Reranker Configuration
    
    This node creates configured Cohere reranker instances that can be used
    by other nodes in the workflow. It focuses on configuration only, without
    document processing or analytics features.
    
    Usage Pattern:
    --------------
    The provider node is used at the beginning of workflows to create a shared
    reranker instance that can be passed to multiple downstream nodes:
    
    ```python
    # In workflow configuration
    reranker_provider = CohereRerankerNode()
    reranker_compressor = reranker_provider.execute(
        cohere_api_key="your-api-key",
        model="rerank-english-v3.0",
        top_n=5,
        max_chunks_per_doc=10
    )
    
    # The reranker compressor can then be used to create ContextualCompressionRetriever instances
    # with specific base retrievers
    contextual_retriever = ContextualCompressionRetriever(
        base_compressor=reranker_compressor,
        base_retriever=your_base_retriever
    )
    ```
    
    Configuration Philosophy:
    -------------------------
    - Minimal parameters: Only what's needed to configure the reranker
    - Secure defaults: API key can be provided via environment variables
    - Model validation: Only supported models are allowed
    - Clear error messages: Helpful feedback for configuration issues
    
    Integration Points:
    -------------------
    This provider can be connected to:
    - Retrieval chain nodes
    - Agent nodes that need reranking capabilities
    - Any node requiring a configured reranker instance
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "CohereRerankerProvider",
            "display_name": "Cohere Reranker Provider",
            "description": (
                "Provider node that creates configured Cohere reranker instances. "
                "Use this node to create a shared reranker for your workflow."
            ),
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {"name": "cohere", "path": "icons/cohere.svg", "alt": "coherererankericons"},
            "colors": ["orange-500", "red-600"],
            "inputs": [
                NodeInput(
                    name="model",
                    type="str",
                    description="Cohere reranking model to use",
                    default="rerank-english-v3.0",
                    required=False,
                ),
                NodeInput(
                    name="top_n",
                    type="int",
                    description="Number of top results to return",
                ),
                # Note: max_chunks_per_doc is not supported by LangChain CohereRerank
                # This parameter has been removed to fix validation error
            ],
            "outputs": [
                NodeOutput(
                    name="reranker",
                    displayName="Reranker Model",
                    type="CohereRerank",
                    description="Configured Cohere reranker compressor ready for use",
                    direction=NodePosition.TOP,
                    is_connection=True
                )
            ],
            "properties": [
                NodeProperty(
                    name="credential_id",
                    displayName="Select Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    placeholder="Select Credential",
                    required=True,
                    serviceType="cohere",
                ),
                NodeProperty(
                    name="model",
                    displayName="Model",
                    type=NodePropertyType.SELECT,
                    default="rerank-english-v3.0",
                    options=[
                        {"label": "Rerank English v3.0", "value": "rerank-english-v3.0"},
                        {"label": "Rerank Multilingual v3.0", "value": "rerank-multilingual-v3.0"},
                        {"label": "Rerank English v2.0", "value": "rerank-english-v2.0"},
                        {"label": "Rerank Multilingual v2.0", "value": "rerank-multilingual-v2.0"}
                    ],
                    required=True
                ),
                NodeProperty(
                    name="top_n",
                    displayName="Top N",
                    type=NodePropertyType.RANGE,
                    default=10,
                    min=1,
                    max=20,
                    minLabel="1",
                    maxLabel="20",
                    required=True
                ),
                NodeProperty(
                    name="max_chunks_per_doc",
                    displayName="Max Chunks Per Doc",
                    type=NodePropertyType.RANGE,
                    color="green-500",
                    default=10,
                    min=1,
                    max=50,
                    minLabel="1",
                    maxLabel="50",
                    required=True
                ),
            ]
        }
    
    def get_required_packages(self) -> list[str]:
        """
        DYNAMIC METHOD: CohereRerankerNode'un ihtiyaç duyduğu Python packages'ini döndür.
        
        Bu method dynamic export sisteminin çalışması için kritik!
        Cohere reranker için gereken API ve LangChain dependencies.
        """
        return [
            "langchain-cohere>=0.4.0",  # Cohere LangChain integration
            "cohere==5.12.0",           # Cohere Python SDK (pinned version)
            "httpx>=0.25.0",            # HTTP client for API calls
            "pydantic>=2.5.0",          # Data validation
            "numpy>=1.24.0"             # Numerical computations for scoring
        ]
    
    def execute(self, **kwargs) -> Runnable:
        """
        Create and configure a Cohere reranker instance.
        
        This method focuses solely on configuration, creating a properly
        configured Cohere reranker instance without processing any documents.
        
        Args:
            **kwargs: Configuration parameters from node inputs
            
        Returns:
            CohereRerank: Configured reranker compressor instance
            
        Raises:
            ValueError: If API key is missing or model is unsupported
        """
        # Extract configuration from user data or kwargs
        cohere_api_key = None
        model = kwargs.get("model") or self.user_data.get("model", "rerank-english-v3.0")
        top_n = kwargs.get("top_n") or self.user_data.get("top_n", 5)
        # Note: max_chunks_per_doc removed as it's not supported by LangChain CohereRerank

        # If credential_id is present, fetch the actual API key
        credential_id = self.user_data.get("credential_id")
        cohere_api_key = self.get_credential(credential_id).get('secret').get('api_key')
        
        # Validate API key
        if not cohere_api_key:
            # Try to get from environment variable
            cohere_api_key = os.getenv("COHERE_API_KEY")
            if not cohere_api_key:
                raise ValueError(
                    "Cohere API key is required. Please provide it in the node configuration "
                    "or set the COHERE_API_KEY environment variable."
                )
        
        # Validate model
        supported_models = [
            "rerank-english-v3.0",
            "rerank-multilingual-v3.0", 
            "rerank-english-v2.0",
            "rerank-multilingual-v2.0"
        ]
        if model not in supported_models:
            raise ValueError(f"Unsupported reranking model: {model}. Supported models: {supported_models}")
        
        # Validate top_n
        if not isinstance(top_n, int) or top_n < 1 or top_n > 50:
            raise ValueError("top_n must be an integer between 1 and 50")
        
        # Note: max_chunks_per_doc validation removed as parameter is not supported
        
        # Create and configure CohereRerank compressor
        # This can be used later to create ContextualCompressionRetriever instances
        # with specific base retrievers
        # Note: max_chunks_per_doc parameter removed as it's not supported by LangChain CohereRerank
        compressor = CohereRerank(
            model=model,
            cohere_api_key=cohere_api_key,
            top_n=top_n
        )
        
        return compressor


# Export for node registry
__all__ = ["CohereRerankerNode"]