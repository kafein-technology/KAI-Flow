import React from "react";
import type { ReactElement } from "react";
import {
  Box,
  Rocket,
  Clock,
  Flag,
  GitCompare,
  GitBranch,
  Bot,
  Cohere,
  Openai,
  Database,
  MessageCircle,
  FileText,
  FileInput,
  Scissors,
  Type,
  PostgresqlVectorstore,
  TavilyNonbrand,
  Pickaxe,
  Globe,
  Webhook,
  BookOpen,
  FileStack,
  Search,
  Code,
  Condition,
} from "~/icons/index";

interface NodeType {
  id: string;
  type: string;
  name: string;
  display_name: string;
  data: any;
  info: string;
  colors?: string[];
}

interface DraggableNodeProps {
  nodeType: NodeType;
  icon?: string;
}

// Fixed icon size - all icons will fit within this container
const ICON_CONTAINER_SIZE = "w-8 h-8";

// Node type to icon color mapping (for sidebar)
const nodeIconColorMap: Record<string, string> = {
  // Flow Control
  Agent: "text-blue-400",
  StartNode: "text-green-400",
  start: "text-green-400",
  TimerStart: "text-yellow-400",
  EndNode: "text-white",
  ConditionalChain: "text-orange-400",
  RouterChain: "text-lime-400",

  // AI & Embedding
  CohereEmbeddings: "text-blue-500",
  OpenAIEmbedder: "text-violet-400",

  // Memory
  BufferMemory: "text-red-400",
  ConversationMemory: "text-rose-400",

  // Documents & Data
  TextDataLoader: "text-pink-400",
  DocumentLoader: "text-blue-400",
  ChunkSplitter: "text-pink-400",
  StringInputNode: "text-blue-400",
  PGVectorStore: "text-slate-400",
  VectorStoreOrchestrator: "text-slate-400",
  IntelligentVectorStore: "text-slate-400",

  // Web & APIs
  TavilySearch: "text-cyan-400",
  WebScraper: "text-blue-400",
  HttpRequest: "text-blue-400",
  WebhookTrigger: "text-emerald-400",
  RespondToWebhook: "text-emerald-400",

  // RAG & QA
  RetrievalQA: "text-purple-400",
  Reranker: "text-blue-500",
  CohereRerankerProvider: "text-blue-500",
  RetrieverProvider: "text-indigo-400",
  RetrieverNode: "text-sky-400",
  Retriever: "text-indigo-400",
  OpenAIEmbeddingsProvider: "text-violet-400",

  // Processing Nodes
  CodeNode: "text-white",
  ConditionNode: "text-white",

  // Generic
  GenericNode: "text-blue-400",
};

// Node type to icon component mapping
const nodeIconMap: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  // Flow Control
  StartNode: Rocket,
  start: Rocket,
  TimerStart: Clock,
  EndNode: Flag,
  ConditionalChain: GitCompare,
  RouterChain: GitBranch,

  // AI & Embedding
  Agent: Bot,
  CohereEmbeddings: Cohere,
  OpenAIEmbedder: Openai,

  // Memory
  BufferMemory: Database,
  ConversationMemory: MessageCircle,

  // Documents & Data
  TextDataLoader: FileText,
  DocumentLoader: FileInput,
  ChunkSplitter: Scissors,
  StringInputNode: Type,
  PGVectorStore: PostgresqlVectorstore,
  VectorStoreOrchestrator: PostgresqlVectorstore,
  IntelligentVectorStore: PostgresqlVectorstore,

  // Web & APIs
  TavilySearch: TavilyNonbrand,
  WebScraper: Pickaxe,
  HttpRequest: Globe,
  WebhookTrigger: Webhook,
  RespondToWebhook: Webhook,

  // RAG & QA
  RetrievalQA: BookOpen,
  Reranker: Cohere,
  CohereRerankerProvider: Cohere,
  RetrieverProvider: FileStack,
  RetrieverNode: Search,
  OpenAIEmbeddingsProvider: Openai,
  Retriever: FileStack,
  Condition: Condition,

  // LLM Providers
  OpenAICompatibleNode: Openai,
  OpenAIChat: Openai,
  OpenAIEmbeddings: Openai,

  // Processing Nodes
  CodeNode: Code,
  ConditionNode: Condition,

  // Generic
  GenericNode: Box,
};

// Static icons (inline SVG that can't be imported)
const staticIcons: Record<string, ReactElement> = {
  RedisCache: (
    <svg
      width="25px"
      height="25px"
      viewBox="0 -18 256 256"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M245.97 168.943c-13.662 7.121-84.434 36.22-99.501 44.075-15.067 7.856-23.437 7.78-35.34 2.09-11.902-5.69-87.216-36.112-100.783-42.597C3.566 169.271 0 166.535 0 163.951v-25.876s98.05-21.345 113.879-27.024c15.828-5.679 21.32-5.884 34.79-.95 13.472 4.936 94.018 19.468 107.331 24.344l-.006 25.51c.002 2.558-3.07 5.364-10.024 8.988"
        fill="#ef4444"
      />
      <path
        d="M185.295 35.998l34.836 13.766-34.806 13.753-.03-27.52"
        fill="#dc2626"
      />
      <path
        d="M146.755 51.243l38.54-15.245.03 27.519-3.779 1.478-34.791-13.752"
        fill="#f87171"
      />
    </svg>
  ),
};

/**
 * Gets the icon element for a node type.
 */
function getNodeIcon(nodeType: string, colors?: string[]): ReactElement | null {
  // Check for static icons first (inline SVGs)
  if (staticIcons[nodeType]) {
    return staticIcons[nodeType];
  }

  // Check for component-based icons
  const IconComponent = nodeIconMap[nodeType];
  if (IconComponent) {
    // Use backend color if available, otherwise use predefined mapping
    let colorClass = "";
    if (colors && colors[0]) {
      // Extract text color from gradient color (e.g., "from-blue-600" -> "text-blue-600")
      const colorPart = colors[0].replace("from-", "text-");
      colorClass = colorPart;
    } else {
      colorClass = nodeIconColorMap[nodeType] || "";
    }
    return <IconComponent className={`w-6 h-6 ${colorClass}`} />;
  }

  // Fallback to Box icon for unknown node types
  return <Box className="w-6 h-6 text-gray-400" />;
}

function DraggableNode({ nodeType, icon }: DraggableNodeProps) {
  const onDragStart = (event: React.DragEvent<HTMLDivElement>) => {
    event.stopPropagation();
    event.dataTransfer.setData(
      "application/reactflow",
      JSON.stringify(nodeType)
    );
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <div
      draggable
      onDragStart={onDragStart}
      className="text-gray-100 flex items-center gap-2 p-3 hover:bg-gray-700/50 transition-all select-none cursor-grab rounded-2xl border border-transparent hover:border-gray-600"
    >
      <div className={`flex items-center justify-center ${ICON_CONTAINER_SIZE} m-2 shrink-0 text-gray-300`}>
        {getNodeIcon(nodeType.type, nodeType.colors) || <></>}
      </div>
      <div className="flex flex-col gap-2">
        <div>
          <h2 className="text-md font-medium text-gray-200">
            {nodeType.display_name ||
              nodeType.data?.displayName ||
              nodeType.name}
          </h2>
        </div>
        <div>
          <p className="text-xs text-gray-400">{nodeType.info}</p>
        </div>
      </div>
    </div>
  );
}

export default DraggableNode;