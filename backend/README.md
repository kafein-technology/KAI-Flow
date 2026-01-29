# KAI-Fusion Backend - Enterprise AI Workflow Orchestration Platform

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.1+-purple.svg)](https://langchain.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

## Overview

KAI-Fusion Backend is a sophisticated enterprise-grade AI workflow orchestration platform built with FastAPI, LangChain, and LangGraph. It provides comprehensive workflow management, node-based processing, and advanced AI integration capabilities for complex business automation scenarios.

### Key Features

- **Enterprise Workflow Engine**: Advanced workflow orchestration with LangGraph integration
- **Node-Based Architecture**: Modular, extensible node system for AI processing
- **Multi-Modal AI Support**: Integration with OpenAI, Anthropic, and other providers
- **Real-time Processing**: WebSocket support for streaming workflows
- **Advanced Security**: JWT authentication, role-based access control, encryption
- **Scalable Database**: PostgreSQL with SQLAlchemy ORM and async support
- **Monitoring & Observability**: Comprehensive logging, tracing, and performance monitoring
- **Production Ready**: Docker deployment, health checks, graceful shutdown

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     KAI-Fusion Backend Architecture            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Client Layer                                                   │
│  ├── Web Frontend (React/Next.js)                              │
│  ├── API Clients                                               │
│  └── Webhook Integrations                                      │
│                                                                 │
│  API Gateway Layer                                              │
│  ├── FastAPI Application (app/main.py)                         │
│  ├── Middleware Stack (CORS, Auth, Logging)                    │
│  ├── Rate Limiting & Security                                  │
│  └── Request/Response Processing                               │
│                                                                 │
│  Service Layer                                                  │
│  ├── Workflow Service (app/services/workflow_service.py)       │
│  ├── Execution Service (app/services/execution_service.py)     │
│  ├── Node Registry Service (app/services/node_registry.py)     │
│  ├── Chat Service (app/services/chat_service.py)               │
│  └── User & Auth Services                                      │
│                                                                 │
│  Core Engine Layer                                              │
│  ├── Workflow Engine (app/core/engine.py)                      │
│  ├── Graph Builder (app/core/graph_builder.py)                 │
│  ├── Node Registry (app/core/node_registry.py)                 │
│  ├── State Management (app/core/state.py)                      │
│  └── Execution Queue (app/core/execution_queue.py)             │
│                                                                 │
│  Node System Layer                                              │
│  ├── Base Node Classes (app/nodes/base.py)                     │
│  ├── LLM Nodes (app/nodes/llms/)                               │
│  ├── Tool Nodes (app/nodes/tools/)                             │
│  ├── Memory Nodes (app/nodes/memory/)                          │
│  ├── Trigger Nodes (app/nodes/triggers/)                       │
│  └── Vector Store Nodes (app/nodes/vector_stores/)             │
│                                                                 │
│  Data Layer                                                     │
│  ├── PostgreSQL Database                                       │
│  ├── SQLAlchemy Models (app/models/)                           │
│  ├── Database Migrations                                       │
│  └── Vector Storage Integration                                │
│                                                                 │
│  Integration Layer                                              │
│  ├── LangChain Integration                                      │
│  ├── LangGraph Workflows                                       │
│  ├── External AI Providers                                     │
│  ├── Vector Databases                                          │
│  └── Third-party APIs                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
backend/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── main.py                   # FastAPI application entry point
│   ├── app.py                    # Application factory and configuration
│   │
│   ├── api/                      # API route handlers
│   │   ├── __init__.py
│   │   ├── auth.py               # Authentication endpoints
│   │   ├── workflows.py          # Workflow management API
│   │   ├── executions.py         # Workflow execution API
│   │   ├── chat.py               # Chat/conversation API
│   │   ├── nodes.py              # Node management API
│   │   ├── node_registry.py      # Node registry API
│   │   ├── vectors.py            # Vector storage API
│   │   ├── documents.py          # Document management API
│   │   ├── webhooks.py           # Webhook integration API
│   │   ├── scheduled_jobs.py     # Timer/scheduling API
│   │   ├── credentials.py        # Credential management API
│   │   ├── variables.py          # Environment variables API
│   │   └── api_key.py            # API key management
│   │
│   ├── auth/                     # Authentication & authorization
│   │   ├── __init__.py
│   │   └── dependencies.py       # Auth dependencies and decorators
│   │
│   ├── core/                     # Core system components
│   │   ├── __init__.py
│   │   ├── config.py             # Application configuration
│   │   ├── database.py           # Database connection and session management
│   │   ├── engine.py             # Workflow execution engine
│   │   ├── graph_builder.py      # LangGraph workflow builder
│   │   ├── node_registry.py      # Node discovery and registration
│   │   ├── node_discovery.py     # Automatic node discovery
│   │   ├── state.py              # Workflow state management
│   │   ├── execution_queue.py    # Execution queue and concurrency control
│   │   ├── checkpointer.py       # Workflow checkpointing
│   │   ├── memory_manager.py     # Memory management for workflows
│   │   ├── credential_provider.py# Secure credential management
│   │   ├── encryption.py         # Data encryption utilities
│   │   ├── security.py           # Security utilities and validation
│   │   ├── tracing.py            # LangSmith tracing integration
│   │   ├── performance_monitor.py# Performance monitoring
│   │   ├── logging_config.py     # Logging configuration
│   │   ├── error_handlers.py     # Global error handling
│   │   ├── exceptions.py         # Custom exception classes
│   │   └── constants.py          # Application constants
│   │
│   ├── middleware/               # FastAPI middleware
│   │   ├── __init__.py
│   │   └── logging_middleware.py # Request/response logging
│   │
│   ├── models/                   # SQLAlchemy database models
│   │   ├── __init__.py
│   │   ├── base.py               # Base model class
│   │   ├── user.py               # User model
│   │   ├── organization.py       # Organization model
│   │   ├── workflow.py           # Workflow and template models
│   │   ├── execution.py          # Workflow execution models
│   │   ├── chat.py               # Chat and message models
│   │   ├── node.py               # Node configuration models
│   │   ├── node_registry.py      # Node registry models
│   │   ├── scheduled_job.py      # Timer/scheduled job models
│   │   ├── webhook.py            # Webhook models
│   │   ├── document.py           # Document storage models
│   │   ├── vector_collection.py  # Vector collection models
│   │   ├── vector_document.py    # Vector document models
│   │   ├── memory.py             # Memory storage models
│   │   ├── variable.py           # Environment variable models
│   │   ├── user_credential.py    # User credential models
│   │   ├── api_key.py            # API key models
│   │   ├── auth.py               # Authentication models
│   │   └── node_configuration.py # Node configuration models
│   │
│   ├── nodes/                    # Node system implementation
│   │   ├── __init__.py
│   │   ├── base.py               # Base node classes and interfaces
│   │   │
│   │   ├── default/              # Default workflow nodes
│   │   │   ├── __init__.py
│   │   │   ├── start_node.py     # Workflow start node
│   │   │   └── end_node.py       # Workflow end node
│   │   │
│   │   ├── llms/                 # Large Language Model nodes
│   │   │   ├── __init__.py
│   │   │   └── openai_node.py    # OpenAI GPT integration
│   │   │
│   │   ├── tools/                # Tool and utility nodes
│   │   │   ├── __init__.py
│   │   │   ├── http_client.py    # HTTP request node
│   │   │   ├── tavily_search.py  # Web search integration
│   │   │   ├── retriever.py      # Vector retrieval node
│   │   │   └── cohere_reranker.py# Document reranking
│   │   │
│   │   ├── memory/               # Memory and state nodes
│   │   │   ├── __init__.py
│   │   │   ├── buffer_memory.py  # Buffer memory implementation
│   │   │   └── conversation_memory.py # Conversation memory
│   │   │
│   │   ├── triggers/             # Trigger and event nodes
│   │   │   ├── __init__.py
│   │   │   ├── webhook_trigger.py# Webhook trigger node
│   │   │   └── timer_start_node.py# Timer trigger node
│   │   │
│   │   ├── agents/               # AI agent nodes
│   │   │   ├── __init__.py
│   │   │   └── react_agent.py    # ReAct agent implementation
│   │   │
│   │   ├── document_loaders/     # Document processing nodes
│   │   │   ├── __init__.py
│   │   │   ├── document_loader.py# Generic document loader
│   │   │   └── web_scraper.py    # Web scraping node
│   │   │
│   │   ├── splitters/            # Text splitting nodes
│   │   │   ├── __init__.py
│   │   │   └── chunk_splitter.py # Text chunking node
│   │   │
│   │   ├── embeddings/           # Embedding generation nodes
│   │   │   ├── __init__.py
│   │   │   └── openai_embeddings_provider.py # OpenAI embeddings
│   │   │
│   │   └── vector_stores/        # Vector database nodes
│   │       ├── __init__.py
│   │       └── vector_store_orchestrator.py # Vector store management
│   │
│   ├── routes/                   # Additional route handlers
│   │   ├── __init__.py
│   │   └── export.py             # Data export routes
│   │
│   ├── schemas/                  # Pydantic schemas for API validation
│   │   ├── __init__.py
│   │   ├── auth.py               # Authentication schemas
│   │   ├── user.py               # User schemas
│   │   ├── organization.py       # Organization schemas
│   │   ├── workflow.py           # Workflow schemas
│   │   ├── execution.py          # Execution schemas
│   │   ├── chat.py               # Chat schemas
│   │   ├── document.py           # Document schemas
│   │   ├── webhook.py            # Webhook schemas
│   │   ├── variable.py           # Variable schemas
│   │   ├── user_credential.py    # Credential schemas
│   │   ├── api_key.py            # API key schemas
│   │   └── node_configuration.py # Node configuration schemas
│   │
│   └── services/                 # Business logic services
│       ├── __init__.py
│       ├── base.py               # Base service class
│       ├── dependencies.py       # Service dependencies
│       ├── workflow_service.py   # Workflow management service
│       ├── execution_service.py  # Execution management service
│       ├── chat_service.py       # Chat service
│       ├── user_service.py       # User management service
│       ├── document_service.py   # Document management service
│       ├── webhook_service.py    # Webhook service
│       ├── scheduled_job_service.py # Timer/scheduling service
│       ├── credential_service.py # Credential management service
│       ├── variable_service.py   # Variable management service
│       ├── api_key_service.py    # API key service
│       ├── node_registry_service.py # Node registry service
│       ├── node_configuration_service.py # Node config service
│       └── memory.py             # Memory service
│
├── migrations/                   # Database migrations
│   ├── database_setup.py         # Initial database setup
│   └── add_chat_message_columns.py # Chat schema updates
│
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker configuration
├── docker-compose.yml            # Docker Compose setup
├── .env.example                  # Environment variables template
└── README.md                     # This file
```

## Core Components

### 1. Workflow Engine (`app/core/engine.py`)

The workflow engine is the heart of KAI-Fusion, providing sophisticated workflow orchestration capabilities:

```python
# Core Engine Interface
class BaseWorkflowEngine(abc.ABC):
    @abc.abstractmethod
    def validate(self, flow_data: JSONType) -> JSONType:
        """Validate workflow definition"""
        pass

    @abc.abstractmethod
    def build(self, flow_data: JSONType, *, user_context: Optional[JSONType] = None) -> None:
        """Build workflow for execution"""
        pass

    @abc.abstractmethod
    async def execute(
        self,
        inputs: Optional[JSONType] = None,
        *,
        stream: bool = False,
        user_context: Optional[JSONType] = None,
    ) -> ExecutionResult:
        """Execute workflow with optional streaming"""
        pass
```

**Key Features:**
- **Validation**: Comprehensive workflow definition validation
- **Compilation**: Intelligent workflow graph compilation
- **Execution**: Dual-mode execution (synchronous and streaming)
- **Error Handling**: Advanced error recovery and retry mechanisms
- **Performance**: Sub-100ms execution overhead

### 2. Node System (`app/nodes/`)

The node system provides a modular, extensible architecture for AI processing components:

#### Base Node Architecture

```python
# Base Node Classes
class BaseNode(ABC):
    """Abstract base class for all nodes"""
    
class ProviderNode(BaseNode):
    """Nodes that provide resources (LLMs, tools, etc.)"""
    
class ProcessorNode(BaseNode):
    """Nodes that process multiple inputs"""
    
class TerminatorNode(BaseNode):
    """Nodes that terminate workflow branches"""
```

#### Node Metadata System

```python
# Node Metadata Definition
_metadata = {
    "name": "NodeClassName",
    "display_name": "Human Readable Name",
    "description": "Detailed node description",
    "category": "Node Category",
    "node_type": NodeType.PROVIDER,
    "inputs": [
        NodeInput(
            name="input_name",
            type="string",
            description="Input description",
            required=True
        )
    ],
    "outputs": [
        NodeOutput(
            name="output_name",
            type="object",
            description="Output description"
        )
    ]
}
```

#### Available Node Types

1. **LLM Nodes** (`app/nodes/llms/`)
   - OpenAI GPT integration
   - Support for GPT-3.5, GPT-4, GPT-4-Turbo
   - Custom model parameters and streaming

2. **Tool Nodes** (`app/nodes/tools/`)
   - HTTP Client for REST API calls
   - Tavily Search for web search
   - Document Retriever for vector search
   - Cohere Reranker for result optimization

3. **Memory Nodes** (`app/nodes/memory/`)
   - Buffer Memory for conversation history
   - Conversation Memory with advanced features
   - Persistent memory storage

4. **Trigger Nodes** (`app/nodes/triggers/`)
   - **Webhook Trigger**: REST API endpoints for external integrations
   - **Timer Trigger**: Scheduled workflow execution with cron support

5. **Agent Nodes** (`app/nodes/agents/`)
   - ReAct Agent for reasoning and action
   - Custom agent implementations

6. **Document Processing** (`app/nodes/document_loaders/`, `app/nodes/splitters/`)
   - Document loaders for various formats
   - Text splitters for chunking
   - Web scrapers for content extraction

7. **Vector Storage** (`app/nodes/vector_stores/`, `app/nodes/embeddings/`)
   - Vector store orchestration
   - OpenAI embeddings generation
   - Multiple vector database support

### 3. Database Architecture (`app/models/`)

KAI-Fusion uses PostgreSQL with SQLAlchemy for robust data persistence:

#### Core Models

```python
# Workflow Model
class Workflow(Base):
    __tablename__ = "workflows"
    
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str]
    flow_data: Dict[str, Any]  # JSON workflow definition
    is_public: bool
    version: int
    created_at: datetime
    updated_at: datetime

