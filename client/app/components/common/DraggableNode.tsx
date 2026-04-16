import React from "react";
import type { ReactElement } from "react";
import { Box, ShieldAlert } from "lucide-react";
import { getNodeTypeIconPath, hasNodeTypeIcon } from "~/lib/iconUtils";

interface NodeType {
  id: string;
  type: string;
  name: string;
  display_name: string;
  data: any;
  info: string;
}

interface DraggableNodeProps {
  nodeType: NodeType;
  icon?: string;
}

// Icon size is controlled by the container, not individual img elements
// Fixed icon size - all icons will fit within this container
const ICON_CONTAINER_SIZE = "w-8 h-8";

// Static icons that don't use file paths (inline SVG or Lucide components)
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
  GenericNode: <Box className="w-6 h-6 text-blue-400" />,
  LLMRedTeam: <ShieldAlert className="w-6 h-6 text-red-500" />,
};

// Alt text mapping for accessibility
const iconAltText: Record<string, string> = {
  StartNode: "start",
  start: "start",
  TimerStart: "timer",
  EndNode: "end",
  ConditionalChain: "conditional",
  RouterChain: "router",
  Agent: "agent",
  CohereEmbeddings: "cohere",
  OpenAIEmbedder: "openai",
  BufferMemory: "buffer-memory",
  ConversationMemory: "conversation-memory",
  TextDataLoader: "text-loader",
  DocumentLoader: "document-loader",
  ChunkSplitter: "chunk-splitter",
  StringInputNode: "string-input",
  PGVectorStore: "pg-vectorstore",
  VectorStoreOrchestrator: "vectorstore-orchestrator",
  IntelligentVectorStore: "intelligent-vectorstore",
  TavilySearch: "tavily-search",
  WebScraper: "web-scraper",
  HttpRequest: "http-request",
  WebhookTrigger: "webhook",
  RespondToWebhook: "respond-to-webhook",
  RetrievalQA: "retrieval-qa",
  Reranker: "reranker",
  CohereRerankerProvider: "cohere-reranker",
  RetrieverProvider: "retriever-provider",
  RetrieverNode: "retriever-node",
  OpenAIEmbeddingsProvider: "openai-embeddings-provider",
  OpenAICompatibleNode: "openai-compatible",
  OpenAIChat: "openai-chat",
  OpenAIEmbeddings: "openai-embeddings",
  CodeNode: "code-node",
  ConditionNode: "condition-node",
  JsonParserNode: "parser",
};

/**
 * Gets the icon element for a node type.
 * Uses lazy evaluation to ensure BASE_PATH is read at render time.
 */
function getNodeIcon(nodeType: string): ReactElement | null {
  // Check for static icons first (inline SVGs or Lucide components)
  if (staticIcons[nodeType]) {
    return staticIcons[nodeType];
  }

  // Get icon path using centralized utility (evaluates BASE_PATH at call time)
  const iconPath = getNodeTypeIconPath(nodeType);
  if (iconPath) {
    return <img src={iconPath} alt={iconAltText[nodeType] || nodeType} />;
  }

  return null;
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
      <div className={`flex items-center justify-center ${ICON_CONTAINER_SIZE} m-2 shrink-0 [&>img]:max-w-full [&>img]:max-h-full [&>img]:object-contain`}>
        {getNodeIcon(nodeType.type) || <></>}
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