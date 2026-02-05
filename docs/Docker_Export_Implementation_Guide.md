# KAI-Flow Docker Export Implementation Guide

## Overview

This document describes the complete implementation of the KAI-Flow Workflow Docker Export feature, which allows users to export their workflows as standalone Docker containers with all necessary dependencies and configurations.

## System Architecture

### Backend Components

#### 1. Export API (`backend/app/routes/export.py`)
- **POST `/{API_START}/export/workflow/{workflow_id}`**: Initialize export and analyze dependencies
- **POST `/{API_START}/export/workflow/{workflow_id}/complete`**: Complete export with user configuration

**Key Features:**
- Workflow dependency analysis
- Node-specific requirement filtering
- Environment variable validation
- Security configuration
- Monitoring setup (LangSmith)
- Docker package generation

#### 2. External Workflow API (`backend/app/api/external_workflows.py`)
- **POST `/{API_START}/{API_VERSION_ONLY}/workflows/external/register`**: Register external Docker workflows
- **GET `/{API_START}/{API_VERSION_ONLY}/workflows/external`**: List registered external workflows
- **GET `/{API_START}/{API_VERSION_ONLY}/workflows/external/{id}/status`**: Check workflow status
- **POST `/{API_START}/{API_VERSION_ONLY}/workflows/external/{id}/execute`**: Execute external workflow
- **DELETE `/{API_START}/{API_VERSION_ONLY}/workflows/external/{id}`**: Unregister external workflow

### Frontend Components

#### 1. Workflow Export Modal (`client/app/components/modals/WorkflowExportModal.tsx`)
Complete modal interface for:
- Environment variable collection
- Security configuration (API keys, host validation)
- Monitoring setup (LangSmith)
- Docker configuration
- Export progress tracking

#### 2. External Workflow Modal (`client/app/components/modals/ExternalWorkflowModal.tsx`)
Management interface for:
- Registering external workflows
- Monitoring connection status
- Executing remote workflows
- Unregistering workflows

#### 3. Services
- **Export Service** (`client/app/services/exportService.ts`)
- **External Workflow Service** (`client/app/services/externalWorkflowService.ts`)

## Export Process Flow

### Step 1: Initialize Export
```typescript
// User clicks "Docker Export" from workflow navbar
const response = await exportService.initializeExport(workflowId);
// Returns: required environment variables, dependencies, node types
```

### Step 2: Environment Configuration
User provides:
- **Required Environment Variables**: API keys for nodes (OpenAI, Tavily, etc.)
- **Security Settings**: 
  - Allowed hosts
  - API key authentication
  - Custom API keys
- **Monitoring**: LangSmith configuration
- **Docker**: Port configuration

### Step 3: Package Generation
```typescript
const result = await exportService.completeExport(workflowId, config);
// Generates: Docker container, .env file, docker-compose.yml, README
```

### Step 4: Download & Deploy
User downloads ZIP package containing:
- `main.py` - Minimal FastAPI runtime
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Service orchestration
- `.env` - Pre-configured environment
- `requirements.txt` - Filtered dependencies
- `workflow-definition.json` - Workflow data
- `README.md` - Setup instructions

## Generated Package Structure

```
workflow-export-{name}/
├── docker-compose.yml     # Ready-to-run compose file
├── .env                   # Pre-configured environment
├── README.md              # Quick start guide
├── main.py                # Minimal FastAPI runtime
├── Dockerfile             # Container definition
├── requirements.txt       # Filtered dependencies
├── workflow-definition.json # Workflow configuration
└── logs/                  # Log directory
```

## Security Features

### 1. Host-based Access Control
```bash
ALLOWED_HOSTS=localhost,127.0.0.1,myapp.com
```
Only specified hosts can access the workflow API.

### 2. API Key Authentication
```bash
API_KEYS=key1,key2,custom_key1,custom_key2
REQUIRE_API_KEY=true
```
Supports multiple API keys for different clients.

### 3. Environment Validation
- OpenAI API key format validation
- Database URL format checking
- Required variable enforcement

## Monitoring Integration

### LangSmith Support
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls_...
LANGCHAIN_PROJECT=my-workflow
```
Optional performance monitoring and tracing.

## External Workflow Integration

### Registration Process
1. User enters Docker workflow host/port
2. System tests connection to `/health` and `/{API_START}/workflow/external/info`
3. Workflow registered as read-only external workflow
4. Can be executed remotely from KAI-Flow

### Management Features
- Connection status monitoring
- Remote execution
- Workflow information display
- Easy unregistration

## Usage Examples

### Basic Export
```bash
# 1. User exports workflow from KAI-Flow UI
# 2. Provides OpenAI API key
# 3. Downloads package
# 4. Deploys:

