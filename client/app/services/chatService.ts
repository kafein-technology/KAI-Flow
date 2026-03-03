import { apiClient } from '../lib/api-client';
import { API_ENDPOINTS } from '../lib/config';
import type { ChatMessage, ChatMessageInput } from '../types/api';

// Tüm chatleri getir (chatflow_id'ye göre gruplanmış)
export const getAllChats = async (): Promise<Record<string, ChatMessage[]>> => {
  return apiClient.get(API_ENDPOINTS.CHAT.LIST);
};

// Yeni chat başlat
export const startNewChat = async (content: string, workflow_id?: string): Promise<ChatMessage[]> => {
  const payload = workflow_id ? { content, workflow_id } : { content };
  return apiClient.post(API_ENDPOINTS.CHAT.CREATE, payload);
};

// Belirli bir chatin mesajlarını getir
export const getChatMessages = async (chatflow_id: string): Promise<ChatMessage[]> => {
  return apiClient.get(API_ENDPOINTS.CHAT.GET(chatflow_id));
};

// Chat'e mesaj gönder (interact)
export const interactWithChat = async (chatflow_id: string, content: string, workflow_id?: string): Promise<ChatMessage[]> => {
  const payload = workflow_id ? { content, workflow_id } : { content };
  return apiClient.post(API_ENDPOINTS.CHAT.INTERACT(chatflow_id), payload);
};

// Mesajı güncelle
export const updateChatMessage = async (chat_message_id: string, content: string): Promise<ChatMessage[]> => {
  return apiClient.put(API_ENDPOINTS.CHAT.UPDATE(chat_message_id), { content });
};

// Mesajı sil
export const deleteChatMessage = async (chat_message_id: string): Promise<{ detail: string }> => {
  return apiClient.delete(API_ENDPOINTS.CHAT.DELETE(chat_message_id));
};

// Chatflow'u sil (tüm mesajları)
export const deleteChatflow = async (chatflow_id: string): Promise<{ detail: string }> => {
  return apiClient.delete(API_ENDPOINTS.CHAT.DELETE_CHATFLOW(chatflow_id));
};

// Workflow'a özel chat history getir
export const getWorkflowChats = async (workflow_id: string): Promise<Record<string, ChatMessage[]>> => {
  return apiClient.get(API_ENDPOINTS.CHAT.GET_WORKFLOW_CHATS(workflow_id));
};

// En son aktif session ID'yi getir
export const getActiveSessionId = async (chatflow_id?: string): Promise<{ session_id: string | null }> => {
  const params = chatflow_id ? `?chatflow_id=${chatflow_id}` : '';
  return apiClient.get(`${API_ENDPOINTS.CHAT.ACTIVE_SESSION.ID}${params}`);
};