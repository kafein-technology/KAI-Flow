import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';
import type { ChatMessage, WorkflowExecution } from '../types/api';
import * as chatService from '../services/chatService';
import { executeWorkflow } from '../services/workflowService';
import { executeWorkflowStream } from '../services/executionService';
import { useExecutionsStore } from './executions';
import {
  ensureLiveNodeFailure,
  mergeLiveNodeOutputMaps,
  reduceLiveNodeEvent,
} from '../lib/liveExecution';

interface ChatStore {
  chats: Record<string, ChatMessage[]>;
  activeChatflowId: string | null;
  builderChats: Record<string, ChatMessage[]>;
  activeBuilderChatflowId: string | null;
  loading: boolean;
  thinking: boolean; // New thinking state
  error: string | null;
  fetchAllChats: () => Promise<void>;
  fetchWorkflowChats: (workflow_id: string, isBuilder?: boolean) => Promise<void>;
  fetchWorkflowBuilderChats: (workflow_id: string) => Promise<void>;
  startNewChat: (content: string, workflow_id: string) => Promise<void>;
  fetchChatMessages: (chatflow_id: string) => Promise<void>;
  fetchBuilderChatMessages: (chatflow_id: string) => Promise<void>;
  interactWithChat: (chatflow_id: string, content: string, workflow_id: string) => Promise<void>;
  setActiveChatflowId: (chatflow_id: string | null) => void;
  setActiveBuilderChatflowId: (chatflow_id: string | null) => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean) => void; // New setter
  setError: (error: string | null) => void;
  addMessage: (chatflow_id: string, message: ChatMessage) => void;
  addBuilderMessage: (chatflow_id: string, message: ChatMessage) => void;
  updateMessage: (chatflow_id: string, message: ChatMessage) => void;
  removeMessage: (chatflow_id: string, message_id: string) => void;
  clearMessages: (chatflow_id: string) => Promise<void>;
  clearBuilderMessages: (chatflow_id: string) => Promise<void>;
  clearAllChats: () => void;
  loadChatHistory: () => Promise<void>;
  // LLM entegrasyonu:
  startLLMChat: (flow_data: any, input_text: string, workflow_id: string) => Promise<void>;
  sendLLMMessage: (flow_data: any, input_text: string, chatflow_id: string, workflow_id: string) => Promise<void>;
  sendEditedMessage: (flow_data: any, input_text: string, chatflow_id: string, workflow_id: string) => Promise<void>;
}

