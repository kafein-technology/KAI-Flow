import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageCircle, Bot, User, Clock, Loader, Plus, History, RefreshCw, Trash2, ChevronDown } from '~/icons/index';
import { externalWorkflowService, exportedWorkflowService } from '~/services/externalWorkflowService';
import type { ExternalWorkflowInfo } from '~/types/external-workflows';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ExternalWorkflowChatProps {
  workflow: ExternalWorkflowInfo;
  isExported?: boolean; // Whether this is an exported workflow instance
}

interface ChatSession {
  session_id: string;
  message_count: number;
  last_activity?: string;
}

export default function ExternalWorkflowChat({ workflow, isExported = false }: ExternalWorkflowChatProps) {
  // For exported workflows, force direct connection
  const effectiveIsExported = isExported || workflow.external_url?.includes('localhost:8001');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [showSessionDropdown, setShowSessionDropdown] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowSessionDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  useEffect(() => {
    // Generate session ID when component mounts
    const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);

    // Load available sessions
    loadSessions();

    // Add welcome message
    const welcomeMessage: ChatMessage = {
      id: 'welcome',
      role: 'assistant',
      content: `Hello! I'm ready to help you with ${workflow.name}. What would you like to know?`,
      timestamp: new Date().toISOString(),
    };
    setMessages([welcomeMessage]);
  }, [workflow.name]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadSessions = async () => {
    if (!workflow.capabilities?.memory) return;

    setLoadingSessions(true);
    try {
      let response;
      if (effectiveIsExported && workflow.external_url) {
        response = await exportedWorkflowService.listExportedWorkflowSessions(
          workflow.external_url,
          workflow.api_key_required ? 'api-key-placeholder' : undefined
        );
      } else {
        response = await externalWorkflowService.listExternalWorkflowSessions(workflow.workflow_id);
      }
      setSessions(response.sessions || []);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setLoadingSessions(false);
    }
  };

  const loadSessionHistory = async (sessionIdToLoad: string) => {
    setLoadingHistory(true);
    try {
      let response;
      if (effectiveIsExported && workflow.external_url) {
        response = await exportedWorkflowService.getExportedWorkflowSessionMemory(
          workflow.external_url,
          sessionIdToLoad,
          workflow.api_key_required ? 'api-key-placeholder' : undefined
        );
      } else {
        response = await externalWorkflowService.getExternalWorkflowSessionHistory(
          workflow.workflow_id,
          sessionIdToLoad
        );
      }

      const historyMessages: ChatMessage[] = response.messages.map((msg: any) => ({
        id: `${msg.role}_${msg.timestamp}`,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
      }));

      setMessages(historyMessages);
      setSessionId(sessionIdToLoad);
    } catch (error) {
      console.error('Failed to load session history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const createNewSession = () => {
    const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);

    const welcomeMessage: ChatMessage = {
      id: 'welcome_new',
      role: 'assistant',
      content: `Hello! I'm ready to help you with ${workflow.name}. What would you like to know?`,
      timestamp: new Date().toISOString(),
    };
    setMessages([welcomeMessage]);
    setShowSessionDropdown(false);

    // Refresh sessions list
    setTimeout(loadSessions, 1000);
  };

  const clearSession = async (sessionIdToClear: string) => {
    try {
      if (effectiveIsExported && workflow.external_url) {
        await exportedWorkflowService.clearExportedWorkflowSessionMemory(
          workflow.external_url,
          sessionIdToClear,
          workflow.api_key_required ? 'api-key-placeholder' : undefined
        );
      } else {
        await externalWorkflowService.clearExternalWorkflowSession(
          workflow.workflow_id,
          sessionIdToClear
        );
      }

      // If clearing current session, create new one
      if (sessionIdToClear === sessionId) {
        createNewSession();
      }

      // Refresh sessions list
      loadSessions();
    } catch (error) {
      console.error('Failed to clear session:', error);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      let response;
      if (effectiveIsExported && workflow.external_url) {
        response = await exportedWorkflowService.executeExportedWorkflow(
          workflow.external_url,
          input.trim(),
          sessionId,
          workflow.api_key_required ? 'api-key-placeholder' : undefined
        );
      } else {
        response = await externalWorkflowService.chatWithExternalWorkflow(
          workflow.workflow_id,
          input.trim(),
          sessionId
        );
      }

      const assistantMessage: ChatMessage = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        content: response.result?.response || response.response,
        timestamp: response.timestamp || new Date().toISOString(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date().toISOString(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="p-4 bg-gray-50 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${workflow.connection_status === 'online' ? 'bg-green-500' : 'bg-red-500'
                }`} />
              <MessageCircle className="w-5 h-5 text-gray-600" />
            </div>
            <div>
              <h4 className="font-medium text-gray-900">{workflow.name}</h4>
              <p className="text-sm text-gray-500">
                Status: {workflow.connection_status} • {effectiveIsExported ? 'Exported' : 'External'} workflow
              </p>
            </div>
          </div>

          {/* Session Management */}
          {workflow.capabilities?.memory && effectiveIsExported && (
            <div className="flex items-center gap-2">
              <button
                onClick={createNewSession}
                className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                title="Start new session"
              >
                <Plus className="w-4 h-4" />
                New
              </button>

              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setShowSessionDropdown(!showSessionDropdown)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                  title="Session history"
                >
                  <History className="w-4 h-4" />
                  Sessions
                  <ChevronDown className={`w-3 h-3 transition-transform ${showSessionDropdown ? 'rotate-180' : ''}`} />
                </button>

                {showSessionDropdown && (
                  <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                    <div className="p-2 border-b">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-900">Chat Sessions</span>
                        <button
                          onClick={loadSessions}
                          disabled={loadingSessions}
                          className="p-1 text-gray-500 hover:text-gray-700 rounded"
                        >
                          <RefreshCw className={`w-4 h-4 ${loadingSessions ? 'animate-spin' : ''}`} />
                        </button>
                      </div>
                    </div>

                    <div className="max-h-48 overflow-y-auto">
                      {sessions.length === 0 ? (
                        <div className="p-3 text-sm text-gray-500 text-center">
                          No previous sessions
                        </div>
                      ) : (
                        sessions.map((session) => (
                          <div
                            key={session.session_id}
                            className={`flex items-center justify-between p-2 hover:bg-gray-50 border-b last:border-b-0 ${session.session_id === sessionId ? 'bg-blue-50' : ''
                              }`}
                          >
                            <button
                              onClick={() => {
                                loadSessionHistory(session.session_id);
                                setShowSessionDropdown(false);
                              }}
                              disabled={loadingHistory}
                              className="flex-1 text-left"
                            >
                              <div className="text-sm font-medium text-gray-900 truncate">
                                Session {session.session_id.slice(-8)}
                              </div>
                              <div className="text-xs text-gray-500">
                                {session.message_count} messages
                                {session.last_activity && (
                                  <span className="ml-1">
                                    • {new Date(session.last_activity).toLocaleDateString()}
                                  </span>
                                )}
                              </div>
                            </button>

                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                clearSession(session.session_id);
                              }}
                              className="p-1 text-red-500 hover:text-red-700 rounded ml-2"
                              title="Clear session"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Current Session Info */}
        {workflow.capabilities?.memory && effectiveIsExported && sessionId && (
          <div className="mt-2 text-xs text-gray-500">
            Current session: <span className="font-mono">{sessionId.slice(-12)}</span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loadingHistory ? (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-2 text-gray-500">
              <Loader className="w-4 h-4 animate-spin" />
              <span>Loading session history...</span>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex items-start gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''
                }`}
            >
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-green-600 text-white'
                }`}>
                {message.role === 'user' ? (
                  <User className="w-4 h-4" />
                ) : (
                  <Bot className="w-4 h-4" />
                )}
              </div>
              <div className={`flex-1 max-w-[80%] ${message.role === 'user' ? 'text-right' : ''
                }`}>
                <div className={`inline-block p-3 rounded-2xl ${message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                  }`}>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
                <div className={`flex items-center gap-1 mt-1 text-xs text-gray-500 ${message.role === 'user' ? 'justify-end' : ''
                  }`}>
                  <Clock className="w-3 h-3" />
                  {formatTime(message.timestamp)}
                </div>
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-600 text-white flex items-center justify-center">
              <Bot className="w-4 h-4" />
            </div>
            <div className="flex-1">
              <div className="inline-block p-3 rounded-2xl bg-gray-100 text-gray-900">
                <div className="flex items-center gap-2">
                  <Loader className="w-4 h-4 animate-spin" />
                  <span>Thinking...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div className="p-4 border-t bg-gray-50">
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-full focus:ring-2 focus:ring-green-500 focus:border-transparent"
            disabled={isLoading || workflow.connection_status !== 'online'}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading || workflow.connection_status !== 'online'}
            className="px-4 py-2 bg-green-600 text-white rounded-full hover:bg-green-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center"
          >
            {isLoading ? (
              <Loader className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>

        {workflow.connection_status !== 'online' && (
          <p className="text-sm text-red-600 mt-2 text-center">
            Chat is disabled - workflow is {workflow.connection_status}
          </p>
        )}

        {workflow.capabilities?.memory && effectiveIsExported && (
          <p className="text-xs text-gray-500 mt-2 text-center">
            This conversation has memory - the AI will remember our chat history
          </p>
        )}
      </div>
    </div>
  );
}
