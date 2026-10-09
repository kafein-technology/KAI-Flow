// User Credential Service Template
import { apiClient } from '~/lib/api-client';
import { API_ENDPOINTS } from '~/lib/config';
import type {
  UserCredential,
  CredentialDetailResponse,
  CredentialCreateRequest,
  CredentialWorkflowUsageResponse,
} from '~/types/api';

export const getUserCredentials = async (): Promise<UserCredential[]> => {
  return await apiClient.get<UserCredential[]>(API_ENDPOINTS.CREDENTIALS.LIST);
};

export const getUserCredentialById = async (id: string): Promise<UserCredential> => {
  return await apiClient.get<UserCredential>(API_ENDPOINTS.CREDENTIALS.GET(id));
};

export const createUserCredential = async (data: CredentialCreateRequest): Promise<CredentialDetailResponse> => {
  return await apiClient.post<CredentialDetailResponse>(API_ENDPOINTS.CREDENTIALS.CREATE, data);
};

export const updateUserCredential = async (id: string, data: Partial<CredentialCreateRequest>): Promise<CredentialDetailResponse> => {
  return await apiClient.put<CredentialDetailResponse>(API_ENDPOINTS.CREDENTIALS.UPDATE(id), data);
};

export const deleteUserCredential = async (id: string): Promise<{ message: string; deleted_id: string }> => {
  return await apiClient.delete<{ message: string; deleted_id: string }>(API_ENDPOINTS.CREDENTIALS.DELETE(id));
};

export const testUserCredential = async (id: string): Promise<{ success: boolean; message: string }> => {
  return await apiClient.post<{ success: boolean; message: string }>(API_ENDPOINTS.CREDENTIALS.TEST(id), {});
};

export const testCredentialRaw = async (
  serviceType: string,
  data: Record<string, any>
): Promise<{ success: boolean; message: string }> => {
  return await apiClient.post<{ success: boolean; message: string }>(
    API_ENDPOINTS.CREDENTIALS.TEST_RAW,
    { service_type: serviceType, data }
  );
};

export const getCredentialWorkflows = async (
  id: string
): Promise<CredentialWorkflowUsageResponse> => {
  return await apiClient.get<CredentialWorkflowUsageResponse>(
    API_ENDPOINTS.CREDENTIALS.WORKFLOWS(id)
  );
};

export interface CredentialModelOption {
  id: string;
  owned_by?: string | null;
}

export interface CredentialModelsResponse {
  models: CredentialModelOption[];
  source: 'provider' | 'empty' | string;
  message?: string | null;
}

export const getCredentialModels = async (
  id: string
): Promise<CredentialModelsResponse> => {
  return await apiClient.get<CredentialModelsResponse>(
    API_ENDPOINTS.CREDENTIALS.MODELS(id)
  );
};

export const listModelsRaw = async (
  serviceType: string,
  data: Record<string, any>
): Promise<CredentialModelsResponse> => {
  return await apiClient.post<CredentialModelsResponse>(
    API_ENDPOINTS.CREDENTIALS.LIST_MODELS,
    { service_type: serviceType, data }
  );
};