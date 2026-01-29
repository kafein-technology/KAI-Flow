import React, {
  useState,
  useRef,
  useCallback,
  useEffect,
  useMemo,
} from "react";
import { v4 as uuidv4 } from "uuid";
import {
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  type Connection,
} from "@xyflow/react";
import { useSnackbar } from "notistack";
import { useWorkflows } from "~/stores/workflows";
import { useNodes } from "~/stores/nodes";
import { useExecutionsStore } from "~/stores/executions";
import { useSmartSuggestions } from "~/stores/smartSuggestions";
import StartNode from "../node/StartNode";
import CustomEdge from "../common/CustomEdge";

import type {
  WorkflowData,
  WorkflowNode,
  WorkflowEdge,
  NodeMetadata,
  WebhookStreamEvent,
} from "~/types/api";

type NodeStatus = "success" | "failed" | "pending";

import { Loader } from "lucide-react";
import ChatComponent from "./ChatComponent";
import ChatHistorySidebar from "./ChatHistorySidebar";
import SidebarToggleButton from "./SidebarToggleButton";
import ErrorDisplayComponent from "./ErrorDisplayComponent";
import ReactFlowCanvas from "./ReactFlowCanvas";
import Navbar from "../common/Navbar";
import Sidebar from "../common/Sidebar";
import EndNode from "../node/EndNode";
import { useChatStore } from "../../stores/chat";
import UnsavedChangesModal from "../modals/UnsavedChangesModal";
import AutoSaveSettingsModal from "../modals/AutoSaveSettingsModal";
import FullscreenNodeModal from "../common/FullscreenNodeModal";
import { TutorialButton } from "../tutorial";
import { executeWorkflowStream } from "~/services/executionService";
import GenericNode from "../node";

// Import config components
import { config } from "../../lib/config";
import { GenericNodeForm } from "../node";

interface FlowCanvasProps {
  workflowId?: string;
}

// Helper function to create a stable JSON string with sorted keys for deep comparison
const stableStringify = (obj: unknown): string => {
  if (obj === null || obj === undefined) return JSON.stringify(obj);
  if (typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj)) {
    return '[' + obj.map(item => stableStringify(item)).join(',') + ']';
  }
  const sortedKeys = Object.keys(obj as Record<string, unknown>).sort();
  const parts = sortedKeys.map(key => {
    const value = (obj as Record<string, unknown>)[key];
    return JSON.stringify(key) + ':' + stableStringify(value);
  });
  return '{' + parts.join(',') + '}';
};

// Helper function to normalize flow data for comparison
// Strips out React Flow internal properties that don't represent actual user changes
const normalizeFlowDataForComparison = (flowData: WorkflowData | undefined): string => {
  if (!flowData) return stableStringify({ nodes: [], edges: [] });

  // Normalize nodes - only include properties that matter for saving
  const normalizedNodes = (flowData.nodes || []).map(node => ({
    id: node.id,
    type: node.type,
    position: {
      x: Math.round((node.position?.x || 0) * 1000) / 1000, // Round to avoid floating point issues
      y: Math.round((node.position?.y || 0) * 1000) / 1000,
    },
    data: node.data,
  }));

  // Normalize edges - only include properties that matter for saving
  const normalizedEdges = (flowData.edges || []).map(edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle || null,
    targetHandle: edge.targetHandle || null,
    type: edge.type || 'custom',
  }));

  // Sort for consistent comparison
  normalizedNodes.sort((a, b) => a.id.localeCompare(b.id));
  normalizedEdges.sort((a, b) => a.id.localeCompare(b.id));

  return stableStringify({ nodes: normalizedNodes, edges: normalizedEdges });
};