unzip workflow-export-my-workflow.zip
cd workflow-export-my-workflow/
docker-compose up -d

# 5. Test:
curl http://localhost:8000/health
curl -X POST http://localhost:8000/{API_START}/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world"}'
```

### Secure Export with API Keys
```bash
# Export with API key protection
# .env contains:
# REQUIRE_API_KEY=true
# API_KEYS=wf_123,wf_456,my_custom_key

curl -X POST http://localhost:8000/{API_START}/workflow/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: wf_123" \
  -d '{"input": "Hello world"}'
```

### External Workflow Registration
```typescript
// From KAI-Flow UI
const config = {
  name: "My Remote Workflow",
  host: "192.168.1.100",
  port: 8080,
  api_key: "wf_123"  // If required
};

await externalWorkflowService.registerExternalWorkflow(config);
```

## API Endpoints Reference

### Export Endpoints
- `POST /{API_START}/export/workflow/{id}` - Initialize export
- `POST /{API_START}/export/workflow/{id}/complete` - Complete export

### External Workflow Endpoints
- `POST /{API_START}/{API_VERSION_ONLY}/workflows/external/register` - Register external workflow
- `GET /{API_START}/{API_VERSION_ONLY}/workflows/external` - List external workflows
- `GET /{API_START}/{API_VERSION_ONLY}/workflows/external/{id}/status` - Check status
- `POST /{API_START}/{API_VERSION_ONLY}/workflows/external/{id}/execute` - Execute workflow
- `DELETE /{API_START}/{API_VERSION_ONLY}/workflows/external/{id}` - Unregister

### Runtime Workflow API (Generated)
- `GET /health` - Health check
- `GET /{API_START}/workflow/info` - Workflow information
- `POST /{API_START}/workflow/execute` - Execute workflow
- `GET /{API_START}/workflow/status/{execution_id}` - Execution status
- `GET /{API_START}/workflow/result/{execution_id}` - Execution result
- `GET /{API_START}/workflow/external/info` - External workflow info
- `POST /{API_START}/workflow/external/ping` - Health ping

## Node Support Matrix

| Node Type | Required Env | Optional Env |
|-----------|--------------|--------------|
| OpenAIChat | OPENAI_API_KEY | OPENAI_MODEL, OPENAI_TEMPERATURE |
| TavilyWebSearch | TAVILY_API_KEY | TAVILY_MAX_RESULTS |
| HttpClient | - | HTTP_TIMEOUT, HTTP_MAX_RETRIES |
| CohereReranker | COHERE_API_KEY | COHERE_MODEL |
| VectorStoreOrchestrator | DATABASE_URL | VECTOR_STORE_COLLECTION |
| BufferMemory | - | MEMORY_BUFFER_SIZE |
| ConversationMemory | - | CONVERSATION_MEMORY_K |
| WebhookTrigger | - | WEBHOOK_SECRET |

## Troubleshooting

### Common Issues

1. **Export fails with "Invalid workflow ID"**
   - Ensure workflow exists and user has access

2. **Package won't start**
   - Check Docker/Docker Compose installation
   - Verify port availability
   - Check environment variables

3. **API key authentication fails**
   - Verify API_KEYS environment variable
   - Check X-API-Key header format

4. **External workflow registration fails**
   - Verify Docker workflow is running
   - Check host/port accessibility
   - Test API key if required

### Debug Commands
```bash
# Check export package health
docker-compose ps
docker-compose logs workflow-api

# Test API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/{API_START}/workflow/info

# Check environment
docker-compose exec workflow-api printenv
```

## Performance Considerations

- **Package Size**: ~5-20MB depending on dependencies
- **Startup Time**: ~30-60 seconds for full initialization
- **Memory Usage**: ~100-500MB depending on workflow complexity
- **Concurrent Requests**: Supports multiple simultaneous executions

## Security Best Practices

1. **Use unique API keys** for each deployment
2. **Restrict allowed hosts** to known domains only
3. **Use HTTPS** in production deployments
4. **Regularly rotate API keys** for external services
5. **Monitor access logs** for suspicious activity

## Future Enhancements

- Support for more node types
- Advanced scheduling capabilities
- Workflow version management
- Performance metrics dashboard
- Automated testing framework
- Kubernetes deployment support

---

*This implementation provides a complete Docker export solution for KAI-Flow workflows, enabling standalone deployment and management of AI workflows in any Docker-compatible environment.*