# Execution Model
class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    
    id: uuid.UUID
    workflow_id: uuid.UUID
    user_id: uuid.UUID
    status: ExecutionStatus
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]]
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
```

#### Key Features

- **UUID Primary Keys**: For distributed system compatibility
- **JSON Fields**: For flexible schema-less data storage
- **Timestamps**: Comprehensive audit trail
- **Foreign Keys**: Proper relational integrity
- **Indexes**: Optimized for query performance

### 4. API Layer (`app/api/`)

FastAPI-based REST API with comprehensive endpoint coverage:

#### Authentication & Authorization

```python
# JWT-based authentication
@router.post("/auth/login")
async def login(credentials: UserLogin) -> TokenResponse
    
@router.post("/auth/register")  
async def register(user_data: UserCreate) -> UserResponse

@router.post("/auth/refresh")
async def refresh_token(refresh_token: str) -> TokenResponse
```

#### Workflow Management

```python
# Workflow CRUD operations
@router.post("/workflows/")
async def create_workflow(workflow: WorkflowCreate) -> WorkflowResponse

@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: uuid.UUID) -> WorkflowResponse

@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: uuid.UUID, workflow: WorkflowUpdate) -> WorkflowResponse

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: uuid.UUID) -> dict
```

#### Workflow Execution

```python
# Execution management
@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: uuid.UUID,
    inputs: Dict[str, Any]
) -> ExecutionResponse

