import React, { useState, useEffect, useRef } from "react";
import {
  Eraser,
  History,
  MessageSquare,
  Maximize2,
  Minimize2,
  RotateCcw,
  Settings2,
  Sparkles,
  X,
  ChevronDown,
  ArrowLeft,
  Plus,
  Trash2,
  Clock,
} from "lucide-react";
import ChatBubble from "../common/ChatBubble";
import { useChatStore } from "~/stores/chat";
import { AIBuilderService } from "~/services/aiBuilderService";
import { getUserCredentials, getUserCredentialById } from "~/services/userCredentialService";
import { getWorkflowChats } from "~/services/chatService";
import { v4 as uuidv4 } from "uuid";
import type { ChatMessage } from "~/types/api";
import CredentialSelector from "../credentials/CredentialSelector";

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
  activeChatflowId: string | null;
  currentWorkflow?: any;
  flowData?: any;
  // KAI Assistant props
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
  const {
    chats,
    setActiveChatflowId,
    fetchWorkflowChats,
    clearMessages,
    clearBuilderMessages,
    builderChats,
    activeBuilderChatflowId,
    setActiveBuilderChatflowId,
    fetchWorkflowBuilderChats,
    fetchBuilderChatMessages,
    addBuilderMessage,
    updateMessage,
    removeMessage,
    sendEditedMessage
  } = useChatStore();

  const hasInitialLoaded = useRef(false);

  // ─── Mode State ───
  const [mode, setMode] = useState<"chat" | "builder">("chat");

  // ─── Builder States ───
  const [builderInput, setBuilderInput] = useState("");
  const [builderLoading, setBuilderLoading] = useState(false);
  const [rebuildFromScratch, setRebuildFromScratch] = useState(false);
  const [showHistoryView, setShowHistoryView] = useState(false);

  // ─── Builder Settings States ───
  const [showSettings, setShowSettings] = useState(false);
  const [credentials, setCredentials] = useState<any[]>([]);
  const [selectedCredentialId, setSelectedCredentialId] = useState<string>("");
  const [verifySsl, setVerifySsl] = useState<boolean>(true);
  const [extraBodyParams, setExtraBodyParams] = useState<string>("");
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // ─── Scroll ───
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, chatLoading, builderChats, activeBuilderChatflowId, builderLoading]);

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
            ["openai", "openai_compatible", "anthropic", "cohere", "generic_api", "custom"].includes(
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

  // ─── Fetch selected credential detail and sync settings ───
  useEffect(() => {
    if (selectedCredentialId) {
      getUserCredentialById(selectedCredentialId)
        .then((cred: any) => {
          if (!cred) return;
          const secret = cred.secret || {};

          // Set SSL Verification based on skip_ssl_verify in the secret
          const skipSsl = secret.skip_ssl_verify;
          if (skipSsl !== undefined) {
            const isSkip = typeof skipSsl === "string"
              ? skipSsl.toLowerCase() in { "true": 1, "1": 1, "yes": 1, "on": 1 }
              : Boolean(skipSsl);
            setVerifySsl(!isSkip);
          } else {
            setVerifySsl(true);
          }

          // Set extra body params if present in credential secret
          if (secret.extra_body_params) {
            setExtraBodyParams(typeof secret.extra_body_params === "string"
              ? secret.extra_body_params
              : JSON.stringify(secret.extra_body_params, null, 2)
            );
          } else {
            setExtraBodyParams("");
          }
        })
        .catch(console.error);
    }
  }, [selectedCredentialId]);

  // ─── Fetch Builder History ───
  useEffect(() => {
    if (chatOpen && mode === "builder" && currentWorkflow?.id) {
      fetchWorkflowBuilderChats(currentWorkflow.id)
        .then(() => {
          // If no active builder chatflow is set yet and we haven't done our initial load, auto-select the most recent
          if (!activeBuilderChatflowId && !hasInitialLoaded.current) {
            const currentBuilderChats = useChatStore.getState().builderChats;
            const chatEntries = Object.entries(currentBuilderChats);
            if (chatEntries.length > 0) {
              // Sort chats by last message timestamp to find the most recent
              chatEntries.sort((a, b) => {
                const aLast = a[1][a[1].length - 1]?.created_at || "";
                const bLast = b[1][b[1].length - 1]?.created_at || "";
                return new Date(bLast).getTime() - new Date(aLast).getTime();
              });
              const mostRecentId = chatEntries[0][0];
              setActiveBuilderChatflowId(mostRecentId);
            }
            hasInitialLoaded.current = true;
          }
        })
        .catch((err) => {
          console.error("Failed to load KAI Assistant chat history:", err);
        });
    }
  }, [chatOpen, mode, currentWorkflow?.id, activeBuilderChatflowId, fetchWorkflowBuilderChats, setActiveBuilderChatflowId]);

  // ─── Fetch History on View Toggle ───
  useEffect(() => {
    if (chatOpen && showHistoryView && currentWorkflow?.id) {
      if (mode === "builder") {
        fetchWorkflowBuilderChats(currentWorkflow.id);
      } else {
        fetchWorkflowChats(currentWorkflow.id, false);
      }
    }
  }, [chatOpen, showHistoryView, mode, currentWorkflow?.id, fetchWorkflowBuilderChats, fetchWorkflowChats]);

  // ─── Formatted Chat Summaries ───
  const chatSummaries = React.useMemo(() => {
    const activeChats = mode === "builder" ? builderChats : chats;
    return Object.entries(activeChats)
      .map(([chatflowId, messages]) => {
        const sortedMessages = [...messages].sort(
          (a, b) =>
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );

        const lastMessage = sortedMessages[sortedMessages.length - 1];
        const firstMessage = sortedMessages[0];

        const title =
          firstMessage?.role === "user"
            ? firstMessage.content.slice(0, 50) +
            (firstMessage.content.length > 50 ? "..." : "")
            : "New Conversation";

        return {
          chatflowId,
          title,
          lastMessage:
            lastMessage?.content.slice(0, 100) +
            (lastMessage?.content.length > 100 ? "..." : ""),
          timestamp: lastMessage?.created_at || new Date().toISOString(),
          messageCount: messages.length,
        };
      })
      .sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
  }, [chats, builderChats, mode]);

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);

    if (diffInHours < 1) {
      return "Just now";
    } else if (diffInHours < 24) {
      return `${Math.floor(diffInHours)} hours ago`;
    } else {
      return date.toLocaleDateString("en-US");
    }
  };

  const handleSelectChat = (chatflowId: string) => {
    if (mode === "builder") {
      if (chatflowId === "") {
        setActiveBuilderChatflowId(null);
        setRebuildFromScratch(false);
      } else {
        setActiveBuilderChatflowId(chatflowId);
      }
    } else {
      if (chatflowId === "") {
        setActiveChatflowId(null);
      } else {
        setActiveChatflowId(chatflowId);
      }
    }
    setShowHistoryView(false);
  };

  const handleDeleteChat = async (chatflowId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this conversation?")) {
      try {
        if (mode === "builder") {
          await clearBuilderMessages(chatflowId);
        } else {
          await clearMessages(chatflowId);
        }
      } catch (error) {
        console.error("Error occurred while deleting chat:", error);
      }
    }
  };

  // ─── Chat Title ───
  const getChatTitle = () => {
    if (mode === "builder") return "KAI Assistant";
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
  const hasBuiltWorkflow = activeBuilderChatflowId
    ? (builderChats[activeBuilderChatflowId] || []).length > 0
    : false;
  const canvasHasWorkflow = currentNodes.length > 0;
  const isBuilderEditMode =
    !rebuildFromScratch && (hasBuiltWorkflow || canvasHasWorkflow);

  const handleBuilderGenerate = async (prompt?: string) => {
    const query = prompt || builderInput;
    if (!query.trim()) return;

    let cfId = activeBuilderChatflowId;
    if (!cfId) {
      cfId = uuidv4();
      setActiveBuilderChatflowId(cfId);
    }

    if (!selectedCredentialId) {
      const userMsg: ChatMessage = {
        id: uuidv4(),
        chatflow_id: cfId,
        role: "user",
        content: query,
        created_at: new Date().toISOString()
      };
      const assistantMsg: ChatMessage = {
        id: uuidv4(),
        chatflow_id: cfId,
        role: "assistant",
        content: "⚠️ Please select an API Credential first. Click the ⚙️ Settings icon in the header to configure your AI provider.",
        created_at: new Date().toISOString()
      };
      addBuilderMessage(cfId, userMsg);
      addBuilderMessage(cfId, assistantMsg);
      setBuilderInput("");
      return;
    }

    setBuilderLoading(true);
    setBuilderInput("");

    const userMsg: ChatMessage = {
      id: uuidv4(),
      chatflow_id: cfId,
      role: "user",
      content: query,
      created_at: new Date().toISOString()
    };
    addBuilderMessage(cfId, userMsg);

    try {
      const buildMode = isBuilderEditMode ? "edit" : "build";
      const existingWorkflow = isBuilderEditMode
        ? { nodes: currentNodes, edges: currentEdges }
        : undefined;

      const result = await AIBuilderService.generateWorkflow(query, {
        credentialId: selectedCredentialId,
        mode: buildMode,
        existingWorkflow,
        verifySsl,
        extraBodyParams: extraBodyParams.trim() || undefined,
        workflowId: currentWorkflow?.id,
        chatflowId: cfId,
      });

      // Fetch the newly added messages from the backend so they are authoritative
      await fetchBuilderChatMessages(cfId);

      if (!result.invalid_request) {
        onFlowGenerated?.(result);
        setRebuildFromScratch(false);
      }
    } catch (err: any) {
      console.error(err);
      const errorMsg =
        err.response?.data?.detail || err.message || "Failed to generate workflow";

      const errorAssistantMsg: ChatMessage = {
        id: uuidv4(),
        chatflow_id: cfId,
        role: "assistant",
        content: `Error: ${errorMsg}`,
        created_at: new Date().toISOString()
      };
      addBuilderMessage(cfId, errorAssistantMsg);
    } finally {
      setBuilderLoading(false);
    }
  };

  const handleSelectBuilderChat = (chatflowId: string) => {
    if (chatflowId === "") {
      // Start a new builder chat session
      setActiveBuilderChatflowId(null);
      setRebuildFromScratch(false);
    } else {
      // Select existing builder chat session
      setActiveBuilderChatflowId(chatflowId);
    }
  };

  const handleRebuild = () => {
    setActiveBuilderChatflowId(null);
    setRebuildFromScratch(true);
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

  const activeBuilderChats = activeBuilderChatflowId ? builderChats[activeBuilderChatflowId] || [] : [];
  const currentInput = mode === "builder" ? builderInput : chatInput;
  const setCurrentInput = mode === "builder" ? setBuilderInput : setChatInput;
  const isLoading = mode === "builder" ? builderLoading : chatLoading;

  if (!chatOpen) return null;

  return (
    <div
      className={`fixed bottom-20 right-4 bg-[#18181A] rounded-xl shadow-2xl flex flex-col z-50 animate-slide-up border border-gray-700 transition-all duration-300 ${isExpanded
          ? "w-[calc(100vw-2rem)] h-[calc(100vh-6rem)] left-4"
          : "w-148 h-[600px]"
        }`}
    >
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          {showHistoryView ? (
            <>
              <button
                onClick={() => setShowHistoryView(false)}
                className="text-gray-400 hover:text-gray-300 p-1 rounded hover:bg-gray-700 w-7 h-7 flex items-center justify-center transition-colors duration-150"
                title="Back to chat"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <span className="font-semibold text-gray-200 text-sm">
                {mode === "builder" ? "KAI Assistant History" : "Conversation History"}
              </span>
            </>
          ) : mode === "builder" ? (
            <>
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span className="font-semibold text-gray-200 text-sm">KAI Assistant</span>
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
          {/* Builder-only actions */}
          {mode === "builder" && !showHistoryView && (
            <>
              <button
                onClick={handleRebuild}
                className="text-gray-400 hover:text-purple-400 hover:bg-purple-500/10 p-1.5 rounded w-7 h-7 flex items-center justify-center transition-colors"
                title="Restart Assistant (Start from scratch)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <button
                onClick={() => setShowSettings(!showSettings)}
                className={`p-1.5 rounded transition-colors w-7 h-7 flex items-center justify-center ${showSettings
                    ? "text-purple-400 bg-purple-500/10 border border-purple-500/20"
                    : "text-gray-400 hover:text-purple-400 hover:bg-purple-500/10"
                  }`}
                title="KAI Assistant Settings"
              >
                <Settings2 className="w-4 h-4" />
              </button>
            </>
          )}

          {/* Switch Mode Button */}
          {!showHistoryView && (
            <button
              onClick={() => {
                setMode(mode === "builder" ? "chat" : "builder");
                setShowSettings(false);
              }}
              className={`p-1.5 rounded border transition-all duration-200 flex items-center gap-1.5 text-xs font-medium ${mode === "builder"
                  ? "bg-purple-500/20 text-purple-400 border-purple-500/30 hover:bg-purple-500/30"
                  : "text-gray-400 hover:text-purple-400 hover:bg-purple-500/10 border-gray-700 hover:border-purple-500/30"
                }`}
              title={mode === "builder" ? "Switch to Chat" : "Switch to KAI Assistant"}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span className="hidden sm:inline font-sans text-xs">KAI Assistant</span>
            </button>
          )}

          <div className="h-4 w-[1px] bg-gray-700 mx-1" />

          {/* Common Buttons (History, Clear, Maximize, Close) */}
          <button
            onClick={() => setShowHistoryView(!showHistoryView)}
            className={`p-1.5 rounded w-7 h-7 flex items-center justify-center transition-colors duration-150 ${showHistoryView
                ? mode === "builder"
                  ? "text-purple-400 bg-purple-500/10 border border-purple-500/20"
                  : "text-blue-400 bg-blue-500/10 border border-blue-500/20"
                : mode === "builder"
                  ? "text-gray-400 hover:text-purple-400 hover:bg-purple-500/10"
                  : "text-gray-400 hover:text-blue-400 hover:bg-blue-500/10"
              }`}
            title={mode === "builder" ? "Assistant conversation history" : "Conversation history"}
          >
            <History className="w-4 h-4" />
          </button>

          <button
            onClick={() => {
              if (mode === "builder") {
                setActiveBuilderChatflowId(null);
                setRebuildFromScratch(false);
              } else {
                onClearChat();
              }
            }}
            className="text-red-400 hover:text-red-300 p-1.5 rounded hover:bg-gray-700 w-7 h-7 flex items-center justify-center"
            title="Clear conversation"
          >
            <Eraser className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-400 hover:text-gray-300 p-1.5 rounded hover:bg-gray-700 w-7 h-7 flex items-center justify-center"
            title={isExpanded ? "Minimize" : "Maximize"}
          >
            {isExpanded ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>

          <button
            onClick={() => setChatOpen(false)}
            className={`p-1.5 rounded w-7 h-7 flex items-center justify-center transition-colors duration-150 ${mode === "builder"
                ? "text-gray-400 hover:text-purple-400 hover:bg-purple-500/10"
                : "text-gray-400 hover:text-blue-400 hover:bg-blue-500/10"
              }`}
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ─── Settings Popover (Builder Mode) ─── */}
      {mode === "builder" && showSettings && (
        <div className="px-4 py-3 border-b border-gray-700 bg-gray-800/50 space-y-3 animate-in">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">
              AI Provider Credential <span className="text-red-400">*</span>
            </label>
            <CredentialSelector
              value={selectedCredentialId}
              onChange={(credentialId) => setSelectedCredentialId(credentialId)}
              placeholder="Select a Credential..."
              showCreateNew={true}
              allowedServiceTypes={["openai", "openai_compatible", "anthropic", "cohere", "generic_api", "custom"]}
            />
          </div>

          {/* Advanced Settings Expander */}
          <div className="border-t border-gray-700/50 pt-2">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1 focus:outline-none"
            >
              <span>{showAdvanced ? "Hide Advanced Settings" : "Show Advanced Settings"}</span>
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${showAdvanced ? "rotate-180" : ""}`} />
            </button>

            {showAdvanced && (
              <div className="space-y-3 mt-2 pt-2 border-t border-gray-700/30 animate-in">
                <div className="flex items-center gap-2">
                  <input
                    id="verify-ssl"
                    type="checkbox"
                    checked={verifySsl}
                    onChange={(e) => setVerifySsl(e.target.checked)}
                    className="w-4 h-4 bg-gray-900 border border-gray-700 rounded text-purple-600 focus:ring-purple-500 focus:ring-offset-gray-800 focus:ring-2 animate-none"
                  />
                  <label htmlFor="verify-ssl" className="text-xs text-gray-300 select-none cursor-pointer">
                    SSL Certificate Verification (Secure)
                  </label>
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">
                    Extra Body Parameters (JSON, Optional)
                  </label>
                  <textarea
                    rows={2}
                    value={extraBodyParams}
                    onChange={(e) => setExtraBodyParams(e.target.value)}
                    placeholder='e.g. { "top_k": 50 }'
                    className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-xs text-gray-200 outline-none focus:border-purple-500 font-mono resize-none"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {showHistoryView ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-4 flex flex-col bg-[#141416]">
          {/* Start New Conversation Card */}
          <button
            onClick={() => handleSelectChat("")}
            className={`w-full p-4 rounded-xl border border-dashed hover:border-gray-500 bg-gray-800/20 hover:bg-gray-800/40 transition-all duration-200 flex items-center justify-center gap-2 group text-sm font-medium ${mode === "builder"
                ? "border-purple-500/30 hover:border-purple-500/50 text-purple-400"
                : "border-blue-500/30 hover:border-blue-500/50 text-blue-400"
              }`}
          >
            <Plus className="w-4 h-4 transition-transform group-hover:rotate-90 duration-200" />
            <span>Start New Conversation</span>
          </button>

          <div className="h-[1px] bg-gray-800/80 my-1" />

          {/* History List */}
          {chatSummaries.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500 py-10">
              <Clock className="w-8 h-8 mb-2 opacity-30 animate-pulse" />
              <span className="text-xs font-sans text-gray-400">No conversation history found</span>
            </div>
          ) : (
            <div className="space-y-2.5">
              {chatSummaries.map((item) => {
                const isActive =
                  mode === "builder"
                    ? item.chatflowId === activeBuilderChatflowId
                    : item.chatflowId === activeChatflowId;

                return (
                  <div
                    key={item.chatflowId}
                    onClick={() => handleSelectChat(item.chatflowId)}
                    className={`group relative p-3 rounded-xl border transition-all duration-200 cursor-pointer flex gap-3 items-start ${isActive
                        ? mode === "builder"
                          ? "border-purple-500/50 bg-purple-500/5 text-gray-100 shadow-[0_0_15px_-3px_rgba(168,85,247,0.15)]"
                          : "border-blue-500/50 bg-blue-500/5 text-gray-100 shadow-[0_0_15px_-3px_rgba(59,130,246,0.1)]"
                        : "border-gray-800 bg-gray-900/20 hover:border-gray-700 hover:bg-gray-800/25 text-gray-350"
                      }`}
                  >
                    {/* Icon */}
                    <div className={`p-2 rounded-lg mt-0.5 transition-colors duration-150 ${isActive
                        ? mode === "builder"
                          ? "bg-purple-500/10 text-purple-400"
                          : "bg-blue-500/10 text-blue-400"
                        : "bg-gray-800/40 text-gray-500 group-hover:text-gray-400"
                      }`}>
                      <MessageSquare className="w-4 h-4" />
                    </div>

                    {/* Text Info */}
                    <div className="flex-1 min-w-0 pr-6">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={`font-semibold text-xs truncate block ${isActive ? "text-gray-100" : "text-gray-300"
                          }`}>
                          {item.title}
                        </span>
                        {isActive && (
                          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${mode === "builder" ? "bg-purple-500 animate-pulse" : "bg-blue-500 animate-pulse"
                            }`} />
                        )}
                      </div>

                      {item.lastMessage && (
                        <p className="text-[10px] text-gray-500 truncate mb-1.5 leading-relaxed font-sans">
                          {item.lastMessage}
                        </p>
                      )}

                      <div className="flex items-center gap-2.5 text-[9px] text-gray-450 font-sans">
                        <span>{formatTimestamp(item.timestamp)}</span>
                        <span className="opacity-40">•</span>
                        <span>{item.messageCount} messages</span>
                      </div>
                    </div>

                    {/* Delete Button */}
                    <button
                      onClick={(e) => handleDeleteChat(item.chatflowId, e)}
                      className="absolute right-2 top-2 p-1 rounded hover:bg-red-500/10 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-150"
                      title="Delete conversation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* ─── Messages Area ─── */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {/* Builder Error - shown inline in chat bubbles only */}

            {/* Chat Error */}
            {mode === "chat" && chatError && (
              <div className="text-xs text-red-400">{chatError}</div>
            )}

            {/* Builder Empty State */}
            {mode === "builder" && activeBuilderChats.length === 0 && !builderLoading && (
              <div className="text-center text-gray-400 mt-10">
                <p className="mb-4">Describe the workflow you want to build.</p>
                <div className="flex flex-wrap justify-center gap-2">
                  <button
                    onClick={() => handleBuilderGenerate("Create a conversational AI agent")}
                    className="px-3 py-1.5 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/25 rounded-full text-xs font-medium transition-colors"
                    disabled={builderLoading}
                  >
                    Conversational Agent
                  </button>
                  <button
                    onClick={() =>
                      handleBuilderGenerate("Build a webhook trigger that saves data")
                    }
                    className="px-3 py-1.5 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/25 rounded-full text-xs font-medium transition-colors"
                    disabled={builderLoading}
                  >
                    Webhook Data Saver
                  </button>
                </div>
              </div>
            )}

            {/* Builder Messages */}
            {mode === "builder" &&
              activeBuilderChats.map((msg, i) => (
                <ChatBubble
                  key={`builder-${i}`}
                  from={msg.role as "user" | "assistant"}
                  message={msg.content}
                  userInitial={msg.role === "user" ? "U" : undefined}
                  isBuilder={true}
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
                isBuilder={true}
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
              className={`flex-1 border rounded-lg px-3 py-2 text-sm transition-all duration-200 focus:outline-none ${mode === "builder"
                  ? "border-purple-500 bg-gray-800 text-gray-100 placeholder-gray-400 focus:border-purple-400 focus:ring-1 focus:ring-purple-500/20"
                  : "border-gray-600 bg-gray-800 text-gray-100 placeholder-gray-400 focus:border-blue-400 focus:ring-1 focus:ring-blue-500/20"
                }`}
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
              className={`text-white px-4 py-2 rounded-lg disabled:opacity-50 ${mode === "builder"
                  ? "bg-purple-600 hover:bg-purple-700"
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
        </>
      )}
    </div>
  );
}
