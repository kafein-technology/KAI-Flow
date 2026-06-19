import { apiClient } from '../lib/api-client';
import { API_ENDPOINTS } from '../lib/config';

export const AIBuilderService = {
  async generateWorkflow(
    question: string,
    options: {
      credentialId: string;
      modelName: string;
      baseUrl?: string;
      mode?: 'build' | 'edit';
      existingWorkflow?: { nodes: any[]; edges: any[] };
    }
  ) {
    const response = await apiClient.post<any>(API_ENDPOINTS.AI_BUILDER.GENERATE, {
      question,
      credential_id: options.credentialId,
      model_name: options.modelName,
      base_url: options.baseUrl || undefined,
      mode: options.mode || 'build',
      existing_workflow: options.existingWorkflow || null,
    });
    return response;
  }
};