@router.get("/executions/{execution_id}/stream")
async def stream_execution(execution_id: uuid.UUID) -> StreamingResponse
```

### 5. LangChain & LangGraph Integration

KAI-Fusion leverages LangChain and LangGraph for advanced AI workflow capabilities:

#### LangChain Integration

```python
# LangChain components integration
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

# Node integration with LangChain
class OpenAINode(ProviderNode):
    def as_runnable(self) -> Runnable:
        """Convert node to LangChain Runnable"""
        return RunnableLambda(
            lambda inputs: self.execute(**inputs),
            name=f"OpenAINode_{self.node_id}"
        )
```

#### LangGraph Workflow Building

```python
# Graph construction with LangGraph
from langgraph.graph import StateGraph, START, END

class GraphBuilder:
    def build_langgraph(self, workflow_definition: dict) -> StateGraph:
        """Build LangGraph from workflow definition"""
        
        graph = StateGraph(FlowState)
        
        # Add nodes
        for node_data in workflow_definition["nodes"]:
            node_instance = self._create_node_instance(node_data)
            graph.add_node(node_data["id"], node_instance.execute)
        
        # Add edges
        for edge in workflow_definition["edges"]:
            graph.add_edge(edge["source"], edge["target"])
        
        return graph.compile()
```

### 6. Vector Storage & Document Processing

Advanced document processing and vector storage capabilities:

#### Document Processing Pipeline

```python
# Document processing workflow
Document → Loader → Splitter → Embeddings → Vector Store

