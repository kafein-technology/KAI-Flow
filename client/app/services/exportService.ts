import { apiClient } from '~/lib/api-client';
import { API_ENDPOINTS, config } from '~/lib/config';
import type {
  WorkflowExportInitResponse,
  WorkflowExportCompleteRequest,
  WorkflowExportCompleteResponse,
  WorkflowExportConfig
} from '~/types/export';

export interface ExportRequest {
  workflow_ids: string[];
}

/**
 * Service for handling workflow Docker export operations
 */
export const exportService = {
  /**
   * Initialize workflow export and get required environment variables
   */
  async initializeExport(workflowId: string, config: WorkflowExportConfig = {}): Promise<WorkflowExportInitResponse> {
    return await apiClient.post<WorkflowExportInitResponse>(
      API_ENDPOINTS.EXPORT.WORKFLOW_INIT(workflowId),
      {
        include_credentials: config.include_credentials || false,
        export_format: config.export_format || "docker"
      }
    );
  },

  /**
   * Complete workflow export with user-provided environment variables
   */
  async completeExport(
    workflowId: string,
    config: WorkflowExportCompleteRequest
  ): Promise<WorkflowExportCompleteResponse> {
    return await apiClient.post<WorkflowExportCompleteResponse>(
      API_ENDPOINTS.EXPORT.WORKFLOW_COMPLETE(workflowId),
      config
    );
  },

  /**
   * Export selected workflows as a ZIP file download.
   *
   * @param workflowIds - Array of workflow UUIDs to export
   * @returns Promise that triggers file download
   */
  async exportWorkflows(workflowIds: string[]): Promise<void> {
    // apiClient.post returns response.data directly (the blob)
    const data = await apiClient.post(
      API_ENDPOINTS.EXPORT.WORKFLOWS,
      { workflow_ids: workflowIds },
      {
        responseType: 'blob',
      }
    );

    // Generate filename with timestamp
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '').slice(0, 14);
    const filename = `workflows_export_${timestamp}.zip`;

    // Create blob and trigger download
    const blob = new Blob([data], { type: 'application/zip' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Download the exported workflow package
   */
  async downloadPackage(downloadUrl: string): Promise<void> {
    try {
      // Extract the endpoint path from download URL
      const apiPrefix = `/${config.API_START}/${config.API_VERSION_ONLY}`;
      const endpoint = downloadUrl.startsWith(apiPrefix)
        ? downloadUrl.replace(apiPrefix, '')
        : downloadUrl;

      console.log('Downloading from endpoint:', endpoint);

      // Use apiClient for consistent base URL and authentication
      const response = await fetch(`${apiClient.getBaseURL()}${endpoint}`, {
        headers: {
          'Authorization': `Bearer ${apiClient.getAccessToken()}`
        }
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status} ${response.statusText}`);
      }

      const blob = await response.blob();
      const filename = downloadUrl.split('/').pop() || 'workflow-export.zip';

      // Create download link and trigger download
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Clean up blob URL
      URL.revokeObjectURL(link.href);

    } catch (error) {
      console.error('Download failed:', error);
      throw new Error('Failed to download export package');
    }
  }
};

export const {
  initializeExport,
  completeExport,
  exportWorkflows,
  downloadPackage
} = exportService;

export default exportService;
