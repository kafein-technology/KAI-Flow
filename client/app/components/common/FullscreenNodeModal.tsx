import React, { useState, useEffect } from "react";
import {
  X,
  Settings,
  Info,
  Save,
  ArrowLeft,
  ArrowRight,
  FileText,
  Hash,
  Calendar,
  User,
  Globe,
  Mail,
  Key,
  Database,
  Play,
} from "~/icons/index";
import { motion, AnimatePresence } from "motion/react";
import { enqueueSnackbar } from "notistack";
import DataDisplayModes from "./DataDisplayModes";

interface NodeInput {
  name: string;
  type: string;
  description: string;
  required: boolean;
  is_connection: boolean;
  default?: any;
  validation_rules?: any;
  ui_config?: any;
}

interface NodeOutput {
  name: string;
  type: string;
  description: string;
  format?: string;
  output_schema?: any;
}

interface NodeMetadata {
  name: string;
  description: string;
  display_name?: string;
  icon?: string;
  color?: string;
  category: string;
  node_type: string;
  inputs: NodeInput[];
  outputs: NodeOutput[];
  version?: string;
  tags?: string[];
  documentation_url?: string;
  examples?: any[];
}

interface FullscreenNodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  nodeMetadata: NodeMetadata;
  configData: any;
  onSave: (values: any) => void;
  onExecute?: () => void; // New execute function
  ConfigComponent: React.ComponentType<{
    configData: any;
    onSave: (values: any) => void;
    onCancel: () => void;
  }>;
  executionData?: {
    nodeId: string;
    inputs?: Record<string, any>;
    inputs_meta?: Record<
      string,
      | {
        sourceNodeId: string;
        sourceNodeName?: string;
        sourceNodeAlias?: string;
        sourceHandle?: string;
      }
      | {
        sourceNodeId: string;
        sourceNodeName?: string;
        sourceNodeAlias?: string;
        sourceHandle?: string;
      }[]
    >;
    outputs?: Record<string, any>;
    status?: "completed" | "failed" | "running" | "pending";
  };
}