// Helper function to execute workflow with streaming and capture execution data
const executeWorkflowWithStreaming = async (
  flow_data: any,
  input_text: string,
  session_id: string,
  chatflow_id: string,
  workflow_id: string
) => {
  console.log('Starting chat execution with streaming...');

  let nodeExecutionData: Record<string, any> = {};
  const liveExecutedNodes = new Set<string>();
  const liveStartedAt = new Date().toISOString();
  let liveSessionId: string | undefined = session_id;
  let lastExecutionId: string | null = null;
  let streamHadError = false;

  const executionData = {
    flow_data,
    input_text,
    session_id,
    chatflow_id,
    workflow_id,
    execution_type: 'chat',
    trigger_source: 'chat_message'
  };

  const publishLiveExecution = (
    status: 'running' | 'completed' | 'failed',
    result: any = '',
    completedAt?: string
  ) => {
    const execution: WorkflowExecution = {
      id: lastExecutionId || `chat-${chatflow_id}`,
      workflow_id,
      input_text,
      result: {
        result,
        executed_nodes: Array.from(liveExecutedNodes),
        node_outputs: { ...nodeExecutionData },
        session_id: liveSessionId,
        status,
      },
      started_at: liveStartedAt,
      ...(completedAt ? { completed_at: completedAt } : {}),
      status,
    };
    useExecutionsStore
      .getState()
      .setCurrentExecutionForWorkflow(workflow_id, execution);
  };

  const mergeReportedStatuses = (reported: unknown) => {
    if (!reported || typeof reported !== 'object' || Array.isArray(reported)) return;
    Object.entries(reported as Record<string, unknown>).forEach(([nodeId, status]) => {
      if (status !== 'success' && status !== 'failed' && status !== 'pending') return;
      nodeExecutionData = reduceLiveNodeEvent(nodeExecutionData, nodeId, {
        type: 'node_status',
        status,
      });
      if (status === 'success' || status === 'failed') {
        liveExecutedNodes.add(nodeId);
      }
    });
  };

  try {
    window.dispatchEvent(new CustomEvent('chat-execution-start', { detail: {} }));

    const stream = await executeWorkflowStream(executionData);
    const reader = stream.getReader();

    try {
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const eventParts = buffer.split('\n\n');
        buffer = eventParts.pop() || '';
        const lines = eventParts.flatMap((part) => part.split('\n'));

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          const data = line.slice(6).trim();
          if (data === '[DONE]' || !data) continue;

          try {
            const parsed = JSON.parse(data);
            const event = parsed.event || parsed.type;

            if (parsed.execution_id) lastExecutionId = parsed.execution_id;
            liveSessionId = parsed.session_id ?? liveSessionId;

            if (event === 'node_status' && parsed.node_id) {
              nodeExecutionData = reduceLiveNodeEvent(
                nodeExecutionData,
                String(parsed.node_id),
                parsed
              );
              if (parsed.status === 'success' || parsed.status === 'failed') {
                liveExecutedNodes.add(String(parsed.node_id));
              }
              publishLiveExecution('running');
            }

            if (event === 'node_start' && parsed.node_id) {
              const nodeId = String(parsed.node_id);
              nodeExecutionData = reduceLiveNodeEvent(
                nodeExecutionData,
                nodeId,
                parsed
              );

              if (
                parsed.metadata?.node_type === 'processor' ||
                nodeId.includes('Agent')
              ) {
                const previous = nodeExecutionData[nodeId] || {};
                const inputs = { ...(previous.inputs || {}) };
                const inputsMeta = { ...(previous.inputs_meta || {}) };
                if (!inputs.input) {
                  inputs.input = input_text;
                  inputsMeta.input = {
                    sourceNodeId: 'chat_input',
                    sourceNodeName: 'Chat Input',
                    sourceNodeAlias: 'Chat Input',
                    sourceHandle: 'user_message'
                  };
                }
                nodeExecutionData = {
                  ...nodeExecutionData,
                  [nodeId]: { ...previous, inputs, inputs_meta: inputsMeta },
                };
              }
              publishLiveExecution('running');
            }

            if (event === 'node_end' && parsed.node_id) {
              const nodeId = String(parsed.node_id);
              nodeExecutionData = reduceLiveNodeEvent(
                nodeExecutionData,
                nodeId,
                parsed
              );
              liveExecutedNodes.add(nodeId);
              publishLiveExecution('running');
            }

            if (event) {
              window.dispatchEvent(new CustomEvent('chat-execution-event', {
                detail: { ...parsed, event }
              }));
            }

            if (event === 'error') {
              streamHadError = true;
              nodeExecutionData = mergeLiveNodeOutputMaps(
                nodeExecutionData,
                parsed.node_outputs
              );
              (parsed.executed_nodes || []).forEach((nodeId: unknown) => {
                liveExecutedNodes.add(String(nodeId));
              });
              mergeReportedStatuses(parsed.node_statuses);

              if (parsed.node_id) {
                const failedNodeId = String(parsed.node_id);
                nodeExecutionData = ensureLiveNodeFailure(
                  nodeExecutionData,
                  failedNodeId,
                  parsed
                );
                liveExecutedNodes.add(failedNodeId);
              }

              window.dispatchEvent(new CustomEvent('chat-execution-error', {
                detail: {
                  ...parsed,
                  type: 'error',
                  event: 'error',
                  error: parsed.error || parsed.data || 'Unknown error',
                  error_type: parsed.error_type || 'execution',
                }
              }));

              publishLiveExecution(
                'failed',
                `ERROR: ${parsed.error || parsed.data || 'Unknown error'}`,
                new Date().toISOString()
              );
            }

            if (event === 'complete' && !streamHadError) {
              nodeExecutionData = mergeLiveNodeOutputMaps(
                nodeExecutionData,
                parsed.node_outputs
              );
              (parsed.executed_nodes || []).forEach((nodeId: unknown) => {
                liveExecutedNodes.add(String(nodeId));
              });
              mergeReportedStatuses(parsed.node_statuses);
              publishLiveExecution(
                'completed',
                parsed.result,
                new Date().toISOString()
              );

              setTimeout(() => {
                window.dispatchEvent(
                  new CustomEvent('chat-execution-complete', {
                    detail: parsed,
                  })
                );
              }, 1500);
            }
          } catch (error) {
            console.error('Error parsing chat execution stream event:', error);
          }
        }
      }
    } finally {
      try {
        reader.releaseLock();
      } catch (_) {}

      if (lastExecutionId) {
        try {
          const executionService = await import('../services/executionService');
          const finalExecution = await executionService.getExecution(lastExecutionId);
          if (finalExecution) {
            const rawFinal = finalExecution as any;
            const finalPayload =
              rawFinal.result && typeof rawFinal.result === 'object'
                ? rawFinal.result
                : rawFinal.outputs || {};
            nodeExecutionData = mergeLiveNodeOutputMaps(
              nodeExecutionData,
              finalPayload.node_outputs || finalPayload.nodeOutputs
            );
            (finalPayload.executed_nodes || finalPayload.executedNodes || []).forEach(
              (nodeId: unknown) => liveExecutedNodes.add(String(nodeId))
            );
            mergeReportedStatuses(finalPayload.node_statuses);

            const mergedFinal = {
              ...rawFinal,
              input_text: rawFinal.input_text ?? input_text,
              result: {
                ...finalPayload,
                result: finalPayload.result ?? finalPayload.output ?? '',
                executed_nodes: Array.from(liveExecutedNodes),
                node_outputs: { ...nodeExecutionData },
                session_id: finalPayload.session_id ?? liveSessionId,
                status: finalPayload.status ?? rawFinal.status,
              },
            };
            useExecutionsStore
              .getState()
              .setCurrentExecutionForWorkflow(workflow_id, mergedFinal);

            if (rawFinal.status === 'cancelled' || rawFinal.status === 'failed') {
              window.dispatchEvent(new CustomEvent('chat-execution-complete', { detail: {} }));
            }
          }
        } catch (error) {
          console.error('Failed to sync final chat execution status:', error);
        }
      }
    }
  } catch (error) {
    console.error('Chat streaming execution failed:', error);
    throw error;
  }
};

