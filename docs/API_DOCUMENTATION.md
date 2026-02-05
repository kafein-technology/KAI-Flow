# KAI-Flow API Documentation

## Table of Contents
1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Workflow Management](#workflow-management)
4. [Node System](#node-system)
5. [User Management](#user-management)
6. [Credential Management](#credential-management)
7. [Health & Monitoring](#health--monitoring)
8. [Error Handling](#error-handling)
9. [Data Models](#data-models)
10. [Examples & Use Cases](#examples--use-cases)

---

## API Overview

### Base Configuration
- **Base URL**: `http://localhost:8001`
- **API Version**: `/{API_START}/{API_VERSION_ONLY}`
- **Content Type**: `application/json`
- **Authentication**: Bearer JWT tokens

### Available Endpoints
```
Authentication:
- POST   /{API_START}/{API_VERSION_ONLY}/auth/signup
- POST   /{API_START}/{API_VERSION_ONLY}/auth/signin  
- POST   /{API_START}/{API_VERSION_ONLY}/auth/refresh
- GET    /{API_START}/{API_VERSION_ONLY}/auth/profile

Workflows:
- GET    /{API_START}/{API_VERSION_ONLY}/workflows
- POST   /{API_START}/{API_VERSION_ONLY}/workflows
- GET    /{API_START}/{API_VERSION_ONLY}/workflows/{id}
- PUT    /{API_START}/{API_VERSION_ONLY}/workflows/{id}
- DELETE /{API_START}/{API_VERSION_ONLY}/workflows/{id}
- POST   /{API_START}/{API_VERSION_ONLY}/workflows/execute
- POST   /{API_START}/{API_VERSION_ONLY}/workflows/{id}/execute/stream
- POST   /{API_START}/{API_VERSION_ONLY}/workflows/validate

Nodes:
- GET    /{API_START}/{API_VERSION_ONLY}/nodes
- GET    /{API_START}/{API_VERSION_ONLY}/nodes/categories
- GET    /{API_START}/{API_VERSION_ONLY}/nodes/{type}

Users:
- GET    /{API_START}/{API_VERSION_ONLY}/users/me
- PUT    /{API_START}/{API_VERSION_ONLY}/users/me

Credentials:
- POST   /{API_START}/{API_VERSION_ONLY}/credentials/validate

System:
- GET    /health
- GET    /info
```

---

## Authentication

### JWT-Based Authentication Flow

#### 1. User Registration
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/auth/signup`

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response** (201 Created):
```json
{
  "user": {
    "id": "user_123abc",
    "email": "user@example.com",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "def50200a8b9c4d7e2f8...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**cURL Example**:
```bash
curl -X POST "http://localhost:8001/{API_START}/{API_VERSION_ONLY}/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123"
  }'
```

#### 2. User Login
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/auth/signin`

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response** (200 OK):
```json
{
  "user": {
    "id": "user_123abc",
    "email": "user@example.com",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "def50200a8b9c4d7e2f8...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### 3. Token Refresh
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/auth/refresh`

**Request Body**:
```json
{
  "refresh_token": "def50200a8b9c4d7e2f8..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### 4. Get User Profile
**Endpoint**: `GET /{API_START}/{API_VERSION_ONLY}/auth/profile`

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response** (200 OK):
```json
{
  "id": "user_123abc",
  "email": "user@example.com",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-20T14:25:00Z"
}
```

---

## Workflow Management

### 1. List User Workflows
**Endpoint**: `GET /{API_START}/{API_VERSION_ONLY}/workflows`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `limit` (optional): Items per page (default: 20)
- `search` (optional): Search workflows by name

**Response** (200 OK):
```json
{
  "data": [
    {
      "id": "workflow_456def",
      "name": "Customer Support Bot",
      "description": "Automated customer support workflow",
      "flow_data": {
        "nodes": [...],
        "edges": [...],
        "viewport": {"x": 0, "y": 0, "zoom": 1}
      },
      "user_id": "user_123abc",
      "created_at": "2024-01-15T11:00:00Z",
      "updated_at": "2024-01-16T09:30:00Z",
      "is_active": true
    }
  ],
  "total": 5,
  "page": 1,
  "limit": 20,
  "has_more": false
}
```

### 2. Create New Workflow
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/workflows`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "name": "AI Content Generator",
  "description": "Generate blog content using AI",
  "flow_data": {
    "nodes": [
      {
        "id": "start_1",
        "type": "StartNode",
        "position": {"x": 100, "y": 100},
        "data": {"name": "Start"}
      },
      {
        "id": "openai_1",
        "type": "OpenAIChat",
        "position": {"x": 300, "y": 100},
        "data": {
          "model_name": "gpt-4",
          "temperature": 0.7,
          "max_tokens": 1000
        }
      }
    ],
    "edges": [
      {
        "id": "edge_1",
        "source": "start_1",
        "target": "openai_1",
        "type": "default"
      }
    ],
    "viewport": {"x": 0, "y": 0, "zoom": 1}
  }
}
```

**Response** (201 Created):
```json
{
  "id": "workflow_789ghi",
  "name": "AI Content Generator",
  "description": "Generate blog content using AI",
  "flow_data": {
    "nodes": [...],
    "edges": [...],
    "viewport": {"x": 0, "y": 0, "zoom": 1}
  },
  "user_id": "user_123abc",
  "created_at": "2024-01-20T15:45:00Z",
  "updated_at": "2024-01-20T15:45:00Z",
  "is_active": true
}
```

### 3. Execute Workflow (Synchronous)
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/workflows/execute`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "workflow_id": "workflow_456def",
  "input_text": "Write a blog post about artificial intelligence",
  "session_context": {
    "user_preferences": {
      "tone": "professional",
      "length": "medium"
    }
  }
}
```

**Alternative Request (Direct Flow Data)**:
```json
{
  "flow_data": {
    "nodes": [
      {
        "id": "start_1",
        "type": "StartNode",
        "position": {"x": 100, "y": 100},
        "data": {"name": "Start"}
      },
      {
        "id": "openai_1",
        "type": "OpenAIChat",
        "position": {"x": 300, "y": 100},
        "data": {
          "model_name": "gpt-4",
          "temperature": 0.7,
          "max_tokens": 1000,
          "api_key": "sk-..."
        }
      }
    ],
    "edges": [
      {
        "id": "edge_1",
        "source": "start_1",
        "target": "openai_1"
      }
    ]
  },
  "input_text": "Explain quantum computing"
}
```

**Response** (200 OK):
```json
{
  "result": {
    "content": "Artificial Intelligence (AI) is a transformative technology...",
    "final_output": "Complete blog post content here...",
    "metadata": {
      "total_tokens": 850,
      "processing_time": 2.3
    }
  },
  "execution_order": ["start_1", "openai_1"],
  "status": "completed",
  "node_count": 2,
  "success": true,
  "execution_id": "exec_xyz789",
  "executed_nodes": ["start_1", "openai_1"],
  "session_id": "session_abc123"
}
```

### 4. Execute Workflow with Streaming
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/workflows/{workflow_id}/execute/stream`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
Accept: text/event-stream
```

**Request Body**:
```json
{
  "input_text": "Create a marketing strategy for a tech startup",
  "session_context": {
    "company": "TechCorp",
    "industry": "SaaS"
  }
}
```

**Response** (200 OK - Server-Sent Events):
```
data: {"type": "start", "message": "Workflow execution started", "timestamp": "2024-01-20T16:00:00Z"}

data: {"type": "node_start", "node_id": "start_1", "node_name": "Start", "timestamp": "2024-01-20T16:00:01Z"}

data: {"type": "node_complete", "node_id": "start_1", "output": {"input": "Create a marketing strategy..."}, "timestamp": "2024-01-20T16:00:02Z"}

data: {"type": "node_start", "node_id": "openai_1", "node_name": "OpenAI Chat", "timestamp": "2024-01-20T16:00:02Z"}

data: {"type": "partial_result", "node_id": "openai_1", "content": "Marketing Strategy for TechCorp\n\n1. Target Audience Analysis...", "timestamp": "2024-01-20T16:00:05Z"}

data: {"type": "node_complete", "node_id": "openai_1", "output": {"content": "Complete marketing strategy document..."}, "timestamp": "2024-01-20T16:00:08Z"}

data: {"type": "complete", "result": {"final_output": "Complete marketing strategy..."}, "execution_time": 8.2, "timestamp": "2024-01-20T16:00:08Z"}
```

### 5. Validate Workflow Structure
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/workflows/validate`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "flow_data": {
    "nodes": [
      {
        "id": "start_1",
        "type": "StartNode",
        "position": {"x": 100, "y": 100},
        "data": {"name": "Start"}
      },
      {
        "id": "invalid_node",
        "type": "NonExistentNode",
        "position": {"x": 300, "y": 100},
        "data": {}
      }
    ],
    "edges": [
      {
        "id": "edge_1",
        "source": "start_1",
        "target": "invalid_node"
      }
    ]
  }
}
```

**Response** (200 OK - Invalid):
```json
{
  "valid": false,
  "errors": [
    {
      "node_id": "invalid_node",
      "error": "Unknown node type: NonExistentNode",
      "code": "INVALID_NODE_TYPE"
    }
  ],
  "warnings": []
}
```

**Response** (200 OK - Valid):
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    {
      "node_id": "openai_1",
      "warning": "API key not provided, execution may fail",
      "code": "MISSING_CREDENTIALS"
    }
  ]
}
```

---

## Node System

### 1. List All Available Nodes
**Endpoint**: `GET /{API_START}/{API_VERSION_ONLY}/nodes`

**Response** (200 OK):
```json
{
  "nodes": [
    {
      "id": "OpenAIChat",
      "type": "OpenAIChat",
      "name": "OpenAI Chat",
      "display_name": "OpenAI Chat Model",
      "category": "llms",
      "description": "OpenAI GPT models for text generation",
      "inputs": [
        {
          "name": "messages",
          "type": "array",
          "description": "Chat messages array",
          "required": true
        },
        {
          "name": "model_name",
          "type": "string",
          "description": "OpenAI model name",
          "default": "gpt-3.5-turbo"
        },
        {
          "name": "temperature",
          "type": "number",
          "description": "Response randomness (0-2)",
          "default": 0.7
        },
        {
          "name": "max_tokens",
          "type": "number",
          "description": "Maximum response length",
          "default": 500
        }
      ],
      "outputs": [
        {
          "name": "content",
          "type": "string",
          "description": "Generated text response"
        }
      ],
      "info": "Generate text responses using OpenAI's language models",
      "icon": "openai",
      "color": "#10A37F"
    },
    {
      "id": "ReactAgent",
      "type": "ReactAgent",
      "name": "React Agent",
      "display_name": "ReAct Agent",
      "category": "agents",
      "description": "Autonomous reasoning and acting agent",
      "inputs": [
        {
          "name": "input",
          "type": "string",
          "description": "User query or task",
          "required": true
        },
        {
          "name": "tools",
          "type": "array",
          "description": "Available tools for the agent",
          "default": []
        },
        {
          "name": "max_iterations",
          "type": "number",
          "description": "Maximum reasoning iterations",
          "default": 10
        }
      ],
      "outputs": [
        {
          "name": "output",
          "type": "string",
          "description": "Agent's final response"
        },
        {
          "name": "intermediate_steps",
          "type": "array",
          "description": "Reasoning steps taken"
        }
      ],
      "info": "AI agent that can reason about tasks and use tools",
      "icon": "bot",
      "color": "#3B82F6"
    }
  ],
  "total": 55,
  "categories": [
    {"name": "llms", "display_name": "Language Models", "count": 3},
    {"name": "agents", "display_name": "AI Agents", "count": 2},
    {"name": "tools", "display_name": "External Tools", "count": 10},
    {"name": "memory", "display_name": "Memory", "count": 3},
    {"name": "chains", "display_name": "Chains", "count": 4},
    {"name": "document_loaders", "display_name": "Document Loaders", "count": 5},
    {"name": "embeddings", "display_name": "Embeddings", "count": 3},
    {"name": "vectorstores", "display_name": "Vector Stores", "count": 4}
  ]
}
```

### 2. Get Node Categories
**Endpoint**: `GET /{API_START}/{API_VERSION_ONLY}/nodes/categories`

**Response** (200 OK):
```json
{
  "categories": [
    {
      "name": "llms",
      "display_name": "Language Models",
      "description": "AI models for text generation and understanding",
      "icon": "brain",
      "nodes": ["OpenAIChat", "AnthropicClaude", "GoogleGemini"]
    },
    {
      "name": "agents", 
      "display_name": "AI Agents",
      "description": "Autonomous AI agents that can reason and act",
      "icon": "robot",
      "nodes": ["ReactAgent", "ToolAgent"]
    },
    {
      "name": "tools",
      "display_name": "External Tools", 
      "description": "Integrations with external services and APIs",
      "icon": "wrench",
      "nodes": ["GoogleSearchTool", "WikipediaTool", "TavilySearch"]
    }
  ]
}
```

### 3. Get Specific Node Details
**Endpoint**: `GET /{API_START}/{API_VERSION_ONLY}/nodes/{node_type}`

**Example**: `GET /{API_START}/{API_VERSION_ONLY}/nodes/OpenAIChat`

**Response** (200 OK):
```json
{
  "id": "OpenAIChat",
  "type": "OpenAIChat", 
  "name": "OpenAI Chat",
  "display_name": "OpenAI Chat Model",
  "category": "llms",
  "description": "Generate responses using OpenAI's GPT models including GPT-3.5, GPT-4, and GPT-4o",
  "inputs": [
    {
      "name": "messages",
      "type": "array",
      "description": "Array of chat messages in OpenAI format",
      "required": true,
      "example": [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"}
      ]
    },
    {
      "name": "model_name",
      "type": "string",
      "description": "OpenAI model to use",
      "required": false,
      "default": "gpt-3.5-turbo",
      "options": ["gpt-3.5-turbo", "gpt-4", "gpt-4o", "gpt-4-turbo"]
    },
    {
      "name": "temperature",
      "type": "number",
      "description": "Controls randomness in output (0.0 to 2.0)",
      "required": false,
      "default": 0.7,
      "min": 0.0,
      "max": 2.0
    },
    {
      "name": "max_tokens",
      "type": "number", 
      "description": "Maximum number of tokens in response",
      "required": false,
      "default": 500,
      "min": 1,
      "max": 4096
    },
    {
      "name": "api_key",
      "type": "string",
      "description": "OpenAI API key",
      "required": true,
      "sensitive": true
    }
  ],
  "outputs": [
    {
      "name": "content",
      "type": "string",
      "description": "Generated text response from the model"
    },
    {
      "name": "usage",
      "type": "object",
      "description": "Token usage information",
      "properties": {
        "prompt_tokens": "number",
        "completion_tokens": "number", 
        "total_tokens": "number"
      }
    }
  ],
  "examples": [
    {
      "name": "Simple Chat",
      "description": "Basic chat interaction",
      "input": {
        "messages": [
          {"role": "user", "content": "What is artificial intelligence?"}
        ],
        "model_name": "gpt-3.5-turbo",
        "temperature": 0.7
      },
      "output": {
        "content": "Artificial intelligence (AI) is a branch of computer science..."
      }
    }
  ],
  "documentation": "https://platform.openai.com/docs/guides/text-generation",
  "pricing_info": "Varies by model - see OpenAI pricing page",
  "rate_limits": "Depends on OpenAI tier and model"
}
```

---

## User Management

### 1. Get Current User
**Endpoint**: `GET /{API_START}/{API_VERSION_ONLY}/users/me`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "id": "user_123abc",
  "email": "user@example.com",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-20T14:25:00Z",
  "profile": {
    "display_name": "John Doe",
    "preferences": {
      "theme": "light",
      "notifications": true,
      "default_model": "gpt-4"
    }
  },
  "usage_stats": {
    "workflows_created": 12,
    "executions_this_month": 145,
    "total_executions": 1247
  }
}
```

### 2. Update User Profile
**Endpoint**: `PUT /{API_START}/{API_VERSION_ONLY}/users/me`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "profile": {
    "display_name": "John Smith",
    "preferences": {
      "theme": "dark",
      "notifications": false,
      "default_model": "gpt-4o"
    }
  }
}
```

**Response** (200 OK):
```json
{
  "id": "user_123abc",
  "email": "user@example.com",
  "updated_at": "2024-01-20T16:45:00Z",
  "profile": {
    "display_name": "John Smith",
    "preferences": {
      "theme": "dark",
      "notifications": false,
      "default_model": "gpt-4o"
    }
  }
}
```

---

## Credential Management

### 1. Validate API Credentials
**Endpoint**: `POST /{API_START}/{API_VERSION_ONLY}/credentials/validate`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body** (OpenAI):
```json
{
  "type": "openai",
  "api_key": "sk-proj-...",
  "model_name": "gpt-4"
}
```

**Request Body** (Anthropic):
```json
{
  "type": "anthropic",
  "api_key": "sk-ant-...",
  "model_name": "claude-3-opus-20240229"
}
```

**Response** (200 OK - Valid):
```json
{
  "valid": true,
  "message": "Credentials validated successfully",
  "provider": "openai",
  "model_info": {
    "model": "gpt-4",
    "max_tokens": 8192,
    "supports_streaming": true,
    "cost_per_1k_tokens": {
      "input": 0.03,
      "output": 0.06
    }
  }
}
```

**Response** (400 Bad Request - Invalid):
```json
{
  "valid": false,
  "message": "Invalid API key or insufficient permissions",
  "error_code": "INVALID_CREDENTIALS",
  "provider": "openai"
}
```

---

## Health & Monitoring

### 1. Health Check
**Endpoint**: `GET /health`

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-20T17:00:00Z",
  "components": {
    "database": "healthy",
    "node_registry": "healthy", 
    "session_manager": "healthy",
    "redis": "healthy"
  },
  "metrics": {
    "uptime_seconds": 86400,
    "total_requests": 15042,
    "active_sessions": 23,
    "memory_usage_mb": 512
  },
  "warnings": []
}
```

### 2. System Information
**Endpoint**: `GET /info`

**Response** (200 OK):
```json
{
  "name": "KAI-Flow API",
  "version": "1.0.0",
  "description": "AI Workflow Automation Platform",
  "documentation": "http://localhost:8001/docs",
  "features": {
    "node_system": "Auto-discovery with 55+ nodes",
    "streaming": "Server-sent events for real-time execution",
    "authentication": "JWT with refresh tokens",
    "multi_ai": "OpenAI, Anthropic, Google Gemini support"
  },
  "stats": {
    "registered_nodes": 55,
    "active_sessions": 23,
    "total_users": 150,
    "total_workflows": 1200
  },
  "endpoints": {
    "auth": "/{API_START}/{API_VERSION_ONLY}/auth",
    "workflows": "/{API_START}/{API_VERSION_ONLY}/workflows", 
    "nodes": "/{API_START}/{API_VERSION_ONLY}/nodes",
    "users": "/{API_START}/{API_VERSION_ONLY}/users",
    "credentials": "/{API_START}/{API_VERSION_ONLY}/credentials"
  }
}
```

---

## Error Handling

### HTTP Status Codes
- **200 OK**: Successful request
- **201 Created**: Resource created successfully  
- **400 Bad Request**: Invalid request data
- **401 Unauthorized**: Invalid or missing authentication
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation errors
- **500 Internal Server Error**: Server error

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "code": "INVALID_EMAIL"
      },
      {
        "field": "password", 
        "message": "Password must be at least 8 characters",
        "code": "PASSWORD_TOO_SHORT"
      }
    ]
  },
  "timestamp": "2024-01-20T17:15:00Z",
  "request_id": "req_abc123"
}
```

### Common Error Codes
- `VALIDATION_ERROR`: Input validation failed
- `AUTHENTICATION_FAILED`: Invalid credentials
- `TOKEN_EXPIRED`: Access token has expired
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `PERMISSION_DENIED`: User lacks required permissions
- `WORKFLOW_EXECUTION_FAILED`: Workflow execution error
- `NODE_EXECUTION_ERROR`: Specific node failed during execution
- `INVALID_CREDENTIALS`: API key validation failed
- `RATE_LIMIT_EXCEEDED`: Too many requests

---

## Data Models

### Core Models

#### User Model
```json
{
  "id": "string (UUID)",
  "email": "string (email format)",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)",
  "profile": {
    "display_name": "string",
    "preferences": "object"
  }
}
```

#### Workflow Model
```json
{
  "id": "string (UUID)",
  "name": "string",
  "description": "string (optional)",
  "flow_data": {
    "nodes": "array of WorkflowNode",
    "edges": "array of WorkflowEdge", 
    "viewport": {
      "x": "number",
      "y": "number", 
      "zoom": "number"
    }
  },
  "user_id": "string (UUID)",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)",
  "is_active": "boolean"
}
```

#### WorkflowNode Model
```json
{
  "id": "string",
  "type": "string (node type)",
  "position": {
    "x": "number",
    "y": "number"
  },
  "data": {
    "name": "string (optional)",
    "additional_properties": "any"
  }
}
```

#### WorkflowEdge Model
```json
{
  "id": "string",
  "source": "string (source node ID)",
  "target": "string (target node ID)",
  "sourceHandle": "string (optional)",
  "targetHandle": "string (optional)",
  "type": "string (optional)"
}
```

#### Execution Result Model
```json
{
  "result": "any (final output)",
  "execution_order": "array of string (node IDs)",
  "status": "string (completed|failed|running)",
  "node_count": "number",
  "success": "boolean",
  "execution_id": "string (UUID)",
  "executed_nodes": "array of string",
  "session_id": "string",
  "error": "string (optional)",
  "error_type": "string (optional)"
}
```

---

## Examples & Use Cases

### Example 1: Simple Chatbot Workflow

#### Create Workflow
```bash
curl -X POST "http://localhost:8001/{API_START}/{API_VERSION_ONLY}/workflows" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Simple Chatbot",
    "description": "Basic AI chatbot using OpenAI",
    "flow_data": {
      "nodes": [
        {
          "id": "start_1",
          "type": "StartNode",
          "position": {"x": 100, "y": 100},
          "data": {"name": "User Input"}
        },
        {
          "id": "openai_1", 
          "type": "OpenAIChat",
          "position": {"x": 400, "y": 100},
          "data": {
            "model_name": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 500,
            "api_key": "sk-proj-..."
          }
        }
      ],
      "edges": [
        {
          "id": "edge_1",
          "source": "start_1",
          "target": "openai_1"
        }
      ]
    }
  }'
```

#### Execute Workflow
```bash
curl -X POST "http://localhost:8001/{API_START}/{API_VERSION_ONLY}/workflows/execute" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "workflow_123",
    "input_text": "Hello, how are you?",
    "session_context": {}
  }'
```

### Example 2: Document Analysis Workflow

#### Workflow with Memory
```json
{
  "name": "Document Q&A with Memory",
  "description": "Answer questions about documents with conversation memory",
  "flow_data": {
    "nodes": [
      {
        "id": "start_1",
        "type": "StartNode",
        "position": {"x": 50, "y": 100},
        "data": {"name": "Question Input"}
      },
      {
        "id": "memory_1",
        "type": "BufferMemory", 
        "position": {"x": 200, "y": 100},
        "data": {
          "memory_key": "chat_history",
          "return_messages": true
        }
      },
      {
        "id": "pdf_loader_1",
        "type": "PDFLoader",
        "position": {"x": 200, "y": 250},
        "data": {
          "file_path": "/documents/manual.pdf"
        }
      },
      {
        "id": "openai_1",
        "type": "OpenAIChat",
        "position": {"x": 450, "y": 175},
        "data": {
          "model_name": "gpt-4",
          "temperature": 0.3,
          "system_prompt": "Answer questions based on the provided document context and conversation history."
        }
      }
    ],
    "edges": [
      {"id": "e1", "source": "start_1", "target": "memory_1"},
      {"id": "e2", "source": "start_1", "target": "pdf_loader_1"},
      {"id": "e3", "source": "memory_1", "target": "openai_1"},
      {"id": "e4", "source": "pdf_loader_1", "target": "openai_1"}
    ]
  }
}
```

### Example 3: Multi-Agent Research Workflow

#### Agent Collaboration Setup
```json
{
  "name": "Multi-Agent Research",
  "description": "Research agents collaborating on complex topics",
  "flow_data": {
    "nodes": [
      {
        "id": "start_1",
        "type": "StartNode",
        "position": {"x": 50, "y": 200},
        "data": {"name": "Research Topic"}
      },
      {
        "id": "research_agent_1",
        "type": "ReactAgent",
        "position": {"x": 250, "y": 100},
        "data": {
          "name": "Research Agent",
          "tools": ["GoogleSearchTool", "WikipediaTool"],
          "system_prompt": "You are a research specialist. Gather comprehensive information on the given topic."
        }
      },
      {
        "id": "analysis_agent_1", 
        "type": "ReactAgent",
        "position": {"x": 250, "y": 300},
        "data": {
          "name": "Analysis Agent",
          "system_prompt": "You are an analysis expert. Synthesize and analyze the research findings."
        }
      },
      {
        "id": "writer_agent_1",
        "type": "OpenAIChat",
        "position": {"x": 500, "y": 200},
        "data": {
          "name": "Writer Agent",
          "model_name": "gpt-4",
          "system_prompt": "You are a professional writer. Create a comprehensive report based on research and analysis."
        }
      }
    ],
    "edges": [
      {"id": "e1", "source": "start_1", "target": "research_agent_1"},
      {"id": "e2", "source": "start_1", "target": "analysis_agent_1"},
      {"id": "e3", "source": "research_agent_1", "target": "writer_agent_1"},
      {"id": "e4", "source": "analysis_agent_1", "target": "writer_agent_1"}
    ]
  }
}
```

### Example 4: Streaming Execution
```javascript
// Frontend JavaScript for streaming execution
const executeWorkflowStream = async (workflowId, inputText) => {
  const response = await fetch(`/{API_START}/{API_VERSION_ONLY}/workflows/${workflowId}/execute/stream`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream'
    },
    body: JSON.stringify({
      input_text: inputText,
      session_context: {}
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        
        switch (data.type) {
          case 'start':
            console.log('Execution started');
            break;
          case 'node_start':
            console.log(`Node ${data.node_name} starting...`);
            break;
          case 'partial_result':
            console.log(`Partial result: ${data.content}`);
            break;
          case 'node_complete':
            console.log(`Node ${data.node_name} completed`);
            break;
          case 'complete':
            console.log('Execution completed:', data.result);
            break;
          case 'error':
            console.error('Execution error:', data.error);
            break;
        }
      }
    }
  }
};
```

---

This comprehensive API documentation covers all endpoints, request/response formats, error handling, and practical examples for integrating with the KAI-Flow platform. The API is designed to be RESTful, well-documented, and developer-friendly with consistent patterns across all endpoints.