function FlowCanvas({ workflowId }: FlowCanvasProps) {
  const { enqueueSnackbar } = useSnackbar();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeEdges, setActiveEdges] = useState<string[]>([]);
  const [activeNodes, setActiveNodes] = useState<string[]>([]);
  const [nodeStatus, setNodeStatus] = useState<
    Record<string, "success" | "failed" | "pending">
  >({});
  const [edgeStatus, setEdgeStatus] = useState<
    Record<string, "success" | "failed" | "pending">
  >({});

  // Create node config components and base node types directly from nodes
  const nodeConfigComponents = useMemo(
    () =>
      nodes.reduce((acc, node) => {
        const nodeType = node.type as string;
        if (!acc[nodeType]) {
          if (nodeType === "StartNode" || nodeType === "EndNode") {
            acc[nodeType] = null;
          } else {
            acc[nodeType] = GenericNodeForm as React.ComponentType<any>;
          }
        }
        return acc;
      }, {} as Record<string, React.ComponentType<any> | null>),
    [nodes]
  );
  // Listen for chat execution events to update node status
  useChatExecutionListener(
    nodes,
    setNodeStatus,
    edges,
    setEdgeStatus,
    setActiveEdges,
    setActiveNodes
  );

  // Auto-save state
  const [autoSaveEnabled, setAutoSaveEnabled] = useState(true);
  const [autoSaveInterval, setAutoSaveInterval] = useState(30000); // 30 seconds
  const [lastAutoSave, setLastAutoSave] = useState<Date | null>(null);
  const [autoSaveStatus, setAutoSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");

  // Unsaved changes modal ref
  const unsavedChangesModalRef = useRef<HTMLDialogElement>(null);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(
    null
  );

  // Auto-save settings modal ref
  const autoSaveSettingsModalRef = useRef<HTMLDialogElement>(null);

  // Fullscreen node modal state
  const [fullscreenModal, setFullscreenModal] = useState<{
    isOpen: boolean;
    nodeData?: any;
    nodeMetadata?: any;
    configComponent?: React.ComponentType<any>;
  }>({
    isOpen: false,
  });

  const {
    currentWorkflow,
    setCurrentWorkflow,
    isLoading,
    error,
    hasUnsavedChanges,
    setHasUnsavedChanges,
    fetchWorkflows,
    updateWorkflow,
    createWorkflow,
    fetchWorkflow,
    deleteWorkflow,
    updateWorkflowStatus,
    updateWorkflowVisibility,
  } = useWorkflows();

  const { nodes: availableNodes } = useNodes();

  // Smart suggestions integration
  const { setLastAddedNode, updateRecommendations } = useSmartSuggestions();

  // Execution store integration
  const {
    executeWorkflow,
    getCurrentExecutionForWorkflow,
    setCurrentExecutionForWorkflow,
    loading: executionLoading,
    error: executionError,
    clearError: clearExecutionError,
  } = useExecutionsStore();

  // Get current execution for the current workflow
  const currentExecution = currentWorkflow?.id
    ? getCurrentExecutionForWorkflow(currentWorkflow.id)
    : null;

  // Listen for webhook execution events to update node status
  // Must be called after currentWorkflow and setCurrentExecutionForWorkflow are defined
  useWebhookExecutionListener(
    nodes,
    setNodeStatus,
    edges,
    setEdgeStatus,
    setActiveEdges,
    setActiveNodes,
    workflowId,
    currentWorkflow?.id,
    setCurrentExecutionForWorkflow
  );

  const [workflowName, setWorkflowName] = useState(
    currentWorkflow?.name || "isimsiz dosya"
  );

  const {
    chats,
    activeChatflowId,
    setActiveChatflowId,
    startLLMChat,
    sendLLMMessage,
    loading: chatLoading,
    thinking: chatThinking, // thinking state'ini al
    error: chatError,
    addMessage,
    fetchChatMessages,
    fetchWorkflowChats,
    clearAllChats,
  } = useChatStore();

  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [chatHistoryOpen, setChatHistoryOpen] = useState(false);

  // Enhanced error handling state
  const [detailedExecutionError, setDetailedExecutionError] = useState<{
    message: string;
    type: string;
    nodeId?: string;
    nodeType?: string;
    timestamp: string;
    stackTrace?: string;
  } | null>(null);
  const [errorNodeId, setErrorNodeId] = useState<string | null>(null);

  // Error handling functions
  const handleErrorDismiss = useCallback(() => {
    setDetailedExecutionError(null);
    setErrorNodeId(null);

    // Reset all failed statuses
    setNodeStatus((s) => {
      const newStatus = { ...s };
      Object.keys(newStatus).forEach((key) => {
        if (newStatus[key] === "failed") {
          delete newStatus[key];
        }
      });
      return newStatus;
    });

    setEdgeStatus((s) => {
      const newStatus = { ...s };
      Object.keys(newStatus).forEach((key) => {
        if (newStatus[key] === "failed") {
          delete newStatus[key];
        }
      });
      return newStatus;
    });
  }, []);

  useEffect(() => {
    if (workflowId) {
      // Tekil workflow'u doğrudan fetch et
      fetchWorkflow(workflowId).catch(() => {
        setCurrentWorkflow(null);
        clearAllChats(); // Clear chats when workflow loading fails
        enqueueSnackbar("Workflow bulunamadı veya yüklenemedi.", {
          variant: "error",
        });
      });
    } else {
      // Yeni workflow: state'i sıfırla
      setCurrentWorkflow(null);
      setNodes([]);
      setEdges([]);
      setWorkflowName("isimsiz dosya");
      clearAllChats(); // Clear chats for new workflow
    }
  }, [workflowId]);

  useEffect(() => {
    if (currentWorkflow?.name) {
      setWorkflowName(currentWorkflow.name);
    } else {
      setWorkflowName("isimsiz dosya");
    }
  }, [currentWorkflow?.name]);

  // Clear chats and execution data when workflow changes to prevent accumulation
  useEffect(() => {
    if (currentWorkflow?.id) {
      // Reset active chat when switching to a different workflow
      setActiveChatflowId(null);
      // Clear chats when switching to a different workflow
      clearAllChats();
      // Clear execution data for the previous workflow
      setCurrentExecutionForWorkflow(currentWorkflow.id, null);
    }
  }, [currentWorkflow?.id, clearAllChats, setCurrentExecutionForWorkflow, setActiveChatflowId]);

  useEffect(() => {
    if (currentWorkflow?.flow_data) {
      const { nodes, edges } = currentWorkflow.flow_data;
      setNodes(nodes || []);

      // Clean up invalid edges that reference non-existent nodes
      if (edges && nodes) {
        const nodeIds = new Set(nodes.map((n) => n.id));
        const validEdges = edges.filter(
          (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)
        );
        setEdges(validEdges);
      } else {
        setEdges(edges || []);
      }
    } else {
      setNodes([]);
      setEdges([]);
    }
  }, [currentWorkflow]);

  useEffect(() => {
    if (currentWorkflow) {
      const currentFlowData: WorkflowData = {
        nodes: nodes as WorkflowNode[],
        edges: edges as WorkflowEdge[],
      };
      const originalFlowData = currentWorkflow.flow_data;
      // Use normalized comparison to avoid false positives from React Flow internal properties
      const hasChanges =
        normalizeFlowDataForComparison(currentFlowData) !== normalizeFlowDataForComparison(originalFlowData);
      setHasUnsavedChanges(hasChanges);
    }
  }, [nodes, edges, currentWorkflow]);

  // Load chat history on component mount
  useEffect(() => {
    if (currentWorkflow?.id) {
      // Load workflow-specific chats only
      fetchWorkflowChats(currentWorkflow.id);
    } else {
      // Clear chats when no workflow is selected (new workflow)
      clearAllChats();
    }
  }, [currentWorkflow?.id, fetchWorkflowChats, clearAllChats]);

  // Load chat messages when active chat changes
  useEffect(() => {
    if (activeChatflowId) {
      fetchChatMessages(activeChatflowId);
    }
  }, [activeChatflowId, fetchChatMessages]);

  // Listen for chat execution errors and display them
  useEffect(() => {
    const handleChatExecutionError = (event: CustomEvent) => {
      console.error("❌ Chat execution error received:", event.detail);

      const errorDetails = {
        message: event.detail.error || "Chat execution failed",
        type: event.detail.error_type || "execution",
        nodeId: event.detail.node_id,
        timestamp: new Date().toLocaleTimeString(),
      };

      setDetailedExecutionError(errorDetails);
    };

    window.addEventListener(
      "chat-execution-error",
      handleChatExecutionError as EventListener
    );

    return () => {
      window.removeEventListener(
        "chat-execution-error",
        handleChatExecutionError as EventListener
      );
    };
  }, [enqueueSnackbar]);

  // Clean up edges when nodes are deleted
  useEffect(() => {
    if (nodes.length > 0 && edges.length > 0) {
      const nodeIds = new Set(nodes.map((n) => n.id));
      const validEdges = edges.filter(
        (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)
      );

      if (validEdges.length !== edges.length) {
        console.log(
          `Auto-cleaned ${edges.length - validEdges.length} orphaned edges`
        );
        // Use callback to prevent infinite loop
        setEdges((prevEdges: Edge[]) => {
          if (prevEdges.length !== validEdges.length) {
            return validEdges;
          }
          return prevEdges;
        });
      }
    }
  }, [nodes]); // Only depend on nodes to prevent infinite loop

  const onConnect = useCallback(
    (params: Connection | Edge) => {
      setEdges((eds: Edge[]) => addEdge({ ...params, type: "custom" }, eds));
    },
    [setEdges]
  );

  // Helper function to normalize name for Jinja template compatibility
  // Rules: lowercase, underscores instead of spaces, no special chars, must start with letter
  const normalizeForJinja = (name: string): string => {
    let normalized = name
      .toLowerCase()           // Convert to lowercase
      .replace(/\s+/g, "_")    // Replace spaces with underscores
      .replace(/[^a-z0-9_]/g, ""); // Remove special characters

    // Must start with a letter
    if (/^[0-9]/.test(normalized)) {
      normalized = "n_" + normalized;
    }

    return normalized || "node";
  };

  // Helper function to generate unique node name with suffix (_1, _2, _3, etc.)
  // This name is used as the default node alias for Jinja templates
  const generateUniqueNodeName = useCallback(
    (baseName: string, nodeType: string, existingNodes: Node[]): string => {
      // Normalize baseName for Jinja compatibility
      const normalizedBaseName = normalizeForJinja(baseName);

      // Count nodes of the same type
      const sameTypeNodes = existingNodes.filter((n) => n.type === nodeType);

      if (sameTypeNodes.length === 0) {
        return normalizedBaseName;
      }

      // Find the highest existing suffix number
      const escapedBaseName = normalizedBaseName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const suffixPattern = new RegExp(`^${escapedBaseName}(?:_(\\d+))?$`);
      let maxSuffix = 0;

      sameTypeNodes.forEach((node) => {
        const nodeName = String((node.data as any)?.name || "");
        const match = nodeName.match(suffixPattern);
        if (match) {
          const suffix = match[1] ? parseInt(match[1], 10) : 0;
          maxSuffix = Math.max(maxSuffix, suffix);
        }
      });

      return `${normalizedBaseName}_${maxSuffix + 1}`;
    },
    []
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeTypeData = event.dataTransfer.getData("application/reactflow");

      if (!nodeTypeData) {
        return;
      }

      const nodeType = JSON.parse(nodeTypeData);
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const nodeMetadata = availableNodes.find(
        (n: NodeMetadata) => n.name === nodeType.type
      );

      // Generate unique node name with suffix for Jinja template usage
      const baseName = nodeType.label || nodeMetadata?.display_name || nodeType.type;
      const uniqueName = generateUniqueNodeName(baseName, nodeType.type, nodes);

      const newNode: Node = {
        id: `${nodeType.type}__${uuidv4()}`,
        type: nodeType.type,
        position,
        data: {
          ...nodeType.data,
          name: uniqueName,  // Must be after spread to override nodeType.data.name
          metadata: nodeMetadata,
        },
      };

      setNodes((nds: Node[]) => nds.concat(newNode));

      // Update smart suggestions with the last added node
      setLastAddedNode(nodeType.type);

      // Update recommendations after setting the last added node
      updateRecommendations(availableNodes);
    },
    [screenToFlowPosition, availableNodes, setLastAddedNode, updateRecommendations, generateUniqueNodeName, nodes]
  );

  const handleSave = useCallback(async () => {
    const flowData: WorkflowData = {
      nodes: nodes as WorkflowNode[],
      edges: edges as WorkflowEdge[],
    };

    if (!workflowName || workflowName.trim() === "") {
      enqueueSnackbar("Lütfen bir dosya adı girin.", { variant: "warning" });
      return;
    }

    if (!currentWorkflow) {
      try {
        const newWorkflow = await createWorkflow({
          name: workflowName,
          description: "",
          flow_data: flowData,
        });
        setCurrentWorkflow(newWorkflow);
        setHasUnsavedChanges(false); // Kaydetme başarılı olduğunda false yap
        enqueueSnackbar(`Workflow "${workflowName}" created and saved!`, {
          variant: "success",
        });
      } catch (error) {
        enqueueSnackbar("Failed to create workflow.", { variant: "error" });
      }
      return;
    }

    try {
      await updateWorkflow(currentWorkflow.id, {
        name: workflowName,
        description: currentWorkflow.description,
        flow_data: flowData,
      });
      setHasUnsavedChanges(false); // Kaydetme başarılı olduğunda false yap
      enqueueSnackbar("Workflow saved successfully!", { variant: "success" });
    } catch (error) {
      console.error("Failed to save workflow:", error);
      enqueueSnackbar("Failed to save workflow.", { variant: "error" });
    }
  }, [
    currentWorkflow,
    nodes,
    edges,
    createWorkflow,
    updateWorkflow,
    enqueueSnackbar,
    setCurrentWorkflow,
    setHasUnsavedChanges,
    workflowName,
  ]);

  // Auto-save function
  const handleAutoSave = useCallback(async () => {
    if (!autoSaveEnabled || !hasUnsavedChanges || !currentWorkflow) {
      return;
    }

    setAutoSaveStatus("saving");

    try {
      const flowData: WorkflowData = {
        nodes: nodes as WorkflowNode[],
        edges: edges as WorkflowEdge[],
      };

      await updateWorkflow(currentWorkflow.id, {
        name: workflowName,
        description: currentWorkflow.description,
        flow_data: flowData,
      });

      setHasUnsavedChanges(false);
      setLastAutoSave(new Date());
      setAutoSaveStatus("saved");

      // Show subtle notification
      enqueueSnackbar("Auto-saved", {
        variant: "success",
        autoHideDuration: 2000,
        anchorOrigin: { vertical: "bottom", horizontal: "right" },
      });

      // Reset status after 3 seconds
      setTimeout(() => {
        setAutoSaveStatus("idle");
      }, 3000);
    } catch (error) {
      console.error("Auto-save failed:", error);
      setAutoSaveStatus("error");

      enqueueSnackbar("Auto-save failed", {
        variant: "error",
        autoHideDuration: 3000,
        anchorOrigin: { vertical: "bottom", horizontal: "right" },
      });

      // Reset error status after 5 seconds
      setTimeout(() => {
        setAutoSaveStatus("idle");
      }, 5000);
    }
  }, [
    autoSaveEnabled,
    hasUnsavedChanges,
    currentWorkflow,
    nodes,
    edges,
    updateWorkflow,
    workflowName,
    setHasUnsavedChanges,
    enqueueSnackbar,
  ]);

  // Auto-save timer effect
  useEffect(() => {
    if (!autoSaveEnabled || !currentWorkflow) {
      return;
    }

    const timer = setInterval(() => {
      if (hasUnsavedChanges) {
        handleAutoSave();
      }
    }, autoSaveInterval);

    return () => clearInterval(timer);
  }, [
    autoSaveEnabled,
    autoSaveInterval,
    hasUnsavedChanges,
    currentWorkflow,
    handleAutoSave,
  ]);

  // Function to handle StartNode execution with proper service integration
  const handleStartNodeExecution = useCallback(
    async (nodeId: string) => {
      if (!currentWorkflow) {
        enqueueSnackbar("No workflow selected", { variant: "error" });
        return;
      }

      try {
        // Reset previous statuses
        setNodeStatus({});
        setEdgeStatus({});
        // Show loading message
        enqueueSnackbar("Executing workflow...", { variant: "info" });

        // Get the flow data
        const flowData: WorkflowData = {
          nodes: nodes as WorkflowNode[],
          edges: edges as WorkflowEdge[],
        };

        // Prepare execution inputs
        const executionData = {
          flow_data: flowData,
          input_text: "",
          node_id: nodeId,
          execution_type: "manual",
          trigger_source: "start_node_double_click",
        };

        // Remove legacy pre-animation; rely solely on streaming events
        setActiveEdges([]);
        setActiveNodes([]);

        // Streaming execution to reflect real-time node/edge status
        try {
          const stream = await executeWorkflowStream({
            ...executionData,
            workflow_id: currentWorkflow.id,
          });

          const reader = stream.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = "";

          const processChunk = (text: string) => {
            buffer += text;
            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";
            for (const part of parts) {
              const dataLine = part
                .split("\n")
                .find((l) => l.startsWith("data:"));
              if (!dataLine) continue;
              const jsonStr = dataLine.replace(/^data:\s*/, "").trim();
              if (!jsonStr) continue;
              try {
                const evt = JSON.parse(jsonStr);
                const t = evt.type as string | undefined;
                if (t === "node_start") {
                  const nid = String(evt.node_id || "");
                  const previousNodeId = evt.previous_node_id;

                  if (nid) {
                    setActiveNodes([nid]);
                    setNodeStatus((s) => ({ ...s, [nid]: "pending" }));

                    // Get all incoming edges to this node
                    const allIncomingEdges = (edges as Edge[]).filter(
                      (e) => e.target === nid
                    );

                    // Separate edges into execution flow (from previous node) and provider inputs
                    const executionFlowEdge = previousNodeId
                      ? allIncomingEdges.find((e) => e.source === previousNodeId)
                      : null;

                    // Check if THIS node is a processor type that accepts provider inputs
                    const currentNode = nodes.find((n) => n.id === nid);
                    const processorTypes = [
                      'ReactAgentNode', 'Agent', // Added 'Agent'
                      'VectorStoreOrchestrator',
                      'ChunkSplitterNode', 'ChunkSplitter',
                      'CodeNode', 'ConditionNode'
                    ];
                    const isProcessorNode = currentNode && processorTypes.some(pt =>
                      currentNode.type?.includes(pt) || currentNode.type === pt
                    );

                    // Provider input edges - ONLY for processor nodes
                    let providerInputEdges: Edge[] = [];
                    if (isProcessorNode) {
                      providerInputEdges = allIncomingEdges.filter((e) => {
                        // Skip the execution flow edge
                        if (executionFlowEdge && e.id === executionFlowEdge.id) return false;

                        // Check if source node is a provider type
                        const sourceNode = nodes.find((n) => n.id === e.source);
                        if (!sourceNode) return false;

                        // Provider node types that supply data to processors
                        const providerTypes = [
                          'OpenAINode', 'OpenAIChat', 'OpenAICompatibleNode',
                          'OpenAIEmbeddingsProvider',
                          'BufferMemoryNode', 'BufferMemory',
                          'ConversationMemoryNode', 'ConversationMemory',
                          'RetrieverProvider',
                          'TavilySearchNode', 'TavilySearch',
                          'CohereRerankerNode',
                          'VectorStoreOrchestrator',
                          'ChunkSplitterNode', 'ChunkSplitter',
                          'DocumentLoaderNode',
                          'WebScraperNode', 'WebScraper',
                          'StringInputNode'
                        ];

                        return providerTypes.some(pt =>
                          sourceNode.type?.includes(pt) ||
                          (sourceNode.type && pt.includes(sourceNode.type)) ||
                          sourceNode.type === pt
                        );
                      });
                    }

                    // Combine edges to animate
                    const edgesToAnimate: Edge[] = [];

                    if (executionFlowEdge) {
                      edgesToAnimate.push(executionFlowEdge);
                    } else if (!previousNodeId && allIncomingEdges.length === 1) {
                      // First node with single incoming edge
                      edgesToAnimate.push(allIncomingEdges[0]);
                    }

                    // Add provider input edges (only for processor nodes)
                    edgesToAnimate.push(...providerInputEdges);

                    if (edgesToAnimate.length > 0) {
                      console.log(
                        "StartNode: Setting edges as pending:",
                        edgesToAnimate.map(e => e.id),
                        `(${edgesToAnimate.length} edges to ${nid})`
                      );
                      setActiveEdges(edgesToAnimate.map((e) => e.id));
                      setEdgeStatus((s) => ({
                        ...s,
                        ...Object.fromEntries(
                          edgesToAnimate.map((e) => [e.id, "pending" as const])
                        ),
                      }));
                    }
                  }
                } else if (t === "node_end") {
                  const nid = String(evt.node_id || "");
                  if (nid) {
                    setNodeStatus((s) => ({ ...s, [nid]: "success" }));
                    // Only mark pending edges as success
                    setEdgeStatus((s) => {
                      const updated = { ...s };
                      Object.keys(updated).forEach((edgeId) => {
                        const edge = (edges as Edge[]).find((e) => e.id === edgeId);
                        if (edge && edge.target === nid && updated[edgeId] === "pending") {
                          updated[edgeId] = "success";
                        }
                      });
                      return updated;
                    });
                  }
                } else if (t === "error") {
                  // Mark current active items as failed
                  const failedNodeId = activeNodes[0];
                  setErrorNodeId(failedNodeId);

                  setNodeStatus((s) =>
                    failedNodeId ? { ...s, [failedNodeId]: "failed" } : s
                  );
                  setEdgeStatus((s) =>
                    activeEdges.length > 0
                      ? { ...s, [activeEdges[0]]: "failed" }
                      : s
                  );

                  // Create detailed error for display
                  const errorDetails = {
                    message: evt.error || "Node execution failed",
                    type: evt.error_type || "execution",
                    nodeId: evt.node_id || failedNodeId,
                    nodeType: evt.node_id
                      ? nodes.find((n) => n.id === evt.node_id)?.type
                      : failedNodeId
                        ? nodes.find((n) => n.id === failedNodeId)?.type
                        : undefined,
                    timestamp: evt.timestamp || new Date().toLocaleTimeString(),
                    stackTrace:
                      evt.stack_trace || evt.details || evt.stack_trace,
                  };

                  setDetailedExecutionError(errorDetails);
                } else if (t === "complete") {
                  // Store the execution result in the store
                  const executionResult = {
                    id: evt.execution_id || Date.now().toString(),
                    workflow_id: currentWorkflow.id,
                    input_text: executionData.input_text,
                    result: {
                      result: evt.result,
                      executed_nodes: evt.executed_nodes,
                      node_outputs: evt.node_outputs,
                      session_id: evt.session_id,
                      status: "completed" as const,
                    },
                    started_at: new Date().toISOString(),
                    completed_at: new Date().toISOString(),
                    status: "completed" as const,
                  };

                  setCurrentExecutionForWorkflow(currentWorkflow.id, executionResult);

                  setTimeout(() => {
                    setActiveEdges([]);
                    setActiveNodes([]);
                  }, 1500);
                }
              } catch {
                // ignore malformed chunks
              }
            }
          };

          // Pump the stream
          // We intentionally do not await the entire stream to keep UI responsive
          (async () => {
            try {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                processChunk(decoder.decode(value, { stream: true }));
              }
            } catch (_) {
              // ignore stream read errors
            } finally {
              try {
                reader.releaseLock();
              } catch { }
            }
          })();
        } catch (_) {
          // fallback to non-streaming if needed
          await executeWorkflow(currentWorkflow.id, executionData);
        }

        // Show success message
        enqueueSnackbar("Workflow executed successfully", {
          variant: "success",
        });

        // Clear any previous execution errors
        clearExecutionError();
      } catch (error: any) {
        console.error("Error executing workflow:", error);

        const failedNodeId = activeNodes[0];
        setErrorNodeId(failedNodeId);

        // Create detailed error for display
        const errorDetails = {
          message: error.message || "Workflow execution failed",
          type: "execution",
          nodeId: failedNodeId,
          nodeType: failedNodeId
            ? nodes.find((n) => n.id === failedNodeId)?.type
            : undefined,
          timestamp: new Date().toLocaleTimeString(),
          stackTrace: error.stack,
        };

        setDetailedExecutionError(errorDetails);

        enqueueSnackbar(`Error executing workflow: ${error.message}`, {
          variant: "error",
        });

        // Mark last active node/edge as failed if possible
        setNodeStatus((s) =>
          failedNodeId ? { ...s, [failedNodeId]: "failed" } : s
        );
        setEdgeStatus((s) =>
          activeEdges.length > 0 ? { ...s, [activeEdges[0]]: "failed" } : s
        );
      }
    },
    [
      currentWorkflow,
      nodes,
      edges,
      executeWorkflow,
      clearExecutionError,
      enqueueSnackbar,
      setActiveEdges,
      activeNodes,
      activeEdges,
    ]
  );

  // Error handling functions
  const handleErrorRetry = useCallback(() => {
    if (errorNodeId && currentWorkflow) {
      // Clear error state
      setDetailedExecutionError(null);
      setErrorNodeId(null);

      // Reset node status
      setNodeStatus((s) => {
        const newStatus = { ...s };
        delete newStatus[errorNodeId];
        return newStatus;
      });

      // Retry execution from the failed node
      handleStartNodeExecution(errorNodeId);
    }
  }, [errorNodeId, currentWorkflow, handleStartNodeExecution]);

  // Monitor execution errors and show them
  useEffect(() => {
    if (executionError) {
      // Create detailed error object
      const errorDetails = {
        message: executionError,
        type: "execution",
        timestamp: new Date().toLocaleTimeString(),
        nodeId: errorNodeId || undefined,
        nodeType: errorNodeId
          ? nodes.find((n) => n.id === errorNodeId)?.type
          : undefined,
      };

      setDetailedExecutionError(errorDetails);

      enqueueSnackbar(`Execution error: ${executionError}`, {
        variant: "error",
      });
      clearExecutionError();
    }
  }, [
    executionError,
    enqueueSnackbar,
    clearExecutionError,
    errorNodeId,
    nodes,
  ]);

  // Monitor execution loading state
  useEffect(() => {
    if (executionLoading) {
      enqueueSnackbar("Executing workflow...", { variant: "info" });
    }
  }, [executionLoading, enqueueSnackbar]);

  // Monitor successful execution and show success message
  useEffect(() => {
    if (currentExecution && !executionLoading) {
      setShowSuccessMessage(true);
      // Clear success message after 3 seconds
      const timer = setTimeout(() => {
        setShowSuccessMessage(false);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [currentExecution, executionLoading]);

  // Use stable nodeTypes - pass handlers via node data instead
  const nodeTypes = useMemo(
    () =>
      nodes.reduce(
        (acc, node) => {
          const nodeType = node.type as string;
          if (!acc[nodeType]) {
            acc[nodeType] = GenericNode;
          }
          return acc;
        },
        {
          StartNode: (props: any) => (
            <StartNode
              {...props}
              onExecute={handleStartNodeExecution}
              isExecuting={executionLoading}
              isActive={activeNodes.includes(props.id)}
            />
          ),
          EndNode: (props: any) => (
            <EndNode {...props} isActive={activeNodes.includes(props.id)} />
          ),
        } as Record<string, React.ComponentType<any> | null>
      ),
    [nodes, handleStartNodeExecution, executionLoading, activeNodes]
  );
  const handleClear = useCallback(() => {
    if (hasUnsavedChanges) {
      if (
        !window.confirm(
          "You have unsaved changes. Are you sure you want to clear the canvas?"
        )
      ) {
        return;
      }
    }
    setNodes([]);
    setEdges([]);
    setNodeStatus({});
    setEdgeStatus({});
    setCurrentWorkflow(null);
  }, [hasUnsavedChanges, setCurrentWorkflow]);

  // Handle navigation after modal actions
  const handleNavigation = useCallback((url: string) => {
    window.location.href = url;
  }, []);

  // Auto-save settings handler
  const handleAutoSaveSettings = useCallback(() => {
    autoSaveSettingsModalRef.current?.showModal();
  }, []);

  // Unsaved changes modal handlers
  const handleUnsavedChangesSave = useCallback(async () => {
    try {
      await handleSave();
      // Navigate to pending location after successful save
      if (pendingNavigation) {
        handleNavigation(pendingNavigation);
      }
    } catch (error) {
      enqueueSnackbar("Kaydetme başarısız oldu", { variant: "error" });
    }
  }, [handleSave, pendingNavigation, enqueueSnackbar, handleNavigation]);

  const handleUnsavedChangesDiscard = useCallback(() => {
    setHasUnsavedChanges(false);
    // Navigate to pending location
    if (pendingNavigation) {
      handleNavigation(pendingNavigation);
    }
  }, [setHasUnsavedChanges, pendingNavigation, handleNavigation]);

  const handleUnsavedChangesCancel = useCallback(() => {
    setPendingNavigation(null);
  }, []);

  // Function to check unsaved changes before navigation
  const checkUnsavedChanges = useCallback(
    (url: string) => {
      if (hasUnsavedChanges) {
        setPendingNavigation(url);
        unsavedChangesModalRef.current?.showModal();
        return false;
      }
      return true;
    },
    [hasUnsavedChanges]
  );

  // handleSendMessage fonksiyonu güncellendi
  const handleSendMessage = async () => {
    if (chatInput.trim() === "") return;
    const userMessage = chatInput;
    setChatInput("");

    const flowData: WorkflowData = {
      nodes: nodes as WorkflowNode[],
      edges: edges as WorkflowEdge[],
    };

    try {
      if (!currentWorkflow) {
        enqueueSnackbar("Bir workflow seçili değil!", { variant: "warning" });
        return;
      }
      if (!activeChatflowId) {
        await startLLMChat(flowData, userMessage, currentWorkflow.id);
      } else {
        await sendLLMMessage(
          flowData,
          userMessage,
          activeChatflowId,
          currentWorkflow.id
        );
      }
    } catch (e: any) {
      // Hata mesajını chat'e ekle
      addMessage(activeChatflowId || "error", {
        id: uuidv4(),
        chatflow_id: activeChatflowId || "error",
        role: "assistant",
        content: e.message || "Bilinmeyen bir hata oluştu.",
        created_at: new Date().toISOString(),
      });
    }
  };

  // Chat geçmişini store'dan al
  const chatHistory = activeChatflowId ? chats[activeChatflowId] || [] : [];

  const handleClearChat = () => {
    setActiveChatflowId(null);
  };

  const handleShowHistory = () => {
    setChatHistoryOpen(true);
  };

  const handleSelectChat = (chatflowId: string) => {
    if (chatflowId === "") {
      // New chat
      setActiveChatflowId(null);
    } else {
      // Select existing chat
      setActiveChatflowId(chatflowId);
    }
  };

  // Handle node click for fullscreen modal
  const handleNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      // Don't open modal if it's already in config mode or a double click
      if (node.data?.isConfigMode || event.detail === 2) {
        return;
      }

      const nodeMetadata =
        node.data?.metadata ||
        availableNodes.find((n: NodeMetadata) => n.name === node.type);

      const configComponent = nodeConfigComponents[node.type!];

      if (nodeMetadata && configComponent) {
        setFullscreenModal({
          isOpen: true,
          nodeData: node,
          nodeMetadata,
          configComponent,
        });
      }
    },
    [availableNodes, nodeConfigComponents]
  );

  // Handle fullscreen modal save
  const handleFullscreenModalSave = useCallback(
    (values: any) => {
      if (fullscreenModal.nodeData) {
        setNodes((nodes) =>
          nodes.map((node) =>
            node.id === fullscreenModal.nodeData.id
              ? {
                ...node,
                data: { ...node.data, ...values },
              }
              : node
          )
        );
      }
      setFullscreenModal({ isOpen: false });
    },
    [fullscreenModal.nodeData, setNodes]
  );

  // Handle fullscreen modal close
  const handleFullscreenModalClose = useCallback(() => {
    setFullscreenModal({ isOpen: false });
  }, []);

  // Edge'leri render ederken CustomEdge'a isActive prop'u ilet
  const edgeTypes = useMemo(
    () => ({
      custom: (edgeProps: any) => (
        <CustomEdge
          {...edgeProps}
          isActive={activeEdges.includes(edgeProps.id)}
        />
      ),
    }),
    [activeEdges]
  );

  return (
    <>
      <Navbar
        workflowName={workflowName}
        setWorkflowName={setWorkflowName}
        onSave={handleSave}
        currentWorkflow={currentWorkflow}
        setCurrentWorkflow={setCurrentWorkflow}
        setNodes={setNodes}
        setEdges={setEdges}
        deleteWorkflow={deleteWorkflow}
        isLoading={isLoading}
        checkUnsavedChanges={checkUnsavedChanges}
        autoSaveStatus={autoSaveStatus}
        lastAutoSave={lastAutoSave}
        onAutoSaveSettings={handleAutoSaveSettings}
        updateWorkflowStatus={updateWorkflowStatus}
        updateWorkflowVisibility={updateWorkflowVisibility}
      />
      <div className="w-full h-full relative pt-16 flex bg-black">
        {/* Sidebar Toggle Button */}
        <SidebarToggleButton
          isSidebarOpen={isSidebarOpen}
          setIsSidebarOpen={setIsSidebarOpen}
        />

        {/* Sidebar modal */}
        {isSidebarOpen && <Sidebar onClose={() => setIsSidebarOpen(false)} />}

        {/* Canvas alanı */}
        <div className="flex-1">
          {/* Error Display */}
          <ErrorDisplayComponent
            error={detailedExecutionError || error}
            onRetry={detailedExecutionError ? handleErrorRetry : undefined}
            onDismiss={detailedExecutionError ? handleErrorDismiss : undefined}
          />

          {/* ReactFlow Canvas */}
          <ReactFlowCanvas
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes as any}
            edgeTypes={edgeTypes}
            activeEdges={activeEdges}
            reactFlowWrapper={reactFlowWrapper}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeStatus={nodeStatus}
            edgeStatus={edgeStatus}
            onNodeClick={handleNodeClick}
          />

          {/* Chat Toggle Button */}
          <button
            className={`fixed bottom-5 right-5 z-50 px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-3 transition-all duration-300 backdrop-blur-sm border ${chatOpen
              ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white border-blue-400/30 shadow-blue-500/25"
              : "bg-gray-900/80 text-gray-300 border-gray-700/50 hover:bg-gray-800/90 hover:border-gray-600/50 hover:text-white"
              }`}
            onClick={() => setChatOpen((v) => !v)}
          >
            <div className="relative">
              <svg
                className={`w-5 h-5 transition-transform duration-300 ${chatOpen ? "rotate-12" : ""
                  }`}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.77 9.77 0 01-4-.8L3 20l.8-3.2A7.96 7.96 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              {chatOpen && (
                <div className="absolute -top-1 -right-1 w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              )}
            </div>
            <span className="font-medium text-sm">Chat</span>
            {chatOpen && (
              <div className="w-1 h-1 bg-white rounded-full animate-ping"></div>
            )}
          </button>

          {/* Chat Component */}
          <ChatComponent
            chatOpen={chatOpen}
            setChatOpen={setChatOpen}
            chatHistory={chatHistory}
            chatError={chatError}
            chatLoading={chatLoading}
            chatInput={chatInput}
            setChatInput={setChatInput}
            onSendMessage={handleSendMessage}
            onClearChat={handleClearChat}
            onShowHistory={handleShowHistory}
            activeChatflowId={activeChatflowId}
            currentWorkflow={currentWorkflow}
            flowData={{
              nodes: nodes as WorkflowNode[],
              edges: edges as WorkflowEdge[],
            }}
            chatThinking={chatThinking}
          />

          {/* Chat History Sidebar */}
          <ChatHistorySidebar
            isOpen={chatHistoryOpen}
            onClose={() => setChatHistoryOpen(false)}
            onSelectChat={handleSelectChat}
            activeChatflowId={activeChatflowId}
            workflow_id={currentWorkflow?.id}
          />

          {/* Execution Status Indicator */}
          {executionLoading && (
            <div className="fixed top-20 right-5 z-50 px-4 py-2 rounded-lg bg-gradient-to-r from-yellow-500 to-orange-600 text-white shadow-lg flex items-center gap-2 animate-pulse">
              <Loader className="w-4 h-4 animate-spin" />
              <span className="text-sm font-medium">Executing workflow...</span>
            </div>
          )}

          {/* Execution Error Display */}
          {executionError && (
            <div className="fixed top-20 right-5 z-50 px-4 py-2 rounded-lg bg-gradient-to-r from-red-500 to-rose-600 text-white shadow-lg flex items-center gap-2">
              <div className="w-4 h-4 bg-white rounded-full flex items-center justify-center">
                <span className="text-red-600 text-xs font-bold">!</span>
              </div>
              <span className="text-sm font-medium">Execution failed</span>
            </div>
          )}

          {/* Execution Success Display */}
          {showSuccessMessage && currentExecution && !executionLoading && (
            <div className="fixed top-20 right-5 z-50 px-4 py-2 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-lg flex items-center gap-2 animate-pulse">
              <div className="w-4 h-4 bg-white rounded-full flex items-center justify-center">
                <span className="text-green-600 text-xs font-bold">✓</span>
              </div>
              <span className="text-sm font-medium">Execution completed</span>
            </div>
          )}
        </div>
      </div>
      <TutorialButton />

      {/* Unsaved Changes Modal */}
      <UnsavedChangesModal
        ref={unsavedChangesModalRef}
        onSave={handleUnsavedChangesSave}
        onDiscard={handleUnsavedChangesDiscard}
        onCancel={handleUnsavedChangesCancel}
      />

      {/* Auto-save Settings Modal */}
      <AutoSaveSettingsModal
        ref={autoSaveSettingsModalRef}
        autoSaveEnabled={autoSaveEnabled}
        setAutoSaveEnabled={setAutoSaveEnabled}
        autoSaveInterval={autoSaveInterval}
        setAutoSaveInterval={setAutoSaveInterval}
        lastAutoSave={lastAutoSave}
      />

      {/* Fullscreen Node Configuration Modal */}
      {fullscreenModal.isOpen &&
        fullscreenModal.nodeMetadata &&
        fullscreenModal.configComponent && (
          <FullscreenNodeModal
            isOpen={fullscreenModal.isOpen}
            onClose={handleFullscreenModalClose}
            nodeMetadata={fullscreenModal.nodeMetadata}
            configData={fullscreenModal.nodeData?.data || {}}
            onSave={handleFullscreenModalSave}
            onExecute={() =>
              handleStartNodeExecution(fullscreenModal.nodeData?.id || "")
            }
            ConfigComponent={fullscreenModal.configComponent}
            executionData={{
              nodeId: fullscreenModal.nodeData?.id || "",
              inputs: (() => {
                const nodeId = fullscreenModal.nodeData?.id;
                if (!nodeId || !currentExecution?.result?.node_outputs)
                  return {};

                // First try to get tracked inputs from execution data
                const nodeExecutionData =
                  currentExecution?.result?.node_outputs?.[nodeId];
                if (
                  nodeExecutionData?.inputs &&
                  Object.keys(nodeExecutionData.inputs).length > 0
                ) {
                  return nodeExecutionData.inputs;
                }

                // Fallback to edge-based input construction for nodes without tracked inputs
                const inputEdges = edges.filter(
                  (edge) => edge.target === nodeId
                );
                if (inputEdges.length === 0) {
                  return {};
                }

                const inputs: Record<string, any[]> = {};

                inputEdges.forEach((edge) => {
                  const sourceNodeOutput =
                    currentExecution?.result?.node_outputs?.[edge.source];
                  const inputKey = edge.targetHandle || "input";
                  const sourceNodeId = edge.source;
                  const sourceNode = nodes.find((n) => n.id === sourceNodeId);

                  // Extract actual output value if it's wrapped in execution data structure
                  let value: any;
                  if (sourceNodeOutput !== undefined) {
                    // Check for wrapped output fields in order of priority
                    const OUTPUT_FIELDS = ['output', 'outputs'];
                    const isObject = sourceNodeOutput && typeof sourceNodeOutput === "object";
                    const outputField = isObject
                      ? OUTPUT_FIELDS.find(field => sourceNodeOutput[field] !== undefined)
                      : null;

                    value = outputField ? sourceNodeOutput[outputField] : sourceNodeOutput;
                  } else {
                    // Try to get default value from source node config
                    const sourceData = (sourceNode?.data as any) || {};

                    // List of fallback fields to check in order of priority
                    const FALLBACK_FIELDS = ['text_input', 'text', 'content', 'value', 'query', 'prompt'];
                    const fallbackField = FALLBACK_FIELDS.find(field => sourceData[field] !== undefined);

                    if (fallbackField) {
                      value = sourceData[fallbackField];
                    } else {
                      // Placeholder for nodes that haven't executed yet and have no default value
                      value = {
                        _placeholder: true,
                        message: "No default value available",
                        sourceNodeId: edge.source
                      };
                    }
                  }

                  if (!Array.isArray(inputs[inputKey])) {
                    inputs[inputKey] = [];
                  }
                  inputs[inputKey].push(value);
                });

                return inputs;
              })(),
              inputs_meta: (() => {
                const nodeId = fullscreenModal.nodeData?.id;
                if (!nodeId || !currentExecution?.result?.node_outputs)
                  return undefined;

                // 1) If engine already tracked inputs_meta explicitly (e.g., from chat), use it
                const nodeExecutionData =
                  currentExecution?.result?.node_outputs?.[nodeId];
                if (
                  nodeExecutionData?.inputs_meta &&
                  Object.keys(nodeExecutionData.inputs_meta).length > 0
                ) {
                  return nodeExecutionData.inputs_meta;
                }

                // 2) Fallback: build inputs_meta from incoming edges
                const inputEdges = edges.filter(
                  (edge) => edge.target === nodeId
                );
                if (inputEdges.length === 0) {
                  return undefined;
                }

                const meta: Record<
                  string,
                  {
                    sourceNodeId: string;
                    sourceNodeName?: string;
                    sourceNodeAlias?: string;
                    sourceHandle?: string;
                  }[]
                > = {};

                inputEdges.forEach((edge) => {
                  const inputKey = edge.targetHandle || "input";
                  const sourceNodeId = edge.source;
                  const sourceNode = nodes.find((n) => n.id === sourceNodeId);

                  const sourceData = (sourceNode?.data as any) || {};
                  const sourceMetadata = (sourceData.metadata as any) || {};

                  const sourceAlias =
                    sourceData.name || sourceMetadata.display_name;
                  const sourceName =
                    sourceMetadata.display_name ||
                    sourceNode?.type ||
                    sourceNodeId;

                  const entry = {
                    sourceNodeId,
                    sourceNodeName: sourceName,
                    sourceNodeAlias: sourceAlias,
                    sourceHandle: edge.sourceHandle || undefined,
                  };

                  if (!Array.isArray(meta[inputKey])) {
                    meta[inputKey] = [];
                  }
                  meta[inputKey].push(entry);
                });

                return meta;
              })(),
              outputs: (() => {
                const nodeId = fullscreenModal.nodeData?.id;
                if (!nodeId) return undefined;

                // 1. If execution output exists, use it
                const executionOutput = currentExecution?.result?.node_outputs?.[nodeId];
                if (executionOutput) {
                  return executionOutput;
                }

                // 2. Only show fallback/placeholder if a workflow execution exists but this node hasn't run
                if (currentExecution?.result?.node_outputs) {
                  // Check node config data for fallback fields
                  const nodeData = (fullscreenModal.nodeData?.data as any) || {};
                  const OUTPUT_FALLBACK_FIELDS = ['output', 'text_input', 'text', 'content', 'value', 'result', 'response', 'query', 'prompt'];
                  const fallbackField = OUTPUT_FALLBACK_FIELDS.find(field => nodeData[field] !== undefined);

                  if (fallbackField) {
                    return { output: nodeData[fallbackField] };
                  }

                  // No fallback fields found, return placeholder
                  return {
                    output: {
                      _placeholder: true,
                      message: "No default value available",
                      nodeId: nodeId
                    }
                  };
                }

                // 3. No execution exists at all - return undefined (shows "No Output Data Yet")
                return undefined;
              })(),
              status:
                currentExecution?.status === "completed"
                  ? "completed"
                  : currentExecution?.status === "running"
                    ? "running"
                    : currentExecution?.status === "failed"
                      ? "failed"
                      : "pending",
            }}
          />
        )}
    </>
  );
}

// Add chat execution event listener for node and edge status updates
function useChatExecutionListener(
  nodes: Node[],
  setNodeStatus: React.Dispatch<
    React.SetStateAction<Record<string, NodeStatus>>
  >,
  edges: Edge[],
  setEdgeStatus: React.Dispatch<
    React.SetStateAction<Record<string, NodeStatus>>
  >,
  setActiveEdges: React.Dispatch<React.SetStateAction<string[]>>,
  setActiveNodes: React.Dispatch<React.SetStateAction<string[]>>
) {
  useEffect(() => {
    const handleChatExecutionStart = () => {
      setNodeStatus({});
      setEdgeStatus({});
      setActiveEdges([]);
      setActiveNodes([]);
    };

    const handleChatExecutionComplete = () => {
      setActiveEdges([]);
      setActiveNodes([]);
    };

    const handleChatExecutionEvent = (event: CustomEvent) => {
      const { event: eventType, node_id, ...data } = event.detail;

      if (eventType === "node_start" && node_id) {
        // PRIORITY 1: Exact ID match (most reliable)
        let actualNode = nodes.find((n) => n.id === node_id);

        // PRIORITY 2: If no exact match, try fuzzy matching as fallback
        if (!actualNode) {
          actualNode = nodes.find((n) => {
            // Match by data.name (user-defined name)
            if (n.data.name === node_id) {
              return true;
            }

            // Match by type (only if exactly one node of this type exists)
            if (n.type === node_id) {
              const sameTypeNodes = nodes.filter((node) => node.type === n.type);
              return sameTypeNodes.length === 1;
            }

            // Derive a clean node type/id token. New ids use `Type__UUID`.
            const cleanNodeId = node_id.includes("__")
              ? node_id.split("__")[0]
              : node_id.replace(/\-\d+$/, "");

            // Only use includes matching if there's exactly one node of this type
            if (n.type && n.type === cleanNodeId) {
              const sameTypeNodes = nodes.filter((node) => node.type === n.type);
              return sameTypeNodes.length === 1;
            }

            // Match by data properties if available
            if (n.data?.node_name && n.data.node_name === node_id) {
              return true;
            }

            return false;
          });
        }

        if (actualNode) {
          // Set active node (for flow animation)
          setActiveNodes([actualNode.id]);
          setNodeStatus((prev) => ({
            ...prev,
            [actualNode.id]: "pending", // Start with pending like in start node execution
          }));

          // Get all incoming edges to this node
          const allIncomingEdges = edges.filter((e) => e.target === actualNode.id);

          // Use previous_node_id from backend to find execution flow edge
          const previousNodeId = data.previous_node_id;

          // Find execution flow edge (from previous node in sequence)
          let executionFlowEdge: Edge | null = null;
          if (previousNodeId) {
            executionFlowEdge = allIncomingEdges.find(
              (e) => e.source === previousNodeId
            ) || null;

            // Fuzzy match if exact not found
            if (!executionFlowEdge) {
              const cleanPrevId = previousNodeId.includes("__")
                ? previousNodeId.split("__")[0]
                : previousNodeId;
              executionFlowEdge = allIncomingEdges.find((e) =>
                e.source.startsWith(cleanPrevId + "__") || e.source === cleanPrevId
              ) || null;
            }
          }

          // Check if THIS node is a processor type that accepts provider inputs
          const processorTypes = [
            'ReactAgentNode', 'Agent', // Added 'Agent'
            'VectorStoreOrchestrator',
            'ChunkSplitterNode', 'ChunkSplitter',
            'CodeNode', 'ConditionNode'
          ];
          const isProcessorNode = actualNode.type && processorTypes.some(pt =>
            actualNode.type?.includes(pt) || actualNode.type === pt
          );

          // Provider input edges - ONLY for processor nodes
          let providerInputEdges: Edge[] = [];
          if (isProcessorNode) {
            providerInputEdges = allIncomingEdges.filter((e) => {
              // Skip execution flow edge
              if (executionFlowEdge && e.id === executionFlowEdge.id) return false;

              // Check if source is a provider node
              const sourceNode = nodes.find((n) => n.id === e.source);
              if (!sourceNode) return false;

              const providerTypes = [
                'OpenAINode', 'OpenAIChat', 'OpenAICompatibleNode',
                'OpenAIEmbeddingsProvider',
                'BufferMemoryNode', 'BufferMemory',
                'ConversationMemoryNode', 'ConversationMemory',
                'RetrieverProvider',
                'TavilySearchNode', 'TavilySearch',
                'CohereRerankerNode',
                'VectorStoreOrchestrator',
                'ChunkSplitterNode', 'ChunkSplitter',
                'DocumentLoaderNode',
                'WebScraperNode', 'WebScraper',
                'StringInputNode'
              ];

              const isProvider = providerTypes.some(pt =>
                sourceNode.type?.includes(pt) ||
                (sourceNode.type && pt.includes(sourceNode.type)) ||
                sourceNode.type === pt
              );

              return isProvider;
            });
          }

          // Combine edges to animate
          const edgesToAnimate: Edge[] = [];

          if (executionFlowEdge) {
            edgesToAnimate.push(executionFlowEdge);
          } else if (!previousNodeId && allIncomingEdges.length === 1) {
            edgesToAnimate.push(allIncomingEdges[0]);
          }

          // Add provider edges (only for processor nodes)
          edgesToAnimate.push(...providerInputEdges);

          setActiveEdges(edgesToAnimate.map((e) => e.id));
          if (edgesToAnimate.length > 0) {
            setEdgeStatus((prev) => ({
              ...prev,
              ...Object.fromEntries(
                edgesToAnimate.map((e) => [e.id, "pending" as const])
              ),
            }));
          } else if (allIncomingEdges.length > 0) {
            console.log("No matching edges to animate for", actualNode.id);
          }
        }
      }

      if (eventType === "node_end" && node_id) {
        // PRIORITY 1: Exact ID match (most reliable)
        let actualNode = nodes.find((n) => n.id === node_id);

        // PRIORITY 2: If no exact match, try fuzzy matching as fallback
        if (!actualNode) {
          actualNode = nodes.find((n) => {
            // Match by data.name (user-defined name)
            if (n.data.name === node_id) {
              return true;
            }

            // Match by type (only if exactly one node of this type exists)
            if (n.type === node_id) {
              const sameTypeNodes = nodes.filter((node) => node.type === n.type);
              return sameTypeNodes.length === 1;
            }

            // Derive a clean node type/id token. New ids use `Type__UUID`.
            const cleanNodeId = node_id.includes("__")
              ? node_id.split("__")[0]
              : node_id.replace(/\-\d+$/, "");

            // Only use includes matching if there's exactly one node of this type
            if (n.type && n.type === cleanNodeId) {
              const sameTypeNodes = nodes.filter((node) => node.type === n.type);
              return sameTypeNodes.length === 1;
            }

            // Match by data properties if available
            if (n.data?.node_name && n.data.node_name === node_id) {
              return true;
            }

            return false;
          });
        }

        if (actualNode) {
          setNodeStatus((prev) => ({
            ...prev,
            [actualNode.id]: "success",
          }));

          // Only mark the edge that was set as pending (from node_start) as success
          // This ensures only the actual execution flow edge gets marked
          setEdgeStatus((prev) => {
            const updated = { ...prev };
            Object.keys(updated).forEach((edgeId) => {
              const edge = edges.find((e) => e.id === edgeId);
              if (edge && edge.target === actualNode.id && updated[edgeId] === "pending") {
                updated[edgeId] = "success";
              }
            });
            return updated;
          });
        }
      }
    };

    window.addEventListener(
      "chat-execution-start",
      handleChatExecutionStart as EventListener
    );
    window.addEventListener(
      "chat-execution-event",
      handleChatExecutionEvent as EventListener
    );
    window.addEventListener(
      "chat-execution-complete",
      handleChatExecutionComplete as EventListener
    );

    return () => {
      window.removeEventListener(
        "chat-execution-start",
        handleChatExecutionStart as EventListener
      );
      window.removeEventListener(
        "chat-execution-event",
        handleChatExecutionEvent as EventListener
      );
      window.removeEventListener(
        "chat-execution-complete",
        handleChatExecutionComplete as EventListener
      );
    };
  }, [
    nodes,
    setNodeStatus,
    edges,
    setEdgeStatus,
    setActiveEdges,
    setActiveNodes,
  ]);
}

// Webhook execution event listener for real-time UI updates
function useWebhookExecutionListener(
  nodes: Node[],
  setNodeStatus: React.Dispatch<
    React.SetStateAction<Record<string, NodeStatus>>
  >,
  edges: Edge[],
  setEdgeStatus: React.Dispatch<
    React.SetStateAction<Record<string, NodeStatus>>
  >,
  setActiveEdges: React.Dispatch<React.SetStateAction<string[]>>,
  setActiveNodes: React.Dispatch<React.SetStateAction<string[]>>,
  workflowId?: string,
  currentWorkflowId?: string,
  setCurrentExecutionForWorkflow?: (workflowId: string, execution: any) => void
) {
  useEffect(() => {
    // Find all webhook trigger nodes in the workflow
    const webhookNodes = nodes.filter(
      (node) => node.type === "WebhookTrigger" || node.type?.includes("WebhookTrigger")
    );

    if (webhookNodes.length === 0) {
      return; // No webhook nodes, nothing to listen to
    }

    const eventSources: EventSource[] = [];
    const processedEventIds = new Set<string>(); // Event deduplication
    const retryCounts = new Map<string, number>(); // Retry tracking per webhook
    const MAX_RETRIES = 5;
    const INITIAL_RETRY_DELAY = 1000; // 1 second

    // Throttling for UI updates
    let lastUpdateTime = 0;
    const THROTTLE_DELAY = 50; // ms
    const pendingUpdates: Array<() => void> = [];

    // Track webhook execution data for FullscreenNodeModal
    const webhookExecutionData = new Map<string, {
      executionId: string;
      nodeOutputs: Record<string, any>;
      executedNodes: string[];
      sessionId?: string;
      result?: any;
      status: "running" | "completed" | "failed";
      startedAt: string;
      completedAt?: string;
    }>();

    // Get base URL with fallback
    const baseUrl = import.meta.env.VITE_API_BASE_URL;

    // Connect to webhook stream for each webhook node
    webhookNodes.forEach((node) => {
      // Extract webhook_id from node data
      // Check multiple possible locations for webhook_id/path
      let webhookId: string = node.id; // Default fallback

      // 1. Direct webhook_id in node data
      if (node.data?.webhook_id && typeof node.data.webhook_id === 'string') {
        webhookId = node.data.webhook_id;
      }
      // 2. Path property in node data
      else if (node.data?.path && typeof node.data.path === 'string') {
        webhookId = node.data.path;
      }

      if (!webhookId) {
        console.warn(`No webhook_id found for node ${node.id}`);
        return;
      }

      try {
        const streamUrl = `${baseUrl}/${config.API_START}/${config.API_VERSION_ONLY}/webhook-test/${webhookId}/stream`;
        const eventSource = new EventSource(streamUrl);

        eventSource.onerror = (error) => {
          const retryCount = retryCounts.get(webhookId) || 0;

          if (retryCount < MAX_RETRIES) {
            const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCount); // Exponential backoff
            console.warn(
              `⚠️ Webhook stream error for ${webhookId}, retrying in ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRIES})`
            );

            retryCounts.set(webhookId, retryCount + 1);

            // Close and reconnect after delay
            setTimeout(() => {
              eventSource.close();
              // Reconnect will be handled by EventSource automatically
              // But we can also manually reconnect if needed
            }, delay);
          } else {
            console.error(
              `❌ Webhook stream error for ${webhookId}: Max retries reached. Connection failed.`,
              error
            );
            retryCounts.delete(webhookId);
          }
        };

        eventSource.onmessage = async (event) => {
          try {
            const data = JSON.parse(event.data) as WebhookStreamEvent;

            // Handle connection and ping events
            if (data.type === "connected") {
              retryCounts.delete(webhookId); // Reset retry count on successful connection
              return;
            }

            if (data.type === "ping") {
              // Keep-alive ping, no action needed
              return;
            }

            if (data.type === "error") {
              console.error(`❌ Webhook stream error:`, data.error);
              return;
            }

            // Check if this is a webhook execution event
            // Backend already executes the workflow, we just need to process the events for UI updates
            if (data.type === "webhook_execution_event" && data.event) {
              // Event deduplication
              const eventId = `${data.execution_id || 'unknown'}-${data.event.type}-${data.event.node_id || 'unknown'}-${data.timestamp || Date.now()}`;
              if (processedEventIds.has(eventId)) {
                console.warn("⚠️ Duplicate webhook event ignored:", eventId);
                return;
              }

              // Limit processed events to prevent memory issues
              if (processedEventIds.size > 1000) {
                // Clear oldest 500 events
                const eventArray = Array.from(processedEventIds);
                eventArray.slice(0, 500).forEach(id => processedEventIds.delete(id));
              }

              processedEventIds.add(eventId);

              const executionEvent = data.event;
              const eventType = executionEvent.type || executionEvent.event;
              const node_id = executionEvent.node_id;

              // Throttled logging to avoid console spam
              const now = Date.now();
              if (now - lastUpdateTime > 1000) { // Log every second max
                lastUpdateTime = now;
              }

              // Throttled UI update function
              const throttledUpdate = (updateFn: () => void) => {
                const updateNow = Date.now();
                if (updateNow - lastUpdateTime > THROTTLE_DELAY) {
                  updateFn();
                  lastUpdateTime = updateNow;
                  // Process any pending updates
                  while (pendingUpdates.length > 0) {
                    const pending = pendingUpdates.shift();
                    if (pending) pending();
                  }
                } else {
                  pendingUpdates.push(updateFn);
                  // Schedule batch update
                  if (pendingUpdates.length === 1) {
                    setTimeout(() => {
                      const batch = pendingUpdates.splice(0);
                      batch.forEach(fn => fn());
                      lastUpdateTime = Date.now();
                    }, THROTTLE_DELAY);
                  }
                }
              };

              // Track execution data from events
              const executionId = data.execution_id || 'unknown';
              if (!webhookExecutionData.has(executionId)) {
                webhookExecutionData.set(executionId, {
                  executionId,
                  nodeOutputs: {},
                  executedNodes: [],
                  status: "running",
                  startedAt: data.timestamp || new Date().toISOString(),
                });
              }

              const execData = webhookExecutionData.get(executionId)!;

              // Collect node execution data from events
              if (eventType === "node_start" && node_id) {
                // Track node start
                if (!execData.executedNodes.includes(node_id)) {
                  execData.executedNodes.push(node_id);
                }

                // Initialize node output entry
                if (!execData.nodeOutputs[node_id]) {
                  execData.nodeOutputs[node_id] = {
                    inputs: executionEvent.inputs || {},
                    inputs_meta: executionEvent.inputs_meta || {},
                  };
                }
              }

              if (eventType === "node_end" && node_id) {
                // Update node output
                if (execData.nodeOutputs[node_id]) {
                  execData.nodeOutputs[node_id] = {
                    ...execData.nodeOutputs[node_id],
                    output: executionEvent.output || executionEvent.result,
                    outputs: executionEvent.output || executionEvent.result,
                    status: executionEvent.error ? "failed" : "completed",
                  };
                } else {
                  execData.nodeOutputs[node_id] = {
                    inputs: {},
                    output: executionEvent.output || executionEvent.result,
                    outputs: executionEvent.output || executionEvent.result,
                    status: executionEvent.error ? "failed" : "completed",
                  };
                }
              }

              // Handle complete event - save execution to store
              if (eventType === "complete" || eventType === "workflow_complete") {
                execData.status = "completed";
                execData.completedAt = data.timestamp || new Date().toISOString();

                // Extract final result from event
                if (executionEvent.result) {
                  execData.result = executionEvent.result;
                }
                if (executionEvent.node_outputs) {
                  // Merge with collected node outputs
                  execData.nodeOutputs = {
                    ...execData.nodeOutputs,
                    ...executionEvent.node_outputs,
                  };
                }
                if (executionEvent.executed_nodes) {
                  execData.executedNodes = executionEvent.executed_nodes;
                }
                if (executionEvent.session_id) {
                  execData.sessionId = executionEvent.session_id;
                }

                // Save to execution store for FullscreenNodeModal
                if (currentWorkflowId && setCurrentExecutionForWorkflow) {
                  const executionResult = {
                    id: executionId,
                    workflow_id: currentWorkflowId,
                    input_text: data.webhook_payload ? JSON.stringify(data.webhook_payload) : "",
                    result: {
                      result: execData.result,
                      executed_nodes: execData.executedNodes,
                      node_outputs: execData.nodeOutputs,
                      session_id: execData.sessionId,
                      status: "completed" as const,
                    },
                    started_at: execData.startedAt,
                    completed_at: execData.completedAt,
                    status: "completed" as const,
                  };

                  setCurrentExecutionForWorkflow(currentWorkflowId, executionResult);
                }
              }

              // Handle node_start events
              if (eventType === "node_start" && node_id) {
                const actualNode = nodes.find((n) => {
                  if (
                    n.id === node_id ||
                    n.data?.name === node_id ||
                    n.type === node_id
                  ) {
                    return true;
                  }
                  const cleanNodeId = node_id.includes("__")
                    ? node_id.split("__")[0]
                    : node_id.replace(/\-\d+$/, "");
                  if (
                    n.type &&
                    (n.type.includes(cleanNodeId) || cleanNodeId.includes(n.type))
                  ) {
                    return true;
                  }
                  return false;
                });

                if (actualNode) {
                  throttledUpdate(() => {
                    setActiveNodes([actualNode.id]);
                    setNodeStatus((prev) => ({
                      ...prev,
                      [actualNode.id]: "pending",
                    }));

                    const incomingEdges = edges.filter((e) => e.target === actualNode.id);
                    if (incomingEdges.length > 0) {
                      setActiveEdges(incomingEdges.map((e) => e.id));
                      setEdgeStatus((prev) => ({
                        ...prev,
                        ...Object.fromEntries(
                          incomingEdges.map((e) => [e.id, "pending" as const])
                        ),
                      }));
                    }
                  });
                }
              }

              // Handle node_end events
              if (eventType === "node_end" && node_id) {
                const actualNode = nodes.find((n) => {
                  if (
                    n.id === node_id ||
                    n.data?.name === node_id ||
                    n.type === node_id
                  ) {
                    return true;
                  }
                  const cleanNodeId = node_id.includes("__")
                    ? node_id.split("__")[0]
                    : node_id.replace(/\-\d+$/, "");
                  if (
                    n.type &&
                    (n.type.includes(cleanNodeId) || cleanNodeId.includes(n.type))
                  ) {
                    return true;
                  }
                  return false;
                });

                if (actualNode) {
                  const isError = executionEvent.error || executionEvent.status === "error";
                  throttledUpdate(() => {
                    setNodeStatus((prev) => ({
                      ...prev,
                      [actualNode.id]: isError ? "failed" : "success",
                    }));

                    const incomingEdges = edges.filter((e) => e.target === actualNode.id);
                    if (incomingEdges.length > 0) {
                      const edgeStatus: NodeStatus = isError ? "failed" : "success";
                      setEdgeStatus((prev) => ({
                        ...prev,
                        ...Object.fromEntries(
                          incomingEdges.map((e) => [e.id, edgeStatus])
                        ),
                      }));
                    }
                  });
                }
              }

              // Handle workflow complete events
              if (eventType === "complete" || eventType === "workflow_complete") {
                throttledUpdate(() => {
                  setActiveEdges([]);
                  setActiveNodes([]);
                });
              }
            }
          } catch (error) {
            console.error("❌ Error parsing webhook stream event:", error, {
              eventData: event.data?.substring(0, 200), // Log first 200 chars
            });
          }
        };

        eventSources.push(eventSource);
      } catch (error) {
        console.error(`Failed to create EventSource for webhook ${webhookId}:`, error);
      }
    });

    // Cleanup: close all event sources when component unmounts or nodes change
    return () => {
      eventSources.forEach((es) => {
        try {
          es.close();
        } catch (error) {
          console.warn("Error closing EventSource:", error);
        }
      });
      // Clear memory
      processedEventIds.clear();
      retryCounts.clear();
      pendingUpdates.length = 0;
      webhookExecutionData.clear();
    };
  }, [nodes, workflowId, currentWorkflowId, setCurrentExecutionForWorkflow]);
}

interface FlowCanvasWrapperProps {
  workflowId?: string;
}

function FlowCanvasWrapper({ workflowId }: FlowCanvasWrapperProps) {
  return (
    <ReactFlowProvider>
      <FlowCanvas workflowId={workflowId} />
    </ReactFlowProvider>
  );
}
export default FlowCanvasWrapper;