export default function FullscreenNodeModal({
  isOpen,
  onClose,
  nodeMetadata,
  configData,
  onSave,
  onExecute,
  ConfigComponent,
  executionData,
}: FullscreenNodeModalProps) {
  const [configValues, setConfigValues] = useState(configData);
  const [nodeAlias, setNodeAlias] = useState(
    configData?.name || nodeMetadata.display_name || nodeMetadata.name
  );
  const [nodeAliasError, setNodeAliasError] = useState<string | null>(null);

  // Validate node alias for Jinja template compatibility
  // Rules: letters, numbers, and underscores only; must start with a letter; cannot be reserved keywords
  // Note: Uppercase letters are allowed but will be auto-converted to lowercase when saving
  const validateNodeAlias = (name: string): string | null => {
    if (!name || name.trim() === "") {
      return "Node name is required";
    }

    // Check for reserved keywords that conflict with template context
    const reservedKeywords = ["input"];
    if (reservedKeywords.includes(name.toLowerCase())) {
      return `'${name}' is a reserved keyword and cannot be used as a node name`;
    }

    // Check for invalid characters (allow a-z, A-Z, 0-9, underscore - case will be normalized later)
    const hasSpace = /\s/.test(name);
    const hasSpecialChars = /[^a-zA-Z0-9_]/.test(name);
    const startsWithNumber = /^[0-9]/.test(name);

    if (hasSpace || hasSpecialChars || startsWithNumber) {
      let suggestion = name.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
      if (/^[0-9]/.test(suggestion)) {
        suggestion = "n_" + suggestion;
      }
      return `Invalid format. For template {{${name}}}, use: {{${suggestion || "node_name"}}}`;
    }

    return null;
  };

  const handleNodeAliasChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setNodeAlias(value);
    setNodeAliasError(validateNodeAlias(value));
  };

  // Helper function to filter out metadata and system fields from node data
  const filterNodeData = (data: any, isOutput: boolean = false): any => {
    if (!data || typeof data !== "object") return data;

    // For OpenAI nodes, show only important fields
    const isOpenAINode =
      data.model ||
      data.openai_api_key ||
      data.estimatedTokens !== undefined ||
      data.tokenUsage ||
      data.generations ||
      data.model_name;

    if (isOpenAINode) {
      if (isOutput) {
        // For OpenAI output, show response metadata
        const keepFields = [
          "response",
          "text",
          "content",
          "tokenUsage",
          "completionTokens",
          "promptTokens",
          "totalTokens",
          "model_name",
          "finish_reason",
          "generations",
        ];
        const filtered: any = {};

        Object.entries(data).forEach(([key, value]) => {
          if (keepFields.includes(key)) {
            filtered[key] = value;
          } else if (key === "generationInfo" && typeof value === "object" && value !== null) {
            // Extract important fields from generationInfo
            const genInfo: any = {};
            const valueObj = value as any;
            if (valueObj.prompt !== undefined) genInfo.promptTokens = valueObj.prompt;
            if (valueObj.completion !== undefined)
              genInfo.completionTokens = valueObj.completion;
            if (valueObj.finish_reason)
              genInfo.finish_reason = valueObj.finish_reason;
            if (valueObj.model_name) genInfo.model_name = valueObj.model_name;
            if (Object.keys(genInfo).length > 0) {
              filtered.generationInfo = genInfo;
            }
          } else if (
            key === "generations" &&
            Array.isArray(value) &&
            value.length > 0
          ) {
            // Extract text and generation info from generations array
            const generation = value[0];
            if (generation.text) {
              filtered.text = generation.text;
            }
            if (generation.generationInfo) {
              const genInfo = generation.generationInfo;
              filtered.tokenUsage = {
                promptTokens: genInfo.prompt || 0,
                completionTokens: genInfo.completion || 0,
                totalTokens: (genInfo.prompt || 0) + (genInfo.completion || 0),
              };
              filtered.model_name = genInfo.model_name;
              filtered.finish_reason = genInfo.finish_reason;
            }
          }
        });

        return filtered;
      } else {
        // For OpenAI input, keep only these important fields
        const keepFields = [
          "messages",
          "model",
          "max_tokens",
          "timeout",
          "max_retries",
          "estimatedTokens",
        ];
        const filtered: any = {};

        Object.entries(data).forEach(([key, value]) => {
          if (keepFields.includes(key)) {
            filtered[key] = value;
          }
        });

        return filtered;
      }
    }

    // For other nodes, use general filtering
    const excludeFields = [
      // Metadata fields
      "icon",
      "name",
      "color",
      "inputs",
      "outputs",
      "metadata",
      "description",
      "displayName",
      "version",
      "category",
      "examples",
      "node_type",
      "documentation_url",
      "tags",

      // System/Internal fields
      "lc",
      "type",
      "id",
      "configuration",
      "baseURL",
      "fetchOptions",
      "model_kwargs",
      "stream",
      "streaming",
      "callbacks",
      "options",
      "isConfigMode",
      "credential_id",

      // LangChain internal fields
      "_type",
      "_name",
      "_id",
      "_kwargs",
      "_input_keys",
      "_output_keys",
      "_memory_keys",
      "_chain_type",
      "client",
      "async_client",
      "openai_api_key",
      "openai_api_base",
      "openai_organization",
      "openai_proxy",
      "request_timeout",
      "n",
      "logit_bias",
      "user",
      "stop",
    ];

    const filtered: any = {};
    Object.entries(data).forEach(([key, value]) => {
      if (!excludeFields.includes(key)) {
        filtered[key] = value;
      }
    });

    return filtered;
  };

  // Helper function to get user-friendly labels for data keys
  const getDataLabel = (key: string): string => {
    const labelMap: Record<string, string> = {
      // Common input/output keys
      text: "Text Content",
      query: "Search Query",
      content: "Content",
      message: "Message",
      prompt: "Prompt",
      response: "Response",
      result: "Result",
      output: "Output",
      input: "Input",
      data: "Data",
      documents: "Documents",
      context: "Context",
      summary: "Summary",
      answer: "Answer",
      question: "Question",
      url: "Web Address",
      urls: "Web Addresses",
      links: "Links",
      title: "Title",
      description: "Description",
      keywords: "Keywords",
      tags: "Tags",
      metadata: "Metadata",
      timestamp: "Timestamp",
      date: "Date",
      time: "Time",
      id: "ID",
      user_id: "User ID",
      session_id: "Session ID",
      api_key: "API Key",
      token: "Token",
      tokenUsage: "Token Usage",
      promptTokens: "Prompt Tokens",
      completionTokens: "Completion Tokens",
      totalTokens: "Total Tokens",
      finish_reason: "Finish Reason",
      model_name: "Model Name",
      status: "Status",
      count: "Count",
      length: "Length",
      size: "Size",
      score: "Score",
      confidence: "Confidence",
      similarity: "Similarity",
      embedding: "Vector Embedding",
      embeddings: "Vector Embeddings",
      chunks: "Text Chunks",
      chunk: "Text Chunk",
      search_results: "Search Results",
      filtered_results: "Filtered Results",
      ranked_results: "Ranked Results",
      top_results: "Top Results",
      relevant_docs: "Relevant Documents",
      source: "Source",
      sources: "Sources",
      reference: "Reference",
      references: "References",
    };

    return (
      labelMap[key.toLowerCase()] ||
      key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
    );
  };

  // Helper function to get appropriate icon for data type
  const getDataIcon = (key: string, value: any) => {
    const keyLower = key.toLowerCase();

    if (
      keyLower.includes("text") ||
      keyLower.includes("content") ||
      keyLower.includes("message")
    ) {
      return <FileText className="w-4 h-4" />;
    }
    if (keyLower.includes("url") || keyLower.includes("link")) {
      return <Globe className="w-4 h-4" />;
    }
    if (keyLower.includes("email") || keyLower.includes("mail")) {
      return <Mail className="w-4 h-4" />;
    }
    if (keyLower.includes("user") || keyLower.includes("person")) {
      return <User className="w-4 h-4" />;
    }
    if (keyLower.includes("date") || keyLower.includes("time")) {
      return <Calendar className="w-4 h-4" />;
    }
    if (
      keyLower.includes("key") ||
      keyLower.includes("token") ||
      keyLower.includes("auth")
    ) {
      return <Key className="w-4 h-4" />;
    }
    if (
      keyLower.includes("data") ||
      keyLower.includes("result") ||
      keyLower.includes("document")
    ) {
      return <Database className="w-4 h-4" />;
    }
    if (typeof value === "number") {
      return <Hash className="w-4 h-4" />;
    }

    return <FileText className="w-4 h-4" />;
  };

  // Helper function to mask sensitive values
  const maskSensitiveValue = (key: string, value: any): any => {
    const keyLower = key.toLowerCase();
    const sensitivePatterns = [
      "api_key",
      "apikey",
      "api-key",
      "password",
      "passwd",
      "pwd",
      "secret",
      "token",
      "auth",
      "credential",
      "private_key",
      "connection_string",
      "database_url",
      "openai_api_key",
      "tavily_api_key",
      "cohere_api_key",
      "anthropic_api_key",
    ];

    // Check if key matches sensitive patterns
    if (sensitivePatterns.some((pattern) => keyLower.includes(pattern))) {
      if (typeof value === "string" && value) {
        // Show first 4 and last 4 characters with asterisks in between
        if (value.length <= 8) {
          return (
            value.substring(0, 2) + "****" + value.substring(value.length - 2)
          );
        } else {
          return (
            value.substring(0, 4) + "****" + value.substring(value.length - 4)
          );
        }
      }
      return "[PROTECTED]";
    }

    return value;
  };

  // Helper function to format values in a user-friendly way
  const formatValue = (value: any, key: string = ""): string => {
    // First mask sensitive data
    const maskedValue = maskSensitiveValue(key, value);

    if (maskedValue === null || maskedValue === undefined) {
      return "Empty";
    }

    if (typeof maskedValue === "boolean") {
      return maskedValue ? "True" : "False";
    }

    if (typeof maskedValue === "number") {
      return maskedValue.toLocaleString("en-US");
    }

    if (typeof maskedValue === "string") {
      // If it's a URL
      if (
        maskedValue.startsWith("http://") ||
        maskedValue.startsWith("https://")
      ) {
        return maskedValue.length > 50
          ? maskedValue.substring(0, 50) + "..."
          : maskedValue;
      }

      // If it's too long, truncate
      if (maskedValue.length > 200) {
        return maskedValue.substring(0, 200) + "...";
      }

      return maskedValue;
    }

    if (Array.isArray(maskedValue)) {
      return `${maskedValue.length} items`;
    }

    if (typeof maskedValue === "object") {
      // Special handling for tokenUsage object
      if (
        key.toLowerCase().includes("tokenusage") ||
        key.toLowerCase().includes("token_usage")
      ) {
        if (maskedValue.totalTokens !== undefined) {
          return `${maskedValue.totalTokens} total (${maskedValue.promptTokens || 0
            } prompt + ${maskedValue.completionTokens || 0} completion)`;
        }
      }

      const keys = Object.keys(maskedValue);
      return `${keys.length} fields`;
    }

    return String(maskedValue);
  };

  // Helper function to get a description for the data
  const getDataDescription = (key: string, value: any): string => {
    const keyLower = key.toLowerCase();

    if (Array.isArray(value)) {
      return `Contains ${value.length} items`;
    }

    if (typeof value === "object" && value !== null) {
      const keys = Object.keys(value);
      return `Contains ${keys.length} fields`;
    }

    if (typeof value === "string") {
      if (keyLower.includes("url") || keyLower.includes("link")) {
        return "Web address";
      }
      if (keyLower.includes("email")) {
        return "Email address";
      }
      if (value.length > 100) {
        return "Long text content";
      }
      return "Text data";
    }

    if (typeof value === "number") {
      return "Numeric data";
    }

    return "Data value";
  };

  useEffect(() => {
    setConfigValues(configData);
    setNodeAlias(
      configData?.name || nodeMetadata.display_name || nodeMetadata.name
    );
  }, [configData, nodeMetadata.display_name, nodeMetadata.name]);

  const handleSave = (values: any) => {
    try {
      // Validate node alias before saving
      const validationError = validateNodeAlias(nodeAlias);
      if (validationError) {
        enqueueSnackbar(validationError, {
          variant: "warning",
          autoHideDuration: 4000,
          anchorOrigin: {
            vertical: "top",
            horizontal: "right",
          },
        });
        return; // Don't save if validation fails
      }

      const finalValues = { ...values, name: nodeAlias };
      setConfigValues(finalValues);
      onSave(finalValues);
      enqueueSnackbar("Node configuration saved successfully!", {
        variant: "success",
        autoHideDuration: 3000,
        anchorOrigin: {
          vertical: "top",
          horizontal: "right",
        },
      });
      onClose();
    } catch (error) {
      console.error("Error saving configuration:", error);
      enqueueSnackbar("Failed to save node configuration", {
        variant: "error",
        autoHideDuration: 4000,
        anchorOrigin: {
          vertical: "top",
          horizontal: "right",
        },
      });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm"
        onKeyDown={handleKeyDown}
        tabIndex={-1}
      >
        <div className="w-full h-full flex flex-col bg-gray-900">
          {/* Header */}
          <motion.div
            initial={{ y: -50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="flex items-center justify-between p-6 border-b border-gray-700 bg-gray-800"
          >
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                {nodeMetadata.icon && (
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <Settings className="w-5 h-5 text-white" />
                  </div>
                )}
                <div>
                  <h1 className="text-xl font-bold text-white">
                    {nodeMetadata.display_name || nodeMetadata.name}
                  </h1>
                  <p className="text-sm text-gray-400">
                    {nodeMetadata.category}
                  </p>
                  <div className="mt-3">
                    <label className="block text-xs text-gray-400 mb-1">
                      Specify the node name for using node output.
                    </label>
                    <input
                      className={`w-64 px-2 py-1 rounded bg-gray-900 border text-sm text-gray-100 focus:outline-none focus:ring-1 ${nodeAliasError
                        ? "border-yellow-500 focus:ring-yellow-500"
                        : "border-gray-700 focus:ring-blue-500"
                        }`}
                      value={nodeAlias}
                      onChange={handleNodeAliasChange}
                      placeholder={
                        nodeMetadata.display_name || nodeMetadata.name
                      }
                    />
                    {nodeAliasError && (
                      <div className="mt-1 text-xs text-yellow-400">
                        {nodeAliasError}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="px-3 py-1 rounded-full bg-gray-700 text-xs text-gray-300">
                {nodeMetadata.node_type}
              </div>
              {onExecute && nodeMetadata.node_type === "processor" && (
                <button
                  onClick={onExecute}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors"
                  title="Execute this processor node"
                >
                  <Play className="w-4 h-4" />
                  Execute
                </button>
              )}
              <button
                onClick={onClose}
                className="p-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
              >
                <X className="w-5 h-5 text-white" />
              </button>
            </div>
          </motion.div>

          {/* Content Area - 3 Column Layout */}
          <div className="flex-1 flex overflow-hidden">
            {/* Left Column - Input Data */}
            <motion.div
              initial={{ x: -50, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="w-1/3 bg-gray-850 border-r border-gray-700 overflow-y-auto"
            >
              <div className="p-4">
                <div className="flex items-center gap-3 mb-6">
                  <ArrowRight className="w-5 h-5 text-blue-400" />
                  <h2 className="text-lg font-semibold text-white">
                    Input Data
                  </h2>
                </div>

                {/* Execution Data Section */}
                {executionData?.inputs &&
                  Object.keys(executionData.inputs).length > 0 ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm mb-4">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      <span className="text-green-400 font-medium">
                        Live Data
                      </span>
                      <div className="text-xs text-gray-500">
                        • Real-time workflow data
                      </div>
                    </div>

                    <div className="space-y-4">
                      {Object.entries(executionData.inputs).flatMap(
                        ([key, rawValue]) => {
                          const valuesArray = Array.isArray(rawValue)
                            ? rawValue
                            : [rawValue];
                          const rawMeta = executionData.inputs_meta?.[key];
                          const metaArray = Array.isArray(rawMeta)
                            ? rawMeta
                            : rawMeta
                              ? [rawMeta]
                              : [];

                          return valuesArray.map((value, index) => {
                            const sourceMeta = metaArray[index] || metaArray[0];
                            const label =
                              valuesArray.length > 1
                                ? `${getDataLabel(key)} [${index + 1}]`
                                : getDataLabel(key);

                            return (
                              <div
                                key={`${key}-${index}`}
                                className="bg-gradient-to-r from-gray-800 to-gray-800/50 rounded-xl p-4 border border-gray-700/50"
                              >
                                {/* Header with icon and user-friendly label */}
                                <div className="flex items-center gap-3 mb-3">
                                  <div className="p-2 bg-blue-600/20 text-blue-400 rounded-lg">
                                    {getDataIcon(key, value)}
                                  </div>
                                  <div className="flex-1">
                                    <div className="text-sm font-medium text-blue-300">
                                      {label}
                                    </div>
                                    <div className="text-xs text-gray-400">
                                      {getDataDescription(key, value)}
                                    </div>
                                    {sourceMeta && (
                                      <div className="mt-1 text-[10px] text-gray-500">
                                        From:{" "}
                                        {sourceMeta.sourceNodeAlias ||
                                          sourceMeta.sourceNodeName ||
                                          sourceMeta.sourceNodeId}
                                        {sourceMeta.sourceHandle && (
                                          <>
                                            {" "}
                                            · handle: {sourceMeta.sourceHandle}
                                          </>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                  <div className="text-xs text-gray-500 bg-gray-700/50 px-2 py-1 rounded">
                                    input
                                  </div>
                                </div>

                                {/* Value display */}
                                {value && typeof value === "object" && value._placeholder ? (
                                  <div className="bg-yellow-900/20 rounded-lg p-3 border border-yellow-500/30">
                                    <div className="flex items-center gap-2">
                                      <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
                                      <div className="text-sm text-yellow-200">
                                        {value.message || "Waiting for execution"}
                                      </div>
                                    </div>
                                  </div>
                                ) : typeof value === "object" && value !== null ? (
                                  <DataDisplayModes
                                    data={maskSensitiveValue(key, value)}
                                    className="mt-2"
                                    defaultMode="schema"
                                  />
                                ) : (
                                  <div className="bg-gray-900/80 rounded-lg p-3 border border-gray-700/30">
                                    <div className="text-sm text-gray-100 break-words">
                                      {formatValue(value, key)}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          });
                        }
                      )}
                    </div>

                    {/* Context Variables */}
                    <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-600/30">
                      <div className="flex items-center gap-2 mb-3">
                        <Info className="w-4 h-4 text-blue-400" />
                        <div className="text-sm font-medium text-gray-300">
                          Execution Info
                        </div>
                      </div>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between items-center">
                          <span className="text-gray-400">Execution Time:</span>
                          <span className="text-blue-400 font-mono text-xs">
                            {new Date().toLocaleString("en-US")}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-gray-400">Mode:</span>
                          <span className="text-blue-400 bg-blue-400/10 px-2 py-1 rounded text-xs">
                            Development
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-blue-500/20 to-blue-600/20 rounded-full flex items-center justify-center border border-blue-500/30">
                      <ArrowRight className="w-8 h-8 text-blue-400" />
                    </div>
                    <div className="text-lg font-medium text-white mb-2">
                      {executionData?.status === "running"
                        ? "Processing..."
                        : "No Input Data Yet"}
                    </div>
                    <div className="text-sm text-gray-400 max-w-48 mx-auto">
                      {executionData?.status === "running"
                        ? "Workflow is running, input data is being prepared"
                        : "When you execute the workflow, data flowing into this node will appear here"}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>

            {/* Center Column - Configuration */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="flex-1 overflow-y-auto bg-gray-900"
            >
              <div className="h-full flex flex-col">
                <div className="p-4 border-b border-gray-700">
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Settings className="w-5 h-5 text-green-400" />
                    Node Configuration
                  </h2>
                </div>
                <div className="flex-1 p-3 overflow-y-auto">
                  <div className="max-w-full">
                    <ConfigComponent
                      configData={configValues}
                      onSave={handleSave}
                      onCancel={onClose}
                    />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Right Column - Output Data */}
            <motion.div
              initial={{ x: 50, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="w-1/3 bg-gray-850 border-l border-gray-700 overflow-y-auto"
            >
              <div className="p-4">
                <div className="flex items-center gap-3 mb-6">
                  <ArrowLeft className="w-5 h-5 text-purple-400" />
                  <h2 className="text-lg font-semibold text-white">
                    Output Data
                  </h2>
                </div>

                {/* Execution Output Section */}
                {executionData?.outputs ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm mb-4">
                      <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
                      <span className="text-purple-400 font-medium">
                        Generated
                      </span>
                      <div className="text-xs text-gray-500">
                        • Processing completed, result ready
                      </div>
                    </div>

                    <div className="space-y-4">
                      {typeof executionData.outputs === "object" &&
                        executionData.outputs !== null ? (
                        Object.entries(
                          filterNodeData(executionData.outputs, true)
                        ).map(([key, value]) => (
                          <div
                            key={key}
                            className="bg-gradient-to-r from-purple-900/20 to-blue-900/20 rounded-xl p-4 border border-purple-500/30"
                          >
                            {/* Header with icon and user-friendly label */}
                            <div className="flex items-center gap-3 mb-3">
                              <div className="p-2 bg-purple-600/20 text-purple-400 rounded-lg">
                                {getDataIcon(key, value)}
                              </div>
                              <div className="flex-1">
                                <div className="text-sm font-medium text-purple-300">
                                  {getDataLabel(key)}
                                </div>
                                <div className="text-xs text-gray-400">
                                  {getDataDescription(key, value)}
                                </div>
                              </div>
                              <div className="text-xs text-gray-500 bg-gray-700/50 px-2 py-1 rounded">
                                çıkış
                              </div>
                            </div>

                            {/* Value display */}
                            {value && typeof value === "object" && value._placeholder ? (
                              <div className="bg-yellow-900/20 rounded-lg p-3 border border-yellow-500/30">
                                <div className="flex items-center gap-2">
                                  <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
                                  <div className="text-sm text-yellow-200">
                                    {value.message || "Waiting for execution"}
                                  </div>
                                </div>
                              </div>
                            ) : typeof value === "object" && value !== null ? (
                              <DataDisplayModes
                                data={maskSensitiveValue(key, value)}
                                className="mt-2"
                                defaultMode="schema"
                              />
                            ) : (
                              <div className="bg-gray-900/80 rounded-lg p-3 border border-gray-700/30">
                                <div className="text-sm text-gray-100 break-words">
                                  {formatValue(value, key)}
                                </div>
                                <button
                                  onClick={() =>
                                    navigator.clipboard.writeText(
                                      String(maskSensitiveValue(key, value))
                                    )
                                  }
                                  className="mt-2 text-xs text-purple-400 hover:text-purple-300 transition-colors bg-purple-600/10 px-2 py-1 rounded"
                                >
                                  Copy
                                </button>
                              </div>
                            )}
                          </div>
                        ))
                      ) : (
                        // Single output value
                        <div className="bg-gradient-to-r from-purple-900/20 to-blue-900/20 rounded-xl p-4 border border-purple-500/30">
                          {/* Header with icon and user-friendly label */}
                          <div className="flex items-center gap-3 mb-3">
                            <div className="p-2 bg-purple-600/20 text-purple-400 rounded-lg">
                              {getDataIcon("result", executionData.outputs)}
                            </div>
                            <div className="flex-1">
                              <div className="text-sm font-medium text-purple-300">
                                {getDataLabel("result")}
                              </div>
                              <div className="text-xs text-gray-400">
                                {getDataDescription(
                                  "result",
                                  executionData.outputs
                                )}
                              </div>
                            </div>
                            <div className="text-xs text-gray-500 bg-gray-700/50 px-2 py-1 rounded">
                              output
                            </div>
                          </div>

                          {/* Value display */}
                          {typeof executionData.outputs === "object" && executionData.outputs !== null ? (
                            <DataDisplayModes
                              data={maskSensitiveValue("result", executionData.outputs)}
                              className="mt-2"
                              defaultMode="schema"
                            />
                          ) : (
                            <div className="bg-gray-900/80 rounded-lg p-3 border border-gray-700/30">
                              <div className="text-sm text-gray-100 break-words">
                                {formatValue(executionData.outputs, "result")}
                              </div>
                              <button
                                onClick={() =>
                                  navigator.clipboard.writeText(
                                    String(
                                      maskSensitiveValue(
                                        "result",
                                        executionData.outputs
                                      )
                                    )
                                  )
                                }
                                className="mt-2 text-xs text-purple-400 hover:text-purple-300 transition-colors bg-purple-600/10 px-2 py-1 rounded"
                              >
                                Copy
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-purple-500/20 to-purple-600/20 rounded-full flex items-center justify-center border border-purple-500/30">
                      <ArrowLeft className="w-8 h-8 text-purple-400" />
                    </div>
                    <div className="text-lg font-medium text-white mb-2">
                      {executionData?.status === "running"
                        ? "Processing..."
                        : "No Output Data Yet"}
                    </div>
                    <div className="text-sm text-gray-400 max-w-48 mx-auto">
                      {executionData?.status === "running"
                        ? "Node is processing, result being prepared"
                        : "When you execute the workflow, results generated by this node will appear here"}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          </div>

          {/* Footer */}
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="flex items-center justify-between p-6 border-t border-gray-700 bg-gray-800"
          >
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <span>Node Type: {nodeMetadata.node_type}</span>
              <span>•</span>
              <span>Category: {nodeMetadata.category}</span>
              {nodeMetadata.version && (
                <>
                  <span>•</span>
                  <span>Version: {nodeMetadata.version}</span>
                </>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  // Find the form within the config component container more specifically
                  const configContainer = document.querySelector(
                    ".flex-1.p-3.overflow-y-auto"
                  );
                  const configForm =
                    configContainer?.querySelector("form") ||
                    document.querySelector("form");

                  if (configForm) {
                    console.log("Form found, submitting...");
                    enqueueSnackbar("Saving configuration...", {
                      variant: "info",
                      autoHideDuration: 1500,
                      anchorOrigin: {
                        vertical: "top",
                        horizontal: "right",
                      },
                    });
                    configForm.requestSubmit();
                  } else {
                    console.error("No form found - checking for submit button");
                    // Fallback: look for submit button
                    const submitButton = document.querySelector(
                      "button[type='submit']"
                    );
                    if (submitButton) {
                      console.log("Submit button found, clicking...");
                      enqueueSnackbar("Saving configuration...", {
                        variant: "info",
                        autoHideDuration: 1500,
                        anchorOrigin: {
                          vertical: "top",
                          horizontal: "right",
                        },
                      });
                      (submitButton as HTMLButtonElement).click();
                    } else {
                      console.error("Neither form nor submit button found");
                      enqueueSnackbar("Unable to save - no form found", {
                        variant: "error",
                        autoHideDuration: 4000,
                        anchorOrigin: {
                          vertical: "top",
                          horizontal: "right",
                        },
                      });
                    }
                  }
                }}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Save Changes
              </button>
            </div>
          </motion.div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
