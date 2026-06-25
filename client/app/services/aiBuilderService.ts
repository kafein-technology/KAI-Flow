import { apiClient } from '../lib/api-client';
import { API_ENDPOINTS } from '../lib/config';

export const AIBuilderService = {
  async generateWorkflow(
    question: string,
    options: {
      credentialId: string;
      modelName?: string;
      baseUrl?: string;
      mode?: 'build' | 'edit';
      existingWorkflow?: { nodes: any[]; edges: any[] };
      verifySsl?: boolean;
      extraBodyParams?: string;
      workflowId?: string;
      chatflowId?: string;
    }
  ) {
    const response = await apiClient.post<any>(API_ENDPOINTS.AI_BUILDER.GENERATE, {
      question,
      credential_id: options.credentialId,
      model_name: options.modelName || 'gpt-4o',
      base_url: options.baseUrl || undefined,
      mode: options.mode || 'build',
      existing_workflow: options.existingWorkflow || null,
      verify_ssl: options.verifySsl !== undefined ? options.verifySsl : null,
      extra_body_params: options.extraBodyParams || null,
      workflow_id: options.workflowId || null,
      chatflow_id: options.chatflowId || null,
    });
    return response;
  }
};
