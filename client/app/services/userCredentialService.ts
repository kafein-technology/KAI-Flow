// User Credential Service Template
import { apiClient } from '~/lib/api-client';
import { API_ENDPOINTS } from '~/lib/config';
import type { UserCredential, CredentialDetailResponse, CredentialCreateRequest } from '~/types/api';

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