# Example implementation
async def process_document(document_path: str):
    # Load document
    loader = DocumentLoader()
    docs = await loader.load(document_path)
    
    # Split into chunks
    splitter = ChunkSplitter(chunk_size=1000, overlap=200)
    chunks = await splitter.split(docs)
    
    # Generate embeddings
    embeddings = OpenAIEmbeddings()
    vectors = await embeddings.embed_documents(chunks)
    
    # Store in vector database
    vector_store = VectorStoreOrchestrator()
    await vector_store.add_documents(chunks, vectors)
```

#### Vector Search & Retrieval

```python
# Vector similarity search
async def search_documents(query: str, top_k: int = 5):
    embeddings = OpenAIEmbeddings()
    query_vector = await embeddings.embed_query(query)
    
    vector_store = VectorStoreOrchestrator()
    results = await vector_store.similarity_search(
        query_vector, 
        top_k=top_k
    )
    
    return results
```

## Advanced Features

### 1. Timer Trigger System

Enhanced timer trigger with automatic workflow execution:

```python
# Timer configuration
timer_config = {
    "schedule_type": "cron",           # interval, cron, once, manual
    "cron_expression": "0 9 * * 1-5", # Weekdays at 9 AM
    "timezone": "America/New_York",
    "auto_trigger_workflow": True,
    "max_executions": 100,
    "retry_on_failure": True,
    "retry_count": 3
}

