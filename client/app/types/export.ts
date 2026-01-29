export interface WorkflowExportConfig {
    include_credentials?: boolean;
    export_format?: 'docker' | 'json' | string;
}

export interface WorkflowExportInitResponse {
    missing_env_vars: string[];
    config: WorkflowExportConfig;
}

export interface WorkflowExportCompleteRequest {
    env_vars: Record<string, string>;
    [key: string]: any;
}

export interface WorkflowExportCompleteResponse {
    download_url: string;
}