export const useChatStore = create<ChatStore>((set, get) => ({
  chats: {},
  activeChatflowId: null,
  builderChats: {},
  activeBuilderChatflowId: null,
  loading: false,
  thinking: false, // Initialize thinking state
  error: null,

  fetchAllChats: async () => {
    set({ loading: true, error: null });
    try {
      const allChats = await chatService.getAllChats();
      // Replace chats state entirely instead of merging
      set((state) => ({
        chats: allChats,
        loading: false,
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to load chat history', loading: false });
    }
  },

  fetchWorkflowChats: async (workflow_id: string, isBuilder?: boolean) => {
    set({ loading: true, error: null });
    try {
      const workflowChats = await chatService.getWorkflowChats(workflow_id, isBuilder);
      // Replace chats state entirely with workflow-specific chats instead of merging
      set((state) => ({
        chats: workflowChats,
        loading: false,
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to load workflow chat history', loading: false });
    }
  },

  fetchWorkflowBuilderChats: async (workflow_id: string) => {
    set({ loading: true, error: null });
    try {
      const workflowChats = await chatService.getWorkflowChats(workflow_id, true);
      set((state) => ({
        builderChats: workflowChats,
        loading: false,
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to load workflow builder chat history', loading: false });
    }
  },

  loadChatHistory: async () => {
    set({ loading: true, error: null });
    try {
      const allChats = await chatService.getAllChats();
      // Replace chats state entirely instead of merging
      set((state) => ({
        chats: allChats,
        loading: false,
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to load chat history', loading: false });
    }
  },

  startNewChat: async (content, workflow_id) => {
    set({ loading: true, error: null });
    try {
      const messages = await chatService.startNewChat(content, workflow_id);
      const chatflow_id = messages[0]?.chatflow_id;
      if (chatflow_id) {
        set((state) => ({
          chats: { ...state.chats, [chatflow_id]: messages },
          activeChatflowId: chatflow_id,
          loading: false,
        }));
      }
    } catch (e: any) {
      set({ error: e.message || 'Failed to start a new chat', loading: false });
    }
  },

  fetchChatMessages: async (chatflow_id) => {
    set({ loading: true, error: null });
    try {
      const messages = await chatService.getChatMessages(chatflow_id);
      set((state) => {
        // Backend messages are authoritative - just use them directly
        // This replaces any local optimistic updates with the real data
        return {
          chats: { ...state.chats, [chatflow_id]: messages },
          loading: false,
        };
      });
    } catch (e: any) {
      set({ error: e.message || 'Failed to retrieve messages', loading: false });
    }
  },

  fetchBuilderChatMessages: async (chatflow_id) => {
    set({ loading: true, error: null });
    try {
      const messages = await chatService.getChatMessages(chatflow_id);
      set((state) => ({
        builderChats: { ...state.builderChats, [chatflow_id]: messages },
        loading: false,
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to fetch builder messages', loading: false });
    }
  },

  interactWithChat: async (chatflow_id, content, workflow_id) => {
    set({ loading: true, error: null });
    try {
      const messages = await chatService.interactWithChat(chatflow_id, content, workflow_id);
      set((state) => ({
        chats: { ...state.chats, [chatflow_id]: messages },
        loading: false,
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to send message', loading: false });
    }
  },

  setActiveChatflowId: (chatflow_id) => set({ activeChatflowId: chatflow_id }),
  setActiveBuilderChatflowId: (chatflow_id) => set({ activeBuilderChatflowId: chatflow_id }),
  setLoading: (loading) => set({ loading }),
  setThinking: (thinking) => set({ thinking }), // Add setThinking
  setError: (error) => set({ error }),

  addMessage: (chatflow_id, message) =>
    set((state) => {
      const existingMessages = state.chats[chatflow_id] || [];
      const existingIds = new Set(existingMessages.map(m => m.id));

      // Only check by ID - don't check content to avoid dropping valid duplicate messages
      if (existingIds.has(message.id)) {
        return state;
      }

      return {
        chats: {
          ...state.chats,
          [chatflow_id]: [...existingMessages, message],
        },
      };
    }),

  addBuilderMessage: (chatflow_id, message) =>
    set((state) => {
      const existingMessages = state.builderChats[chatflow_id] || [];
      const existingIds = new Set(existingMessages.map(m => m.id));

      if (existingIds.has(message.id)) {
        return state;
      }

      return {
        builderChats: {
          ...state.builderChats,
          [chatflow_id]: [...existingMessages, message],
        },
      };
    }),

  updateMessage: (chatflow_id, message) =>
    set((state) => ({
      chats: {
        ...state.chats,
        [chatflow_id]: (state.chats[chatflow_id] || []).map((m) =>
          m.id === message.id ? message : m
        ),
      },
    })),

  removeMessage: (chatflow_id, message_id) =>
    set((state) => ({
      chats: {
        ...state.chats,
        [chatflow_id]: (state.chats[chatflow_id] || []).filter((m) => m.id !== message_id),
      },
    })),

  clearMessages: async (chatflow_id: string) => {
    try {
      // Send delete request to backend
      await chatService.deleteChatflow(chatflow_id);

      // Also delete from local state
      set((state) => {
        const newChats = { ...state.chats };
        delete newChats[chatflow_id];
        return {
          chats: newChats,
          activeChatflowId: state.activeChatflowId === chatflow_id ? null : state.activeChatflowId,
        };
      });
    } catch (error) {
      console.error('Error occurred while deleting chat:', error);
      // In case of error, revert local delete
      throw error;
    }
  },

  clearBuilderMessages: async (chatflow_id: string) => {
    try {
      // Send delete request to backend
      await chatService.deleteChatflow(chatflow_id);

      // Also delete from local state
      set((state) => {
        const newBuilderChats = { ...state.builderChats };
        delete newBuilderChats[chatflow_id];
        return {
          builderChats: newBuilderChats,
          activeBuilderChatflowId: state.activeBuilderChatflowId === chatflow_id ? null : state.activeBuilderChatflowId,
        };
      });
    } catch (error) {
      console.error('Error occurred while deleting builder chat:', error);
      throw error;
    }
  },

  clearAllChats: () => set({ chats: {} }),

  // LLM integration:
  startLLMChat: async (flow_data, input_text, workflow_id) => {
    set({ loading: true, thinking: true, error: null }); // Set thinking to true

    // Use existing activeChatflowId or generate new one
    let chatflow_id = get().activeChatflowId;
    if (!chatflow_id) {
      chatflow_id = uuidv4();
      get().setActiveChatflowId(chatflow_id);
    }

    // Immediately add user message to UI
    const userMessage: ChatMessage = {
      id: uuidv4(),
      chatflow_id,
      role: 'user',
      content: input_text,
      created_at: new Date().toISOString(),
    };
    get().addMessage(chatflow_id, userMessage);

    try {
      // Use chatflow_id as session_id for memory consistency - now with streaming
      await executeWorkflowWithStreaming(flow_data, input_text, chatflow_id, chatflow_id, workflow_id);
      // Fetch only new messages (agent responses) instead of all messages
      await get().fetchChatMessages(chatflow_id);
    } catch (e: any) {
      set({ error: e.message || 'Failed to start LLM conversation' });
    } finally {
      set({ loading: false, thinking: false }); // Set thinking to false
    }
  },

  sendLLMMessage: async (flow_data, input_text, chatflow_id, workflow_id) => {
    set({ loading: true, thinking: true, error: null }); // Set thinking to true

    // Always add new user message immediately for UI responsiveness
    const userMessage: ChatMessage = {
      id: uuidv4(),
      chatflow_id,
      role: 'user',
      content: input_text,
      created_at: new Date().toISOString(),
    };
    get().addMessage(chatflow_id, userMessage);

    try {
      // Use chatflow_id as session_id for memory consistency - now with streaming
      await executeWorkflowWithStreaming(flow_data, input_text, chatflow_id, chatflow_id, workflow_id);
      // Note: Streaming execution saves messages to backend, so fetch to get the assistant response
      await get().fetchChatMessages(chatflow_id);
    } catch (e: any) {
      set({ error: e.message || 'Failed to send message' });
    } finally {
      set({ loading: false, thinking: false }); // Set thinking to false
    }
  },

  // New function specifically for handling edited messages
  sendEditedMessage: async (flow_data: any, input_text: string, chatflow_id: string, workflow_id: string) => {
    set({ loading: true, thinking: true, error: null }); // Set thinking to true

    try {
      await executeWorkflow(flow_data, input_text, chatflow_id, undefined, workflow_id);
      // Fetch only new messages (agent responses) instead of all messages
      await get().fetchChatMessages(chatflow_id);
    } catch (e: any) {
      set({ error: e.message || 'Failed to send edited message' });
    } finally {
      set({ loading: false, thinking: false }); // Set thinking to false
    }
  },
})); 