# Automatic workflow triggering
class TimerStartNode(TerminatorNode):
    async def _timer_loop(self):
        """Main timer loop for automatic workflow triggering"""
        while self.user_data.get("enabled", True):
            next_run = self._calculate_next_run_time()
            await asyncio.sleep((next_run - datetime.now()).total_seconds())
            await self._trigger_workflow_execution()
```

### 2. Webhook Integration System

Production-ready webhook system for external integrations:

```python
# Webhook endpoint creation
@webhook_router.post("/{webhook_id}")
async def webhook_handler(
    webhook_id: str,
    payload: WebhookPayload,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Authentication check
    if not validate_webhook_token(credentials.credentials):
        raise HTTPException(status_code=401)
    
    # Process webhook event
    await process_webhook_event(webhook_id, payload)
    
    return WebhookResponse(success=True, webhook_id=webhook_id)
```

### 3. Real-time Streaming

WebSocket support for real-time workflow execution:

```python
# Streaming execution
@router.websocket("/workflows/{workflow_id}/stream")
async def stream_workflow_execution(
    websocket: WebSocket,
    workflow_id: uuid.UUID
):
    await websocket.accept()
    
    engine = get_engine()
    
    async for event in engine.execute(stream=True):
        await websocket.send_json({
            "type": event["type"],
            "data": event["data"],
            "timestamp": datetime.now().isoformat()
        })
```

### 4. Security & Encryption

Comprehensive security framework:

```python
# Data encryption
class EncryptionService:
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data using Fernet"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

# Credential management
class CredentialProvider:
    async def get_encrypted_credential(self, user_id: uuid.UUID, key: str) -> Optional[str]:
        """Retrieve and decrypt user credential"""
        credential = await self.credential_service.get_user_credential(user_id, key)
        if credential:
            return self.encryption_service.decrypt_sensitive_data(credential.encrypted_value)
        return None
```

## Database Schema

### Core Tables

```sql
-- Users and Organizations
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflows and Executions
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    flow_data JSONB NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    inputs JSONB DEFAULT '{}',
    outputs JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Chat and Memory
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES workflows(id) ON DELETE SET NULL,
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scheduled Jobs and Webhooks
CREATE TABLE scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    node_id VARCHAR(255) NOT NULL,
    job_name VARCHAR(255) NOT NULL,
    timer_type VARCHAR(50) NOT NULL,
    cron_expression VARCHAR(255),
    interval_seconds INTEGER,
    delay_seconds INTEGER,
    timezone VARCHAR(100) DEFAULT 'UTC',
    is_enabled BOOLEAN DEFAULT TRUE,
    max_executions INTEGER DEFAULT 0,
    current_executions INTEGER DEFAULT 0,
    next_run_at TIMESTAMP WITH TIME ZONE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector Storage
CREATE TABLE vector_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    embedding_model VARCHAR(255) NOT NULL,
    dimension INTEGER NOT NULL,
    metric VARCHAR(50) DEFAULT 'cosine',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE vector_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID REFERENCES vector_collections(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536), -- OpenAI embeddings dimension
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Indexes for Performance

```sql
-- Performance indexes
CREATE INDEX idx_workflows_user_id ON workflows(user_id);
CREATE INDEX idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_scheduled_jobs_next_run ON scheduled_jobs(next_run_at) WHERE is_enabled = TRUE;
CREATE INDEX idx_vector_documents_collection_id ON vector_documents(collection_id);

-- Full-text search indexes
CREATE INDEX idx_workflows_name_search ON workflows USING gin(to_tsvector('english', name));
CREATE INDEX idx_workflows_description_search ON workflows USING gin(to_tsvector('english', description));
```

## Configuration

### Environment Variables

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/kai_fusion
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Security Configuration
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
ENCRYPTION_KEY=your-fernet-encryption-key

# AI Provider Configuration
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
COHERE_API_KEY=your-cohere-api-key
TAVILY_API_KEY=your-tavily-api-key

# LangSmith Configuration (Optional)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=kai-fusion-backend

# Application Configuration
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:3000", "https://your-frontend-domain.com"]

# Webhook Configuration  
WEBHOOK_BASE_URL=http://localhost:8000
WEBHOOK_SECRET_KEY=your-webhook-secret

# Vector Database Configuration
VECTOR_DATABASE_URL=your-vector-db-connection-string
VECTOR_DATABASE_TYPE=pgvector

# Performance Configuration
WORKERS=4
MAX_CONNECTIONS=100
KEEP_ALIVE=65
```

### Application Configuration

```python
# app/core/config.py
class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Database settings
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(30, env="DATABASE_MAX_OVERFLOW")
    
    # Security settings
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_access_token_expire_minutes: int = Field(30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # AI provider settings
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    
    # Application settings
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

## API Documentation

### Authentication Endpoints

```http
POST /api/auth/login
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "secure_password"
}

Response:
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 1800
}
```

### Workflow Management

```http
POST /api/workflows/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "name": "My AI Workflow",
    "description": "Advanced AI processing workflow",
    "flow_data": {
        "nodes": [
            {
                "id": "start_1",
                "type": "Start",
                "position": {"x": 100, "y": 200},
                "data": {"name": "Start Node"}
            },
            {
                "id": "openai_1",
                "type": "OpenAINode",
                "position": {"x": 400, "y": 200},
                "data": {
                    "name": "GPT-4 Processing",
                    "inputs": {
                        "model": "gpt-4-turbo-preview",
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                }
            },
            {
                "id": "end_1",
                "type": "End",
                "position": {"x": 700, "y": 200},
                "data": {"name": "End Node"}
            }
        ],
        "edges": [
            {
                "id": "start_to_openai",
                "source": "start_1",
                "target": "openai_1",
                "sourceHandle": "output",
                "targetHandle": "input"
            },
            {
                "id": "openai_to_end",
                "source": "openai_1",
                "target": "end_1",
                "sourceHandle": "output",
                "targetHandle": "input"
            }
        ]
    }
}
```

### Workflow Execution

```http
POST /api/workflows/{workflow_id}/execute
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "inputs": {
        "message": "Analyze this business proposal and provide recommendations"
    }
}

Response:
{
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
    "started_at": "2024-08-05T10:30:00Z",
    "inputs": {
        "message": "Analyze this business proposal..."
    }
}
```

### Streaming Execution

```javascript
// WebSocket connection for real-time execution
const ws = new WebSocket('ws://localhost:8000/api/workflows/{workflow_id}/stream');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'node_start':
            console.log(`Node ${data.node_id} started`);
            break;
        case 'node_end':
            console.log(`Node ${data.node_id} completed:`, data.output);
            break;
        case 'workflow_complete':
            console.log('Workflow completed:', data.result);
            break;
        case 'error':
            console.error('Workflow error:', data.error);
            break;
    }
};

// Send execution request
ws.send(JSON.stringify({
    action: 'execute',
    inputs: {
        message: 'Process this data'
    }
}));
```

## Frontend Integration

### React Integration Example

```typescript
// Frontend API client
class KAIFusionAPI {
    private baseURL = 'http://localhost:8000/api';
    private token: string | null = null;

    async login(email: string, password: string): Promise<AuthResponse> {
        const response = await fetch(`${this.baseURL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        this.token = data.access_token;
        return data;
    }

    async createWorkflow(workflow: WorkflowCreate): Promise<Workflow> {
        const response = await fetch(`${this.baseURL}/workflows/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`
            },
            body: JSON.stringify(workflow)
        });
        
        return response.json();
    }

    async executeWorkflow(workflowId: string, inputs: any): Promise<Execution> {
        const response = await fetch(`${this.baseURL}/workflows/${workflowId}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`
            },
            body: JSON.stringify({ inputs })
        });
        
        return response.json();
    }
}

