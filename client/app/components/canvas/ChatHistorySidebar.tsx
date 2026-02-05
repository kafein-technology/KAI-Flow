import React, { useEffect, useState } from "react";
import { useChatStore } from "../../stores/chat";
import { usePinnedItems } from "../../stores/pinnedItems";
import type { ChatMessage } from "../../types/api";
import PinButton from "../common/PinButton";
import { MessageSquare, Plus, Trash2, Clock, Heart } from "../../icons/index";

interface ChatHistorySidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectChat: (chatflowId: string) => void;
  activeChatflowId: string | null;
  workflow_id?: string; // Workflow ID eklendi
}

export default function ChatHistorySidebar({
  isOpen,
  onClose,
  onSelectChat,
  activeChatflowId,
  workflow_id,
}: ChatHistorySidebarProps) {
  const { chats, fetchAllChats, fetchWorkflowChats, loading, clearMessages } =
    useChatStore();
  const { getPinnedItems } = usePinnedItems();
  const [chatSummaries, setChatSummaries] = useState<
    Array<{
      chatflowId: string;
      title: string;
      lastMessage: string;
      timestamp: string;
      messageCount: number;
    }>
  >([]);

  useEffect(() => {
    if (isOpen) {
      if (workflow_id) {
        // Workflow'a özel chat history getir
        fetchWorkflowChats(workflow_id);
      } else {
        // Tüm chat history'yi getir
        fetchAllChats();
      }
    }
  }, [isOpen, fetchAllChats, fetchWorkflowChats, workflow_id]);

  useEffect(() => {
    // Create chat summaries from the chats data
    const summaries = Object.entries(chats)
      .map(([chatflowId, messages]) => {
        const sortedMessages = messages.sort(
          (a, b) =>
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );

        const lastMessage = sortedMessages[sortedMessages.length - 1];
        const firstMessage = sortedMessages[0];

        // Create a title from the first user message or use a default
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

    setChatSummaries(summaries);
  }, [chats]);

  // Get pinned chats
  const pinnedChats = getPinnedItems("chat");
  const pinnedChatIds = new Set(pinnedChats.map((chat) => chat.id));

  // Separate pinned and unpinned chats
  const pinnedChatSummaries = chatSummaries.filter((chat) =>
    pinnedChatIds.has(chat.chatflowId)
  );
  const unpinnedChatSummaries = chatSummaries.filter(
    (chat) => !pinnedChatIds.has(chat.chatflowId)
  );

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

  const handleNewChat = () => {
    onSelectChat(""); // Empty string indicates new chat
    onClose();
  };

  const handleDeleteChat = async (chatflowId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Bu konuşmayı silmek istediğinizden emin misiniz?")) {
      try {
        await clearMessages(chatflowId);
      } catch (error) {
        console.error("Chat silinirken hata oluştu:", error);
        alert("Chat silinirken bir hata oluştu. Lütfen tekrar deneyin.");
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Sidebar */}
      <div className="relative w-80 h-full bg-gray-900 border-r border-gray-700 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-200">
            Konuşma Geçmişi
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-300"
          >
            ✕
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-4 border-b border-gray-700">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Conversation
          </button>
        </div>

        {/* Chat List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center p-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : chatSummaries.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-gray-400">
              <MessageSquare className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-center">No conversation history</p>
              <p className="text-sm text-center mt-2">
                Start a new conversation
              </p>
            </div>
          ) : (
            <div className="p-2">
              {/* Pinned Chats Section */}
              {pinnedChatSummaries.length > 0 && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2 px-2">
                    <Heart className="w-4 h-4 text-red-500 fill-current" />
                    <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Pinned Chats
                    </span>
                  </div>
                  {pinnedChatSummaries.map((chat) => (
                    <div
                      key={chat.chatflowId}
                      onClick={() => {
                        onSelectChat(chat.chatflowId);
                        onClose();
                      }}
                      className={`p-3 rounded-lg cursor-pointer transition-colors mb-2 border-l-2 border-red-500 ${
                        activeChatflowId === chat.chatflowId
                          ? "bg-blue-600 text-white"
                          : "hover:bg-gray-800 text-gray-200 bg-gray-800/50"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-sm truncate">
                            {chat.title}
                          </h3>
                          <p
                            className={`text-xs mt-1 truncate ${
                              activeChatflowId === chat.chatflowId
                                ? "text-blue-100"
                                : "text-gray-400"
                            }`}
                          >
                            {chat.lastMessage}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <Clock className="w-3 h-3" />
                            <span className="text-xs">
                              {formatTimestamp(chat.timestamp)}
                            </span>
                            <span className="text-xs">
                              • {chat.messageCount} messages
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <PinButton
                            id={chat.chatflowId}
                            type="chat"
                            title={chat.title}
                            description={chat.lastMessage}
                            metadata={{
                              messageCount: chat.messageCount,
                              lastActivity: chat.timestamp,
                            }}
                            size="sm"
                            variant="minimal"
                            className="text-gray-400 hover:text-red-500"
                          />
                          <button
                            onClick={(e) =>
                              handleDeleteChat(chat.chatflowId, e)
                            }
                            className={`p-1 rounded hover:bg-opacity-20 transition-colors ${
                              activeChatflowId === chat.chatflowId
                                ? "hover:bg-white"
                                : "hover:bg-red-500"
                            }`}
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Regular Chats Section */}
              {unpinnedChatSummaries.length > 0 && (
                <div>
                  {pinnedChatSummaries.length > 0 && (
                    <div className="flex items-center gap-2 mb-2 px-2">
                      <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                        Recent Chats
                      </span>
                    </div>
                  )}
                  {unpinnedChatSummaries.map((chat) => (
                    <div
                      key={chat.chatflowId}
                      onClick={() => {
                        onSelectChat(chat.chatflowId);
                        onClose();
                      }}
                      className={`p-3 rounded-lg cursor-pointer transition-colors mb-2 ${
                        activeChatflowId === chat.chatflowId
                          ? "bg-blue-600 text-white"
                          : "hover:bg-gray-800 text-gray-200"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-sm truncate">
                            {chat.title}
                          </h3>
                          <p
                            className={`text-xs mt-1 truncate ${
                              activeChatflowId === chat.chatflowId
                                ? "text-blue-100"
                                : "text-gray-400"
                            }`}
                          >
                            {chat.lastMessage}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <Clock className="w-3 h-3" />
                            <span className="text-xs">
                              {formatTimestamp(chat.timestamp)}
                            </span>
                            <span className="text-xs">
                              • {chat.messageCount} messages
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <PinButton
                            id={chat.chatflowId}
                            type="chat"
                            title={chat.title}
                            description={chat.lastMessage}
                            metadata={{
                              messageCount: chat.messageCount,
                              lastActivity: chat.timestamp,
                            }}
                            size="sm"
                            variant="minimal"
                            className="text-gray-400 hover:text-red-500"
                          />
                          <button
                            onClick={(e) =>
                              handleDeleteChat(chat.chatflowId, e)
                            }
                            className={`p-1 rounded hover:bg-opacity-20 transition-colors ${
                              activeChatflowId === chat.chatflowId
                                ? "hover:bg-white"
                                : "hover:bg-red-500"
                            }`}
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
