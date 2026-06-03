import type { NodeMetadata } from '~/types/api';

// Define common node chains and their recommendations
export interface NodeChain {
  trigger: string;
  recommendations: string[];
  description: string;
  category: string;
}

// Common node chains for different workflows
export const NODE_CHAINS: NodeChain[] = [
  // Document Processing Chain
  {
    trigger: 'WebScraper',
    recommendations: ['ChunkSplitter', 'OpenAIEmbeddingsProvider', 'VectorStoreOrchestrator'],
    description: 'Process web content for vector storage',
    category: 'Document Processing'
  },
  {
    trigger: 'DocumentLoader',
    recommendations: ['ChunkSplitter', 'OpenAIEmbeddingsProvider', 'VectorStoreOrchestrator'],
    description: 'Process documents for vector storage',
    category: 'Document Processing'
  },
  {
    trigger: 'TextDataLoader',
    recommendations: ['ChunkSplitter', 'OpenAIEmbeddingsProvider', 'VectorStoreOrchestrator'],
    description: 'Process text data for vector storage',
    category: 'Document Processing'
  },
  
  // Text Splitting Chain
  {
    trigger: 'ChunkSplitter',
    recommendations: ['OpenAIEmbeddingsProvider', 'CohereEmbeddings', 'VectorStoreOrchestrator'],
    description: 'Embed split text for storage',
    category: 'Embedding'
  },
  
  // Embedding Chain
  {
    trigger: 'OpenAIEmbeddingsProvider',
    recommendations: ['VectorStoreOrchestrator', 'RetrieverProvider', 'Agent'],
    description: 'Store embeddings in vector database',
    category: 'Vector Storage'
  },
  {
    trigger: 'CohereEmbeddings',
    recommendations: ['VectorStoreOrchestrator', 'RetrieverProvider', 'Agent'],
    description: 'Store embeddings in vector database',
    category: 'Vector Storage'
  },
  {
    trigger: 'OpenAIEmbedder',
    recommendations: ['VectorStoreOrchestrator', 'RetrieverProvider', 'Agent'],
    description: 'Store embeddings in vector database',
    category: 'Vector Storage'
  },
  
  // Vector Storage Chain
  {
    trigger: 'VectorStoreOrchestrator',
    recommendations: ['RetrieverProvider', 'Agent', 'OpenAIChat'],
    description: 'Use stored vectors for retrieval',
    category: 'Retrieval'
  },
  
  // Retrieval Chain
  {
    trigger: 'RetrieverProvider',
    recommendations: ['Agent', 'OpenAIChat', 'CohereRerankerProvider'],
    description: 'Process retrieved content',
    category: 'Processing'
  },
  
  // Reranking Chain
  {
    trigger: 'CohereRerankerProvider',
    recommendations: ['Agent', 'OpenAIChat', 'EndNode'],
    description: 'Process reranked results',
    category: 'Processing'
  },
  
  // LLM Chain
  {
    trigger: 'OpenAIChat',
    recommendations: ['EndNode', 'BufferMemory'],
    description: 'Complete the conversation flow',
    category: 'Memory & Output'
  },
  
  // Memory Chain
  {
    trigger: 'BufferMemory',
    recommendations: ['OpenAIChat', 'Agent', 'EndNode'],
    description: 'Continue with memory-enhanced processing',
    category: 'Processing'
  },
  
  // Agent Chain
  {
    trigger: 'Agent',
    recommendations: ['EndNode', 'BufferMemory'],
    description: 'Complete agent workflow',
    category: 'Memory & Output'
  },
  
  // Chain Processing
  {
    trigger: 'RetrievalQA',
    recommendations: ['EndNode', 'BufferMemory'],
    description: 'Complete QA workflow',
    category: 'Memory & Output'
  },
  {
    trigger: 'ConditionalChain',
    recommendations: ['EndNode', 'OpenAIChat', 'Agent'],
    description: 'Complete conditional workflow',
    category: 'Processing'
  },
  {
    trigger: 'RouterChain',
    recommendations: ['EndNode', 'OpenAIChat', 'Agent'],
    description: 'Complete routing workflow',
    category: 'Processing'
  },
  
  // Trigger Chain
  {
    trigger: 'TimerStartNode',
    recommendations: ['WebScraper', 'DocumentLoader', 'OpenAIChat'],
    description: 'Start automated workflow',
    category: 'Automation'
  },
  {
    trigger: 'WebhookTrigger',
    recommendations: ['WebScraper', 'DocumentLoader', 'OpenAIChat'],
    description: 'Start webhook-triggered workflow',
    category: 'Automation'
  },
  
  // Cache Chain
  {
    trigger: 'BufferMemory',
    recommendations: ['OpenAIChat', 'Agent', 'EndNode'],
    description: 'Use memory-enhanced results',
    category: 'Processing'
  },
  
  // HTTP Client Chain
  {
    trigger: 'HttpRequest',
    recommendations: ['OpenAIChat', 'Agent', 'EndNode'],
    description: 'Process HTTP response',
    category: 'Processing'
  },
  
  // Search Chain
  {
    trigger: 'TavilySearch',
    recommendations: ['ChunkSplitter', 'OpenAIEmbeddingsProvider', 'OpenAIChat'],
    description: 'Process search results',
    category: 'Processing'
  },
  
  // Intelligent Vector Store Chain
  {
    trigger: 'IntelligentVectorStore',
    recommendations: ['RetrieverNode', 'RetrievalQA', 'Agent'],
    description: 'Use intelligent vector store for retrieval',
    category: 'Retrieval'
  },
  
  // OpenAI Embeddings Provider Chain
  {
    trigger: 'OpenAIEmbeddingsProvider',
    recommendations: ['PGVectorStore', 'VectorStoreOrchestrator', 'RetrieverNode'],
    description: 'Store provider embeddings in vector database',
    category: 'Vector Storage'
  }
];

export class SmartSuggestionsService {
  /**
   * Get recommendations based on the last added node
   */
  static getRecommendations(lastNodeType: string, availableNodes: NodeMetadata[]): NodeMetadata[] {
    // Find the chain that matches the last node type
    const chain = NODE_CHAINS.find(c => c.trigger === lastNodeType);
    
    if (!chain) {
      return [];
    }
    
    // Filter available nodes to only include recommended ones
    const recommendedNodes = availableNodes.filter(node => 
      chain.recommendations.includes(node.name)
    );
    
    return recommendedNodes;
  }
  
  /**
   * Get all available chains for display
   */
  static getAvailableChains(): NodeChain[] {
    return NODE_CHAINS;
  }
  
  /**
   * Get chain description for a specific node type
   */
  static getChainDescription(nodeType: string): string | null {
    const chain = NODE_CHAINS.find(c => c.trigger === nodeType);
    return chain?.description || null;
  }
  
  /**
   * Get chain category for a specific node type
   */
  static getChainCategory(nodeType: string): string | null {
    const chain = NODE_CHAINS.find(c => c.trigger === nodeType);
    return chain?.category || null;
  }
  
  /**
   * Check if a node type has recommendations
   */
  static hasRecommendations(nodeType: string): boolean {
    return NODE_CHAINS.some(c => c.trigger === nodeType);
  }
} 