// React component example
const WorkflowExecutor: React.FC = () => {
    const [execution, setExecution] = useState<Execution | null>(null);
    const [loading, setLoading] = useState(false);

    const executeWorkflow = async (workflowId: string, inputs: any) => {
        setLoading(true);
        try {
            const api = new KAIFusionAPI();
            const result = await api.executeWorkflow(workflowId, inputs);
            setExecution(result);
        } catch (error) {
            console.error('Execution failed:', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            {loading && <div>Executing workflow...</div>}
            {execution && (
                <div>
                    <h3>Execution Result</h3>
                    <pre>{JSON.stringify(execution, null, 2)}</pre>
                </div>
            )}
        </div>
    );
};
```

### JSON Workflow Format

```json
{
    "nodes": [
        {
            "id": "webhook_trigger_1",
            "type": "WebhookTrigger",
            "position": {"x": 100, "y": 200},
            "data": {
                "name": "External API Trigger",
                "inputs": {
                    "authentication_required": true,
                    "allowed_event_types": "api.request,data.process",
                    "max_payload_size": 2048,
                    "rate_limit_per_minute": 100
                }
            }
        },
        {
            "id": "start_1",
            "type": "Start",
            "position": {"x": 400, "y": 200},
            "data": {"name": "Workflow Start"}
        },
        {
            "id": "openai_1",
            "type": "OpenAINode",
            "position": {"x": 700, "y": 200},
            "data": {
                "name": "GPT-4 Analysis",
                "inputs": {
                    "model": "gpt-4-turbo-preview",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "system_message": "You are an expert data analyst.",
                    "enable_streaming": true
                }
            }
        },
        {
            "id": "timer_1",
            "type": "TimerStartNode",
            "position": {"x": 400, "y": 400},
            "data": {
                "name": "Daily Report Timer",
                "inputs": {
                    "schedule_type": "cron",
                    "cron_expression": "0 9 * * 1-5",
                    "timezone": "America/New_York",
                    "auto_trigger_workflow": true,
                    "max_executions": 0,
                    "retry_on_failure": true
                }
            }
        },
        {
            "id": "http_client_1",
            "type": "HttpRequest",
            "position": {"x": 1000, "y": 200},
            "data": {
                "name": "Send Results",
                "inputs": {
                    "method": "POST",
                    "url": "https://api.example.com/results",
                    "headers": {
                        "Content-Type": "application/json",
                        "Authorization": "Bearer {{api_token}}"
                    },
                    "enable_templating": true
                }
            }
        },
        {
            "id": "end_1",
            "type": "End",
            "position": {"x": 1300, "y": 200},
            "data": {"name": "Workflow End"}
        }
    ],
    "edges": [
        {
            "id": "webhook_to_start",
            "source": "webhook_trigger_1",
            "target": "start_1",
            "sourceHandle": "webhook_data",
            "targetHandle": "input"
        },
        {
            "id": "start_to_openai",
            "source": "start_1",
            "target": "openai_1",
            "sourceHandle": "output",
            "targetHandle": "input"
        },
        {
            "id": "timer_to_openai",
            "source": "timer_1",
            "target": "openai_1",
            "sourceHandle": "timer_data",
            "targetHandle": "input"
        },
        {
            "id": "openai_to_http",
            "source": "openai_1",
            "target": "http_client_1",
            "sourceHandle": "output",
            "targetHandle": "input"
        },
        {
            "id": "http_to_end",
            "source": "http_client_1",
            "target": "end_1",
            "sourceHandle": "output",
            "targetHandle": "input"
        }
    ]
}
```

## Installation & Deployment

### Local Development Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd KAI-Fusion/backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# 5. Set up database
python migrations/database_setup.py

# 6. Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://kai_user:kai_password@db:5432/kai_fusion
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./app:/app/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=kai_fusion
      - POSTGRES_USER=kai_user
      - POSTGRES_PASSWORD=kai_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Deployment

```bash
# Production deployment with Gunicorn
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload \
    --access-logfile - \
    --error-logfile -
```

## Monitoring & Observability

### Health Checks

```python
# Health check endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    
    checks = {
        "database": await check_database_connection(),
        "redis": await check_redis_connection(),
        "external_apis": await check_external_apis(),
        "workflow_engine": check_workflow_engine_status(),
        "memory_usage": get_memory_usage(),
        "active_connections": get_active_connections()
    }
    
    overall_status = "healthy" if all(checks.values()) else "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "version": "2.1.0"
    }
```

### Logging Configuration

```python
# Structured logging
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Usage in application
logger = structlog.get_logger()

logger.info("Workflow executed", 
    workflow_id=workflow_id,
    execution_time=execution_time,
    node_count=len(nodes),
    user_id=user_id
)
```

### Performance Monitoring

```python
# Performance monitoring
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        
    def track_request(self, endpoint: str, duration: float, status_code: int):
        """Track API request performance"""
        key = f"{endpoint}_{status_code}"
        if key not in self.metrics:
            self.metrics[key] = []
        
        self.metrics[key].append({
            "duration": duration,
            "timestamp": datetime.now(),
            "status_code": status_code
        })
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {}
        
        for key, measurements in self.metrics.items():
            durations = [m["duration"] for m in measurements]
            stats[key] = {
                "count": len(durations),
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "min_duration": min(durations),
                "p95_duration": sorted(durations)[int(len(durations) * 0.95)]
            }
        
        return stats
```

## Testing

### Unit Tests

```python
# tests/test_workflow_service.py
import pytest
from app.services.workflow_service import WorkflowService
from app.models.workflow import Workflow

@pytest.mark.asyncio
async def test_create_workflow(db_session, test_user):
    """Test workflow creation"""
    service = WorkflowService()
    
    workflow_data = {
        "name": "Test Workflow",
        "description": "Test Description",
        "flow_data": {"nodes": [], "edges": []}
    }
    
    workflow = await service.create(
        db_session,
        user_id=test_user.id,
        workflow_data=workflow_data
    )
    
    assert workflow.name == "Test Workflow"
    assert workflow.user_id == test_user.id
    assert workflow.flow_data == {"nodes": [], "edges": []}

@pytest.mark.asyncio
async def test_workflow_execution(db_session, test_workflow):
    """Test workflow execution"""
    from app.core.engine import get_engine
    
    engine = get_engine()
    
    # Validate workflow
    validation = engine.validate(test_workflow.flow_data)
    assert validation["valid"] is True
    
    # Build workflow
    engine.build(test_workflow.flow_data)
    
    # Execute workflow
    result = await engine.execute(
        inputs={"message": "Test input"},
        user_context={"user_id": str(test_workflow.user_id)}
    )
    
    assert result is not None
    assert "output" in result
```

### Integration Tests

```python
# tests/test_api_integration.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_workflow_api_integration(async_client: AsyncClient, auth_headers):
    """Test complete workflow API integration"""
    
    # Create workflow
    workflow_data = {
        "name": "Integration Test Workflow",
        "description": "Test workflow for API integration",
        "flow_data": {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "Start",
                    "data": {"name": "Start"}
                },
                {
                    "id": "end_1", 
                    "type": "End",
                    "data": {"name": "End"}
                }
            ],
            "edges": [
                {
                    "source": "start_1",
                    "target": "end_1"
                }
            ]
        }
    }
    
    # Create workflow
    response = await async_client.post(
        "/api/workflows/",
        json=workflow_data,
        headers=auth_headers
    )
    assert response.status_code == 201
    workflow = response.json()
    
    # Execute workflow
    response = await async_client.post(
        f"/api/workflows/{workflow['id']}/execute",
        json={"inputs": {"message": "Test"}},
        headers=auth_headers
    )
    assert response.status_code == 201
    execution = response.json()
    
    # Check execution status
    response = await async_client.get(
        f"/api/executions/{execution['id']}",
        headers=auth_headers
    )
    assert response.status_code == 200
