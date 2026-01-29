import type { Position } from "@xyflow/react";

// User and Authentication types
export interface User {
  id: string;
  email: string;
  full_name?: string;
  created_at: string;
  updated_at?: string;
}

export interface UserInfo {
  id: string;
  full_name?: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

export interface SignInRequest {
  email: string;
  password: string;
}

export interface SignUpRequest {
  email: string;
  password: string;
}

// Workflow types
export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    name?: string;
    [key: string]: any;
  };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  type?: string;
}

export interface WorkflowData {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  viewport?: {
    x: number;
    y: number;
    zoom: number;
  };
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  flow_data: WorkflowData;
  user_id: string;
  user?: UserInfo;
  created_at: string;
  updated_at: string;
  is_public: boolean;
  is_active?: boolean;
  version?: number;
}

export interface WorkflowCreateRequest {
  name: string;
  description?: string;
  flow_data: WorkflowData;
  is_public?: boolean;
}

export interface WorkflowUpdateRequest {
  name?: string;
  description?: string;
  flow_data?: WorkflowData;
  is_public?: boolean;
  is_active?: boolean;
}

// Dashboard stats for a single day
export interface DashboardDayStats {
  date: string;
  prodexec: number;
  failedprod: number;
  completed: number;
  avg_runtime_ms: number;
}

// Dashboard stats response from API - contains data for different time periods
export interface WorkflowStats {
  "7days": DashboardDayStats[];
  "30days": DashboardDayStats[];
  "90days": DashboardDayStats[];
}

export interface WorkflowVisibilityUpdate {
  is_public: boolean;
}

export interface WorkflowDuplicateRequest {
  new_name?: string;
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description?: string;
  category?: string;
  flow_data: WorkflowData;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTemplateCreate {
  name: string;
  description?: string;
  category?: string;
  flow_data: WorkflowData;
}

export interface WorkflowTemplateResponse extends WorkflowTemplate { }

export interface WorkflowValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  node_count: number;
  edge_count: number;
}

export interface WorkflowPublicSearchParams {
  skip?: number;
  limit?: number;
  search?: string;
}

export interface WorkflowSearchParams {
  q: string;
  skip?: number;
  limit?: number;
}

export interface WorkflowExecutionResult {
  result: any;
  execution_order?: string[];
  status?: 'completed' | 'failed' | 'running';
  node_count?: number;
  error?: string;
  error_type?: string;
  success?: boolean;
  execution_id?: string;
  executed_nodes?: string[];
  session_id?: string;
  node_outputs?: Record<string, any>;
}

export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  input_text: string;
  result: WorkflowExecutionResult;
  started_at: string;
  completed_at?: string;
  status: 'completed' | 'failed' | 'running';
  runtime?: string;
}

// Node types
export interface NodeInput {
  name: string;
  displayName?: string;
  type: string;
  description?: string;
  required?: boolean;
  default?: any;
  is_connection?: boolean;
  direction?: Position;
}

export interface NodeOutput {
  name: string;
  displayName?: string;
  type: string;
  description?: string;
  direction?: Position;
}

export interface NodeMetadata {
  name: string;
  display_name: string;
  description: string;
  category: string;
  inputs: NodeInput[];
  outputs: NodeOutput[];
  properties: Record<string, any>; // TODO: Replace with NodeProperty[]
  icon?: {
    name?: string;
    path?: string;
    alt?: string;
  };
  colors?: string[];
}

export interface NodeCategory {
  name: string;
  display_name: string;
  icon: string;
}

export interface CustomNode {
  id: string;
  name: string;
  description: string;
  category: string;
  config: Record<string, any>;
  code: string;
  user_id: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomNodeCreateRequest {
  name: string;
  description: string;
  category: string;
  config: Record<string, any>;
  code: string;
  is_public?: boolean;
}

// Credentials types (for future implementation)
export interface UserCredential {
  id: string;
  name: string;
  service_type: string;
  created_at: string;
  updated_at: string;
  data?: Record<string, any>; // opsiyonel
  secret?: Record<string, any>; // opsiyonel
}

export interface UserCredentialCreate {
  name: string;
  service_type: string;
  secret: Record<string, any>;
}

export interface CredentialDetailResponse {
  id: string;
  name: string;
  service_type: string;
  created_at: string;
  updated_at: string;
}

export interface CredentialCreateRequest {
  name: string;
  data: Record<string, any>;
  service_type?: string;
}

// Variables types (for future implementation)
export interface Variable {
  id: string;
  name: string;
  value: string;
  type: string; // enum değil, string olmalı
  description?: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface VariableCreateRequest {
  name: string;
  value: string;
  type: string; // enum değil, string olmalı
  description?: string;
}

// Template types (for future implementation)
export interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  flow_data: WorkflowData;
  user_id: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateCreateRequest {
  name: string;
  description: string;
  category: string;
  flow_data: WorkflowData;
  is_public?: boolean;
}

// API Response wrappers
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

// Health and Info types
export interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  version: string;
  components: {
    database: string;
    node_registry: string;
    session_manager: string;
  };
  warnings?: string[];
}

export interface ApiInfo {
  name: string;
  version: string;
  endpoints: Record<string, string>;
  features: Record<string, string>;
  stats: {
    registered_nodes: number;
    active_sessions: number;
  };
}

// API Key types
export interface ApiKey {
  id: string;
  key_name: string;
  created_at: string;
  last_used_at?: string;
}

export interface ApiKeyCreateRequest {
  key_name: string;
}

export interface ApiKeyUpdateRequest {
  key_name?: string;
}

export interface ApiKeyCreateResponse {
  id: string;
  key_name: string;
  created_at: string;
  last_used_at?: string;
  key: string; // Sadece oluşturulurken döner
}

// Chat types
export interface ChatMessage {
  id: string;
  chatflow_id: string;
  role: string; // 'user' | 'bot' gibi
  content: string;
  source_documents?: string | null;
  created_at: string;
}

export interface ChatMessageInput {
  content: string;
}

// Webhook execution event types
export interface ExecutionEvent {
  type: "node_start" | "node_end" | "complete" | "workflow_complete" | "error" | "token";
  node_id?: string;
  output?: any;
  result?: any;
  error?: string;
  status?: "success" | "failed" | "error";
  metadata?: Record<string, any>;
  event?: string; // Backward compatibility
  inputs?: Record<string, any>;
  inputs_meta?: Record<string, any>;
  node_outputs?: Record<string, any>;
  executed_nodes?: string[];
  session_id?: string;
}

export interface WebhookExecutionEvent {
  type: "webhook_execution_event";
  webhook_id: string;
  workflow_id: string;
  execution_id: string | null;
  event: ExecutionEvent;
  webhook_payload?: Record<string, any>;
  timestamp: string;
}

export interface WebhookStreamEvent {
  type: "connected" | "ping" | "error" | "webhook_execution_event";
  webhook_id?: string;
  timestamp?: string;
  error?: string;
  event?: ExecutionEvent;
  workflow_id?: string;
  execution_id?: string | null;
  webhook_payload?: Record<string, any>;
} 