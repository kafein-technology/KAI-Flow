import { apiClient } from '~/lib/api-client';
import type {
  ExternalWorkflowConfig,
  ExternalWorkflowInfo,
  ExternalWorkflowRegistration,
  ExternalWorkflowStatus
} from '~/types/external-workflows';

/**
 * Service for managing external Docker workflows
 */
export const externalWorkflowService = {
  /**
   * Register an external Docker workflow
   */
  async registerExternalWorkflow(config: ExternalWorkflowConfig): Promise<ExternalWorkflowRegistration> {
    return await apiClient.post<ExternalWorkflowRegistration>(
      '/external/register',
      config
    );
  },

  /**
   * List all registered external workflows
   */
  async listExternalWorkflows(): Promise<ExternalWorkflowInfo[]> {
    return await apiClient.get<ExternalWorkflowInfo[]>('/external');
  },

  /**
   * Check status of an external workflow
   */
  async checkExternalWorkflowStatus(workflowId: string): Promise<ExternalWorkflowStatus> {
    return await apiClient.get<ExternalWorkflowStatus>(
      `/external/${workflowId}/status`
    );
  },

  /**
   * Get external workflow info (read-only)
   */
  async getExternalWorkflowInfo(workflowId: string): Promise<any> {
    return await apiClient.get<any>(`/external/${workflowId}/info`);
  },

  /**
   * Chat with external workflow (read-only)
   */
  async chatWithExternalWorkflow(workflowId: string, input: string, sessionId?: string): Promise<any> {
    return await apiClient.post<any>(
      `/external/${workflowId}/chat`,
      { input, session_id: sessionId }
    );
  },

  /**
   * List all chat sessions for an external workflow
   */
  async listExternalWorkflowSessions(workflowId: string): Promise<any> {
    return await apiClient.get<any>(`/external/${workflowId}/sessions`);
  },

  /**
   * Get chat history for a specific session
   */
  async getExternalWorkflowSessionHistory(workflowId: string, sessionId: string): Promise<any> {
    return await apiClient.get<any>(`/external/${workflowId}/sessions/${sessionId}/history`);
  },

  /**
   * Clear a specific chat session
   */
  async clearExternalWorkflowSession(workflowId: string, sessionId: string): Promise<any> {
    return await apiClient.delete<any>(`/external/${workflowId}/sessions/${sessionId}`);
  },

  /**
   * Execute an external workflow
   */
  async executeExternalWorkflow(workflowId: string, executionData: any): Promise<any> {
    return await apiClient.post(
      `/external/${workflowId}/execute`,
      executionData
    );
  },

  /**
   * Unregister an external workflow
   */
  async unregisterExternalWorkflow(workflowId: string): Promise<{ message: string; workflow_id: string }> {
    return await apiClient.delete(
      `/external/${workflowId}`
    );
  }
};

/**
 * Service for managing exported workflow instances
 * These are direct API connections to exported workflow containers
 */
export const exportedWorkflowService = {
  /**
   * Execute exported workflow directly
   */
  async executeExportedWorkflow(baseUrl: string, input: string, sessionId?: string, apiKey?: string): Promise<any> {
    // Connect to the selected remote server, independently of this UI's API path.
    const fixedBaseUrl = baseUrl.replace(/\/+$/, '');

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (apiKey && apiKey !== 'api-key-placeholder') {
      headers['X-API-Key'] = apiKey;
    }

    const requestBody: { input: string; session_id?: string } = {
      input: input.trim()
    };

    // Only add session_id if it exists and is not empty
    if (sessionId && sessionId.trim()) {
      requestBody.session_id = sessionId.trim();
    }

    const response = await fetch(`${fixedBaseUrl}/api/v1/workflow/execute`, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Workflow execution failed: ${response.status} - ${errorText}`);
    }

    return await response.json();
  },

  /**
   * Get exported workflow info
   */
  async getExportedWorkflowInfo(baseUrl: string, apiKey?: string): Promise<any> {
    const headers: Record<string, string> = {};

    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }

    const response = await fetch(`${baseUrl.replace(/\/+$/, '')}/api/workflow/external/info`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`Failed to get workflow info: ${response.statusText}`);
    }

    return await response.json();
  },

  /**
   * List chat sessions for exported workflow
   */
  async listExportedWorkflowSessions(baseUrl: string, apiKey?: string): Promise<any> {
    const headers: Record<string, string> = {};

    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }

    const response = await fetch(`${baseUrl.replace(/\/+$/, '')}/api/workflow/sessions`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`Failed to list sessions: ${response.statusText}`);
    }

    return await response.json();
  },

  /**
   * Get session memory for exported workflow
   */
  async getExportedWorkflowSessionMemory(baseUrl: string, sessionId: string, apiKey?: string): Promise<any> {
    const fixedBaseUrl = baseUrl.replace(/\/+$/, '');
    const headers: Record<string, string> = {};

    if (apiKey && apiKey !== 'api-key-placeholder') {
      headers['X-API-Key'] = apiKey;
    }

    const response = await fetch(`${fixedBaseUrl}/api/workflow/memory/${sessionId}`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`Failed to get session memory: ${response.statusText}`);
    }

    return await response.json();
  },

  /**
   * Clear session memory for exported workflow
   */
  async clearExportedWorkflowSessionMemory(baseUrl: string, sessionId: string, apiKey?: string): Promise<any> {
    const headers: Record<string, string> = {};

    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }

    const response = await fetch(`${baseUrl.replace(/\/+$/, '')}/api/workflow/memory/${sessionId}`, {
      method: 'DELETE',
      headers
    });

    if (!response.ok) {
      throw new Error(`Failed to clear session memory: ${response.statusText}`);
    }

    return await response.json();
  },

  /**
   * Ping exported workflow
   */
  async pingExportedWorkflow(baseUrl: string, apiKey?: string): Promise<any> {
    const headers: Record<string, string> = {};

    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }

    const response = await fetch(`${baseUrl.replace(/\/+$/, '')}/api/workflow/external/ping`, {
      method: 'POST',
      headers
    });

    if (!response.ok) {
      throw new Error(`Failed to ping workflow: ${response.statusText}`);
    }

    return await response.json();
  }
};

export default externalWorkflowService;