```

### Load Testing

```python
# scripts/load_test.py
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def execute_workflow(session, workflow_id, auth_token):
    """Execute workflow with authenticated session"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    data = {"inputs": {"message": "Load test execution"}}
    
    start_time = time.time()
    async with session.post(
        f"http://localhost:8000/api/workflows/{workflow_id}/execute",
        json=data,
        headers=headers
    ) as response:
        result = await response.json()
        end_time = time.time()
        
        return {
            "status_code": response.status,
            "duration": end_time - start_time,
            "success": response.status == 201
        }

async def load_test(concurrent_requests=10, total_requests=100):
    """Run load test against workflow API"""
    
    async with aiohttp.ClientSession() as session:
        # Authenticate and get token
        auth_response = await session.post(
            "http://localhost:8000/api/auth/login",
            json={"email": "test@example.com", "password": "testpass"}
        )
        auth_data = await auth_response.json()
        token = auth_data["access_token"]
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def controlled_execution():
            async with semaphore:
                return await execute_workflow(session, "workflow-id", token)
        
        # Execute requests
        tasks = [controlled_execution() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        successful = sum(1 for r in results if r["success"])
        avg_duration = sum(r["duration"] for r in results) / len(results)
        max_duration = max(r["duration"] for r in results)
        
        logger(f"Load Test Results:")
        logger(f"Total Requests: {total_requests}")
        logger(f"Successful: {successful} ({successful/total_requests*100:.1f}%)")
        logger(f"Average Duration: {avg_duration:.3f}s")
        logger(f"Max Duration: {max_duration:.3f}s")
        logger(f"Requests/second: {total_requests/sum(r['duration'] for r in results):.1f}")

if __name__ == "__main__":
    asyncio.run(load_test(concurrent_requests=20, total_requests=200))
```

## Contributing

### Development Guidelines

1. **Code Style**: Follow PEP 8 and use Black for formatting
2. **Type Hints**: Use type hints for all functions and methods
3. **Documentation**: Comprehensive docstrings for all public APIs
4. **Testing**: Maintain >90% test coverage
5. **Security**: Security review for all credential handling

### Pull Request Process

1. Create feature branch from `main`
2. Implement changes with tests
3. Update documentation
4. Run full test suite
5. Create pull request with detailed description

### Code Quality Tools

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Code formatting
black app/ tests/
isort app/ tests/

# Type checking
mypy app/

# Linting
flake8 app/ tests/
pylint app/

# Security scanning
bandit -r app/

# Test coverage
pytest --cov=app --cov-report=html
```

## License

This project is proprietary software owned by KAI-Fusion. All rights reserved.

## Support

For technical support and questions:
- Email: support@kai-fusion.com
- Documentation: https://docs.kai-fusion.com
- GitHub Issues: https://github.com/kai-fusion/backend/issues

---

**KAI-Fusion Backend v2.1.0** - Enterprise AI Workflow Orchestration Platform
Built with ❤️ by the KAI-Fusion Team