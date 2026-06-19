import React, { useState, useEffect, useRef } from "react";
import {
  Eraser,
  History,
  MessageSquare,
  Maximize2,
  Minimize2,
  RotateCcw,
  Settings2,
  Hammer,
  X,
} from "lucide-react";
import ChatBubble from "../common/ChatBubble";
import { useChatStore } from "~/stores/chat";
import { AIBuilderService } from "~/services/aiBuilderService";
import { getUserCredentials } from "~/services/userCredentialService";

interface ChatComponentProps {
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
  chatHistory: any[];
  chatError: string | null;
  chatLoading: boolean;
  chatThinking: boolean;
  chatInput: string;
  setChatInput: (input: string) => void;
  onSendMessage: () => void;
  onClearChat: () => void;
  onShowHistory: () => void;
  activeChatflowId: string | null;
  currentWorkflow?: any;
  flowData?: any;
  // AI Builder props
  onFlowGenerated?: (flowData: any) => void;
  currentNodes?: any[];
  currentEdges?: any[];
}

export default function ChatComponent({
  chatOpen,
  setChatOpen,
  chatHistory,
  chatError,
  chatLoading,
  chatThinking,
  chatInput,
  setChatInput,
  onSendMessage,
  onClearChat,
  onShowHistory,
  activeChatflowId,
  currentWorkflow,
  flowData,
  onFlowGenerated,
  currentNodes = [],
  currentEdges = [],
}: ChatComponentProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { updateMessage, removeMessage, sendEditedMessage } = useChatStore();

  // ─── Mode State ───
  const [mode, setMode] = useState<"chat" | "builder">("chat");

  // ─── Builder States ───
  const [builderInput, setBuilderInput] = useState("");
  const [builderLoading, setBuilderLoading] = useState(false);
  const [builderHistory, setBuilderHistory] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);
  const [hasBuiltWorkflow, setHasBuiltWorkflow] = useState(false);
  const [rebuildFromScratch, setRebuildFromScratch] = useState(false);

  // ─── Builder Settings States ───
  const [showSettings, setShowSettings] = useState(false);
  const [credentials, setCredentials] = useState<any[]>([]);
  const [selectedCredentialId, setSelectedCredentialId] = useState<string>("");
  const [modelName, setModelName] = useState<string>("gpt-4o");
  const [baseUrl, setBaseUrl] = useState<string>("");

  // ─── Scroll ───
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, chatLoading, builderHistory, builderLoading]);

  useEffect(() => {
    if (chatOpen && !chatLoading && !builderLoading && !editingMessageId) {
      inputRef.current?.focus();
    }
  }, [chatOpen, chatLoading, builderLoading, editingMessageId, mode]);

  // ─── Fetch Credentials when panel opens or mode switches to builder ───
  useEffect(() => {
    if (chatOpen && mode === "builder") {
      getUserCredentials()
        .then((creds) => {
          const apiCreds = creds.filter((c: any) =>
            ["openai", "anthropic", "cohere", "generic_api", "custom"].includes(
              c.service_type
            )
          );
          setCredentials(apiCreds);
          if (apiCreds.length > 0) {
            setSelectedCredentialId((prev) => prev || apiCreds[0].id);
          }
        })
        .catch(console.error);
    }
  }, [chatOpen, mode]);

  // ─── Chat Title ───
  const getChatTitle = () => {
    if (mode === "builder") return "AI Builder";
    if (!activeChatflowId || chatHistory.length === 0) return "New Conversation";
    const firstUserMessage = chatHistory.find((msg) => msg.role === "user");
    if (firstUserMessage) {
      const title = firstUserMessage.content.slice(0, 30);
      return title.length < firstUserMessage.content.length ? title + "..." : title;
    }
    return "New Conversation";
  };

  // ─── Chat Edit Handlers ───
  const handleEditMessage = (messageId: string) => {
    setEditingMessageId(messageId);
  };

  const handleSaveEdit = async (messageId: string, newContent: string) => {
    if (activeChatflowId) {
      const message = chatHistory.find((msg) => msg.id === messageId);
      if (message) {
        setEditingMessageId(null);
        const updatedMessage = { ...message, content: newContent };
        updateMessage(activeChatflowId, updatedMessage);
        const messageIndex = chatHistory.findIndex((msg) => msg.id === messageId);
        const messagesToRemove = chatHistory
          .slice(messageIndex + 1)
          .filter((msg) => msg.role === "assistant")
          .map((msg) => msg.id);
        messagesToRemove.forEach((id) => {
          removeMessage(activeChatflowId!, id);
        });
        if (currentWorkflow && flowData) {
          try {
            await sendEditedMessage(flowData, newContent, activeChatflowId, currentWorkflow.id);
          } catch (error) {
            console.error("Error sending updated message:", error);
          }
        }
      }
    }
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
  };

  const handleDeleteMessage = (messageId: string) => {
    if (activeChatflowId) {
      const message = chatHistory.find((msg) => msg.id === messageId);
      if (message) {
        removeMessage(activeChatflowId, messageId);
        if (message.role === "user") {
          const messageIndex = chatHistory.findIndex((msg) => msg.id === messageId);
          const messagesToRemove = chatHistory
            .slice(messageIndex + 1)
            .filter((msg) => msg.role === "assistant")
            .map((msg) => msg.id);
          messagesToRemove.forEach((id) => {
            removeMessage(activeChatflowId!, id);
          });
        }
      }
    }
  };

  // ─── Builder Handlers ───
  const canvasHasWorkflow =
    currentEdges.length > 0 ||
    currentNodes.some((node) => node.type !== "StartNode");
  const isBuilderEditMode =
    !rebuildFromScratch && (hasBuiltWorkflow || canvasHasWorkflow);

  const handleBuilderGenerate = async (prompt?: string) => {
    const query = prompt || builderInput;
    if (!query.trim()) return;

    if (!selectedCredentialId) {
      setBuilderHistory((prev) => [
        ...prev,
        { role: "user", content: query },
        {
          role: "assistant",
          content:
            "⚠️ Please select an API Credential first. Click the ⚙️ Settings icon in the header to configure your AI provider.",
        },
      ]);
      setBuilderInput("");
      return;
    }

    setBuilderLoading(true);
    setBuilderInput("");
    setBuilderHistory((prev) => [...prev, { role: "user", content: query }]);

    try {
      const buildMode = isBuilderEditMode ? "edit" : "build";
      const existingWorkflow = isBuilderEditMode
        ? { nodes: currentNodes, edges: currentEdges }
        : undefined;

      const result = await AIBuilderService.generateWorkflow(query, {
        credentialId: selectedCredentialId,
        modelName: modelName.trim() || "gpt-4o",
        baseUrl: baseUrl.trim() || undefined,
        mode: buildMode,
        existingWorkflow,
      });

      // Check if the backend flagged this as an invalid/irrelevant request
      if (result.invalid_request) {
        const rejectMsg = result.message || "Your request does not appear to be a workflow edit. Please describe what you want to change.";
        setBuilderHistory((prev) => [
          ...prev,
          { role: "assistant", content: `⚠️ ${rejectMsg}` },
        ]);
      } else {
        const successMsg = isBuilderEditMode
          ? "Workflow updated successfully!"
          : "Workflow created successfully! The nodes have been placed on your canvas.";

        setBuilderHistory((prev) => [...prev, { role: "assistant", content: successMsg }]);
        onFlowGenerated?.(result);
        setHasBuiltWorkflow(true);
        setRebuildFromScratch(false);
      }
    } catch (err: any) {
      console.error(err);
      const errorMsg =
        err.response?.data?.detail || err.message || "Failed to generate workflow";
      setBuilderHistory((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${errorMsg}` },
      ]);
    } finally {
      setBuilderLoading(false);
    }
  };

  const handleRebuild = () => {
    setHasBuiltWorkflow(false);
    setRebuildFromScratch(true);
    setBuilderHistory([
      {
        role: "assistant",
        content: "Rebuild mode activated. Describe the new workflow you want from scratch.",
      },
    ]);
  };

  // ─── Unified Send ───
  const handleUnifiedSend = () => {
    if (mode === "builder") {
      handleBuilderGenerate();
    } else {
      onSendMessage();
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  };

  const currentInput = mode === "builder" ? builderInput : chatInput;
  const setCurrentInput = mode === "builder" ? setBuilderInput : setChatInput;
  const isLoading = mode === "builder" ? builderLoading : chatLoading;

  if (!chatOpen) return null;

  return (
    <div
      className={`fixed bottom-20 right-4 bg-[#18181A] rounded-xl shadow-2xl flex flex-col z-50 animate-slide-up border border-gray-700 transition-all duration-300 ${
        isExpanded
          ? "w-[calc(100vw-2rem)] h-[calc(100vh-6rem)] left-4"
          : "w-148 h-[600px]"
      }`}
    >
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          {mode === "builder" ? (
            <>
              <Hammer className="w-4 h-4 text-orange-400" />
              <span className="font-semibold text-gray-200 text-sm">AI Builder</span>
            </>
          ) : (
            <>
              <MessageSquare className="w-4 h-4 text-blue-400" />
              <span className="font-semibold text-gray-200 text-sm truncate">
                {getChatTitle()}
              </span>
            </>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* Builder Mode Toggle */}
          <button
            onClick={() => {
              setMode(mode === "builder" ? "chat" : "builder");
              setShowSettings(false);
            }}
            className={`p-1.5 rounded transition-all duration-200 flex items-center gap-1 text-xs font-medium ${
              mode === "builder"
                ? "bg-orange-500/20 text-orange-400 border border-orange-500/30"
                : "text-gray-400 hover:text-orange-300 hover:bg-gray-700"
            }`}
            title={mode === "builder" ? "Switch to Chat" : "Switch to AI Builder"}
          >
            <Hammer className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Builder</span>
          </button>

          {/* Settings (Builder only) */}
          {mode === "builder" && (
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`p-1 rounded transition-colors ${
                showSettings
                  ? "text-blue-400 bg-blue-500/10"
                  : "text-gray-400 hover:text-gray-300 hover:bg-gray-700"
              }`}
              title="AI Builder Settings"
            >
              <Settings2 className="w-4 h-4" />
            </button>
          )}

          {/* Rebuild (Builder only) */}
          {mode === "builder" && (
            <button
              onClick={handleRebuild}
              className="text-orange-400 hover:text-orange-300 p-1 rounded hover:bg-gray-700"
              title="Rebuild (Start over)"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}

          {/* Expand/Minimize */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-400 hover:text-gray-300 p-1 rounded hover:bg-gray-700"
            title={isExpanded ? "Minimize" : "Maximize"}
          >
            {isExpanded ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>

          {/* History (Chat only) */}
          {mode === "chat" && (
            <button
              onClick={onShowHistory}
              className="text-gray-400 hover:text-gray-300 p-1 rounded hover:bg-gray-700"
              title="Conversation history"
            >
              <History className="w-4 h-4" />
            </button>
          )}

          {/* Clear */}
          <button
            onClick={() => {
              if (mode === "builder") {
                setBuilderHistory([]);
              } else {
                onClearChat();
              }
            }}
            className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-gray-700"
            title="Clear conversation"
          >
            <Eraser className="w-4 h-4" />
          </button>

          {/* Close */}
          <button
            onClick={() => setChatOpen(false)}
            className="text-gray-400 hover:text-gray-300 p-1 rounded hover:bg-gray-700"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ─── Settings Popover (Builder Mode) ─── */}
      {mode === "builder" && showSettings && (
        <div className="px-4 py-3 border-b border-gray-700 bg-gray-800/50 space-y-3 animate-in">
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              AI Provider Credential <span className="text-red-400">*</span>
            </label>
            <select
              title="API Credential"
              className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm text-gray-200 outline-none focus:border-blue-500"
              value={selectedCredentialId}
              onChange={(e) => setSelectedCredentialId(e.target.value)}
            >
              <option value="" disabled>
                Select a Credential...
              </option>
              {credentials.map((c: any) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.service_type})
                </option>
              ))}
            </select>
            {credentials.length === 0 && (
              <p className="text-xs text-orange-400 mt-1">
                Go to Settings → Credentials to add an API key first.
              </p>
            )}
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Model Name</label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g. gpt-4o, anthropic/claude-3.5-sonnet"
              className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm text-gray-200 outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Base URL (OpenRouter / Custom Endpoints)
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="e.g. https://openrouter.ai/api/v1"
              className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm text-gray-200 outline-none focus:border-blue-500"
            />
          </div>
        </div>
      )}

      {/* ─── Messages Area ─── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Builder Error - shown inline in chat bubbles only */}

        {/* Chat Error */}
        {mode === "chat" && chatError && (
          <div className="text-xs text-red-400">{chatError}</div>
        )}

        {/* Builder Empty State */}
        {mode === "builder" && builderHistory.length === 0 && (
          <div className="text-center text-gray-400 mt-10">
            <p className="mb-4">Describe the workflow you want to build.</p>
            <div className="flex flex-wrap justify-center gap-2">
              <button
                onClick={() => handleBuilderGenerate("Create a conversational AI agent")}
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-full text-xs font-medium transition-colors"
                disabled={builderLoading}
              >
                Conversational Agent
              </button>
              <button
                onClick={() =>
                  handleBuilderGenerate("Build a webhook trigger that saves data")
                }
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-full text-xs font-medium transition-colors"
                disabled={builderLoading}
              >
                Webhook Data Saver
              </button>
            </div>
          </div>
        )}

        {/* Builder Messages */}
        {mode === "builder" &&
          builderHistory.map((msg, i) => (
            <ChatBubble
              key={`builder-${i}`}
              from={msg.role}
              message={msg.content}
              userInitial={msg.role === "user" ? "U" : undefined}
            />
          ))}

        {/* Chat Messages */}
        {mode === "chat" &&
          [...chatHistory]
            .sort((a, b) => {
              const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
              const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
              return timeA - timeB;
            })
            .map((msg, i) => (
              <ChatBubble
                key={msg.id || i}
                from={msg.role === "user" ? "user" : "assistant"}
                message={msg.content}
                userInitial={msg.role === "user" ? "U" : undefined}
                messageId={msg.id}
                onEdit={handleEditMessage}
                onDelete={handleDeleteMessage}
                isEditing={editingMessageId === msg.id}
                onSaveEdit={handleSaveEdit}
                onCancelEdit={handleCancelEdit}
              />
            ))}

        {/* Loading indicators */}
        {mode === "builder" && builderLoading && (
          <ChatBubble
            from="assistant"
            message={isBuilderEditMode ? "Editing workflow..." : "Building workflow..."}
            loading
          />
        )}
        {mode === "chat" && chatThinking && (
          <ChatBubble from="assistant" message="" loading />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ─── Input Area ─── */}
      <div className="p-3 border-t border-gray-700 flex gap-2">
        <input
          ref={inputRef}
          type="text"
          className="flex-1 border rounded-lg px-3 py-2 text-sm border-gray-600 bg-gray-800 text-gray-100 placeholder-gray-400 focus:outline-none focus:border-blue-400"
          placeholder={
            mode === "builder"
              ? isBuilderEditMode
                ? "Describe an adjustment... (e.g., change agent's system prompt)"
                : "e.g. Create a simple chatbot..."
              : "Write your message..."
          }
          value={currentInput}
          onChange={(e) => setCurrentInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleUnifiedSend();
          }}
          disabled={isLoading}
        />
        <button
          onClick={handleUnifiedSend}
          className={`text-white px-4 py-2 rounded-lg disabled:opacity-50 ${
            mode === "builder"
              ? "bg-orange-600 hover:bg-orange-700"
              : "bg-blue-600 hover:bg-blue-700"
          }`}
          disabled={isLoading || !currentInput.trim()}
        >
          {mode === "builder"
            ? isBuilderEditMode
              ? "Edit"
              : "Build"
            : "Send"}
        </button>
      </div>
    </div>
  );
}
