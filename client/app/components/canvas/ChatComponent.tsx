import React, { useState, useEffect, useRef } from "react";
import ChatBubble from "../common/ChatBubble";
import { useChatStore } from "~/stores/chat";
import { MessageSquare, Minimize2, Maximize2, History, Eraser } from "../../icons/index";

interface ChatComponentProps {
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
  chatHistory: any[];
  chatError: string | null;
  chatLoading: boolean;
  chatThinking: boolean; // Yeni thinking prop'u
  chatInput: string;
  setChatInput: (input: string) => void;
  onSendMessage: () => void;
  onClearChat: () => void;
  onShowHistory: () => void;
  activeChatflowId: string | null;
  currentWorkflow?: any;
  flowData?: any;
}

export default function ChatComponent({
  chatOpen,
  setChatOpen,
  chatHistory,
  chatError,
  chatLoading,
  chatThinking, // Yeni thinking prop'u
  chatInput,
  setChatInput,
  onSendMessage,
  onClearChat,
  onShowHistory,
  activeChatflowId,
  currentWorkflow,
  flowData,
}: ChatComponentProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const { updateMessage, removeMessage, sendEditedMessage } = useChatStore();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, chatLoading]);

  // Get chat title from first user message
  const getChatTitle = () => {
    if (!activeChatflowId || chatHistory.length === 0) {
      return "New Conversation";
    }

    const firstUserMessage = chatHistory.find((msg) => msg.role === "user");
    if (firstUserMessage) {
      const title = firstUserMessage.content.slice(0, 30);
      return title.length < firstUserMessage.content.length
        ? title + "..."
        : title;
    }

    return "New Conversation";
  };

  const handleEditMessage = (messageId: string, currentContent: string) => {
    setEditingMessageId(messageId);
  };

  const handleSaveEdit = async (messageId: string, newContent: string) => {
    if (activeChatflowId) {
      const message = chatHistory.find((msg) => msg.id === messageId);
      if (message) {
        // Immediately close the edit modal
        setEditingMessageId(null);

        const updatedMessage = { ...message, content: newContent };
        updateMessage(activeChatflowId, updatedMessage);

        // Remove all assistant messages that came after this user message
        const messageIndex = chatHistory.findIndex(
          (msg) => msg.id === messageId
        );
        const messagesToRemove = chatHistory
          .slice(messageIndex + 1)
          .filter((msg) => msg.role === "assistant")
          .map((msg) => msg.id);

        messagesToRemove.forEach((id) => {
          removeMessage(activeChatflowId!, id);
        });

        // Trigger new response with updated message
        if (currentWorkflow && flowData) {
          try {
            await sendEditedMessage(
              flowData,
              newContent,
              activeChatflowId,
              currentWorkflow.id
            );
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
        // Remove the selected message
        removeMessage(activeChatflowId, messageId);

        // If it's a user message, also remove all assistant messages that came after it
        if (message.role === "user") {
          const messageIndex = chatHistory.findIndex(
            (msg) => msg.id === messageId
          );
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

  if (!chatOpen) return null;

  return (
    <div
      className={`fixed bottom-20 right-4 bg-[#18181A] rounded-xl shadow-2xl flex flex-col z-50 animate-slide-up border border-gray-700 transition-all duration-300 ${isExpanded
        ? "w-[calc(100vw-2rem)] h-[calc(100vh-6rem)] left-4"
        : "w-148 h-[600px]"
        }`}
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-blue-400" />
          <span className="font-semibold text-gray-200 text-sm truncate">
            {getChatTitle()}
          </span>
        </div>
        <div className="flex items-center gap-2">
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
          <button
            onClick={onShowHistory}
            className="text-gray-400 hover:text-gray-300 p-1 rounded hover:bg-gray-700"
            title="Conversation history"
          >
            <History className="w-4 h-4" />
          </button>
          <button
            onClick={onClearChat}
            className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-gray-700"
            title="Clear conversation"
          >
            <Eraser className="w-4 h-4" />
          </button>
          <button
            onClick={() => setChatOpen(false)}
            className="text-gray-400 hover:text-gray-300 p-1 rounded hover:bg-gray-700"
          >
            ✕
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {chatError && <div className="text-xs text-red-400">{chatError}</div>}
        {[...chatHistory]
          .sort((a, b) => {
            // Sort by created_at timestamp, with fallback for missing values
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
        {chatThinking && <ChatBubble from="assistant" message="" loading />}
        <div ref={messagesEndRef} />
      </div>
      <div className="p-3 border-t border-gray-700 flex gap-2">
        <input
          type="text"
          className="flex-1 border rounded-lg px-3 py-2 text-sm border-gray-600 bg-gray-800 text-gray-100 placeholder-gray-400 focus:outline-none focus:border-blue-400"
          placeholder="Mesajınızı yazın..."
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSendMessage();
          }}
          disabled={chatLoading}
        />
        <button
          onClick={onSendMessage}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          disabled={chatLoading || !chatInput.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
