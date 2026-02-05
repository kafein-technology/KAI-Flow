# KAI-Flow: Comprehensive Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture Overview](#architecture-overview)
3. [Backend Architecture](#backend-architecture)
4. [Frontend Architecture](#frontend-architecture)
5. [Development Setup](#development-setup)
6. [Node System](#node-system)
7. [Authentication & Security](#authentication--security)
8. [Database & Models](#database--models)
9. [API Integration](#api-integration)
10. [Testing Strategy](#testing-strategy)
11. [Deployment & Configuration](#deployment--configuration)
12. [Performance & Monitoring](#performance--monitoring)

---

## Project Overview

**KAI-Flow** is a comprehensive AI workflow automation platform that enables users to create complex AI-powered workflows through an intuitive visual interface. The platform combines a drag-and-drop workflow builder with powerful backend execution capabilities, supporting 55+ integrated AI models, tools, and data processing nodes.

### Key Features
- **Visual Workflow Builder**: ReactFlow-based drag-and-drop interface
- **Multi-AI Integration**: Support for OpenAI, Anthropic, Google Gemini, and more
- **Real-time Execution**: Server-sent events for streaming workflow results
- **Memory Management**: Conversation history and context preservation
- **Extensible Node System**: 55+ pre-built nodes across 8 categories
- **Credential Management**: Secure API key storage and validation
- **Session Management**: User-specific workflow execution contexts

### Technology Stack
- **Backend**: Python FastAPI with async/await support
- **Frontend**: React 18 + TypeScript with Vite
- **AI Framework**: LangChain ecosystem (langchain, langchain-community, langgraph)
- **Database**: PostgreSQL with SQLAlchemy/SQLModel
- **Authentication**: JWT-based with refresh tokens
- **Task Queue**: Celery with Redis backend
- **UI Framework**: Tailwind CSS + DaisyUI components
- **Testing**: Vitest (Frontend), pytest (Backend)

---

## Architecture Overview

KAI-Flow follows a modern microservices-inspired architecture with clear separation between frontend and backend concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React/TS)                      │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │   Workflow      │ │   Node Library  │ │   Execution     ││
│  │   Builder       │ │   Sidebar       │ │   Monitor       ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │ HTTP/SSE
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │   API Layer     │ │  Engine Core    │ │  Node Registry  ││
│  │   (FastAPI)     │ │  (LangGraph)    │ │  (Auto-discover)││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │   Auth/Users    │ │   Memory Mgmt   │ │   Credentials   ││
│  │   Management    │ │   (Sessions)    │ │   Validation    ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              External Services & Storage                    │
│     PostgreSQL  │  Redis  │  OpenAI  │  Anthropic  │ ...   │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend Architecture

### Core Components

#### 1. FastAPI Application (`app/main.py`)
```python
# Application Entry Point
app = FastAPI(
    title="KAI-Flow API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Router Registration
app.include_router(workflows_router, prefix="/{API_START}/{API_VERSION_ONLY}")
app.include_router(nodes_router, prefix="/{API_START}/{API_VERSION_ONLY}")
app.include_router(auth_router, prefix="/{API_START}/{API_VERSION_ONLY}")
app.include_router(credentials_router, prefix="/{API_START}/{API_VERSION_ONLY}")
app.include_router(users_router, prefix="/{API_START}/{API_VERSION_ONLY}")
```

#### 2. Workflow Engine (`app/core/engine_v2.py`)
The unified workflow engine provides a consistent interface for workflow execution:

```python
class BaseWorkflowEngine:
    def validate(self, workflow_data: Dict) -> bool
    def build(self, workflow_data: Dict) -> Any
    def execute(self, graph: Any, inputs: Dict) -> Dict
    def execute_stream(self, graph: Any, inputs: Dict) -> Iterator[Dict]
```

#### 3. Node Registry (`app/core/node_registry.py`)
Automatic discovery and registration of node types:

```python
def discover_nodes() -> Dict[str, BaseNode]:
    """Auto-discover all node implementations"""
    
def get_node_metadata(node_class: Type[BaseNode]) -> Dict:
    """Extract metadata from node class"""
    
def register_node(node_type: str, node_class: Type[BaseNode]):
    """Register a node type globally"""
```

### Directory Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry
│   ├── core/
│   │   ├── config.py          # Configuration management
│   │   ├── engine_v2.py       # Unified workflow engine
│   │   ├── node_registry.py   # Node auto-discovery
│   │   └── base_node.py       # Base node interface
│   ├── api/
│   │   ├── workflows.py       # Workflow CRUD & execution
│   │   ├── nodes.py           # Node metadata endpoints
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── credentials.py     # Credential validation
│   │   └── users.py           # User management
│   ├── models/
│   │   ├── workflow.py        # SQLModel definitions
│   │   ├── user.py            # User models
│   │   └── base.py            # Base model classes
│   ├── services/
│   │   ├── workflow_service.py # Business logic
│   │   ├── auth_service.py     # Authentication logic
│   │   └── credential_service.py # Credential management
│   └── nodes/                  # Node implementations
│       ├── llms/              # Language models
│       ├── tools/             # External tool integrations
│       ├── chains/            # Workflow orchestration
│       ├── memory/            # Context management
│       ├── agents/            # Autonomous AI agents
│       ├── document_loaders/  # Data ingestion
│       ├── embeddings/        # Vector embeddings
│       └── vectorstores/      # Vector databases
├── requirements.txt
├── start.py                   # Development server
└── test_react_workflow.py     # Main test file
```

### API Layer Architecture

#### Workflow Management
- **POST** `/{API_START}/{API_VERSION_ONLY}/workflows/` - Create workflow
- **GET** `/{API_START}/{API_VERSION_ONLY}/workflows/` - List user workflows
- **PUT** `/{API_START}/{API_VERSION_ONLY}/workflows/{id}` - Update workflow
- **DELETE** `/{API_START}/{API_VERSION_ONLY}/workflows/{id}` - Delete workflow
- **POST** `/{API_START}/{API_VERSION_ONLY}/workflows/execute` - Execute workflow
- **POST** `/{API_START}/{API_VERSION_ONLY}/workflows/{id}/execute/stream` - Stream execution

#### Node System
- **GET** `/{API_START}/{API_VERSION_ONLY}/nodes` - List all available nodes
- **GET** `/{API_START}/{API_VERSION_ONLY}/nodes/categories` - List node categories
- **GET** `/{API_START}/{API_VERSION_ONLY}/nodes/{type}` - Get specific node metadata

#### Authentication
- **POST** `/{API_START}/{API_VERSION_ONLY}/auth/signup` - User registration
- **POST** `/{API_START}/{API_VERSION_ONLY}/auth/signin` - User login
- **POST** `/{API_START}/{API_VERSION_ONLY}/auth/refresh` - Refresh access token
- **GET** `/{API_START}/{API_VERSION_ONLY}/auth/profile` - Get user profile

---

## Frontend Architecture

### Core Components

#### 1. Application Structure (`client/app/`)
```
app/
├── routes/
│   ├── _index.tsx             # Home page
│   ├── canvas.tsx             # Main workflow editor
│   ├── auth/
│   │   ├── signin.tsx         # Login page
│   │   └── signup.tsx         # Registration page
│   └── workflows.tsx          # Workflow management
├── components/
│   ├── canvas/
│   │   ├── FlowCanvas.tsx     # Main ReactFlow editor
│   │   ├── NodeSidebar.tsx    # Draggable node library
│   │   └── ExecutionPanel.tsx # Workflow execution controls
│   ├── common/
│   │   ├── DraggableNode.tsx  # Node drag component
│   │   └── Header.tsx         # Navigation header
│   └── modals/
│       └── llms/
│           └── OpenAIChatModal.tsx # Node configuration
├── stores/
│   ├── auth.ts                # Authentication state
│   ├── workflows.ts           # Workflow management
│   ├── nodes.ts               # Node library state
│   └── executions.ts          # Execution tracking
├── services/
│   ├── api.ts                 # HTTP client configuration
│   ├── auth.ts                # Authentication API
│   ├── workflows.ts           # Workflow API
│   └── nodes.ts               # Node API
├── types/
│   └── api.ts                 # TypeScript type definitions
└── hooks/
    ├── useAuth.ts             # Authentication hook
    └── useWorkflow.ts         # Workflow management hook
```

#### 2. State Management (Zustand)

**Authentication Store:**
```typescript
interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  signin: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  signout: () => void;
  refresh: () => Promise<void>;
}
```

**Workflow Store:**
```typescript
interface WorkflowStore {
  workflows: Workflow[];
  currentWorkflow: Workflow | null;
  nodes: Node[];
  edges: Edge[];
  isExecuting: boolean;
  loadWorkflows: () => Promise<void>;
  saveWorkflow: (workflow: Workflow) => Promise<void>;
  executeWorkflow: (input: string) => Promise<void>;
}
```

#### 3. ReactFlow Integration
The visual workflow editor uses ReactFlow with custom node types:

```typescript
// Custom Node Types
const nodeTypes = {
  openaiChat: OpenAIChatNode,
  reactAgent: ReactAgentNode,
  bufferMemory: BufferMemoryNode,
  start: StartNode,
  condition: ConditionNode,
  // ... 50+ more node types
};

// Main Canvas Component
function FlowCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onDrop={onDrop}
      onDragOver={onDragOver}
    >
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  );
}
```

---

## Development Setup

### Prerequisites
- **Node.js** 18+ (for frontend)
- **Python** 3.11+ (for backend)
- **PostgreSQL** 14+ (database)
- **Redis** 6+ (caching/sessions)

### Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment configuration
cp .env.example .env
# Edit .env with your API keys and database credentials

# Start development server
python start.py
# OR: uvicorn app.main:app --reload --port 8001
```

### Frontend Setup
```bash
cd client

# Install dependencies
npm install

# Environment configuration
cp .env.example .env
# Edit .env with backend URL

# Start development server
npm run dev
```

### Full Stack Development
```bash
# Terminal 1: Backend
cd backend && python start.py

# Terminal 2: Frontend
cd client && npm run dev

# Access points:
# Frontend: http://localhost:5173
# Backend API: http://localhost:8001
# API Documentation: http://localhost:8001/docs
```

---

## Node System

### Node Categories & Types

#### 1. Language Models (`llms/`)
- **OpenAIChat**: GPT-3.5, GPT-4, GPT-4o models
- **AnthropicClaude**: Claude 3 series models
- **GoogleGemini**: Gemini Pro and Ultra models

#### 2. AI Agents (`agents/`)
- **ReactAgent**: Autonomous reasoning and action agent
- **ToolAgent**: Multi-tool capable agent

#### 3. Memory Management (`memory/`)
- **BufferMemory**: Conversation history storage
- **ConversationMemory**: Multi-turn conversation context
- **SummaryMemory**: Condensed conversation summaries

#### 4. Workflow Chains (`chains/`)
- **SequentialChain**: Linear workflow execution
- **ConditionalChain**: Branching logic implementation
- **LLMChain**: Direct language model chaining
- **MapReduceChain**: Parallel processing patterns

#### 5. External Tools (`tools/`)
- **GoogleSearchTool**: Web search integration
- **TavilySearch**: Advanced web search
- **WikipediaTool**: Wikipedia knowledge access
- **WolframAlphaTool**: Mathematical computations
- **WebBrowserTool**: Web page content extraction

#### 6. Document Processing (`document_loaders/`)
- **PDFLoader**: PDF document ingestion
- **TextDataLoader**: Plain text file processing
- **WebLoader**: Web page content loading
- **YoutubeLoader**: YouTube transcript extraction
- **GitHubLoader**: GitHub repository content

#### 7. Embeddings (`embeddings/`)
- **OpenAIEmbeddings**: OpenAI text-embedding models
- **CohereEmbeddings**: Cohere embedding models
- **HuggingFaceEmbeddings**: Open-source embeddings

#### 8. Vector Stores (`vectorstores/`)
- **ChromaRetriever**: Chroma vector database
- **PineconeVectorStore**: Pinecone cloud vector DB
- **QdrantVectorStore**: Qdrant vector search
- **FaissVectorStore**: Facebook AI Similarity Search

### Node Implementation Pattern

All nodes inherit from `BaseNode` and implement the required interface:

```python
class BaseNode:
    def __init__(self, **kwargs):
        """Initialize node with configuration"""
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute node logic and return outputs"""
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return node metadata for UI"""
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate input parameters"""
```

---

## Authentication & Security

### JWT-Based Authentication
The platform uses JWT tokens with refresh token rotation:

```python
# Authentication Flow
1. User signs up/in with email/password
2. Server generates access token (30min) + refresh token (7 days)
3. Frontend stores tokens in memory (AuthStore)
4. Access token included in API requests
5. Automatic refresh when access token expires
```

### Security Features
- **Password Hashing**: bcrypt with salt rounds
- **Token Validation**: JWT signature verification
- **CORS Configuration**: Controlled cross-origin requests
- **Input Validation**: Pydantic models for request validation
- **SQL Injection Prevention**: SQLAlchemy ORM usage
- **API Key Encryption**: Secure credential storage

### Authorization Levels
- **Public Endpoints**: Health checks, documentation
- **Authenticated Endpoints**: User-specific resources
- **Admin Endpoints**: System management (future)

---

## Database Architecture & Production Setup

### Database Technology Stack
- **Primary Database**: PostgreSQL 14+ (Production Grade)
- **ORM Framework**: SQLAlchemy 2.0+ with asyncio support
- **Migration Tool**: Alembic for version control
- **Connection Management**: AsyncPG for high-performance async operations
- **Backup Support**: psycopg2-binary for maintenance operations

### Complete Database Schema

#### 1. Users Table (`users`)
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50),
    credential TEXT,
    temp_token TEXT,
    token_expiry TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    active_workspace_id UUID,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 2. Workflows Table (`workflows`)
```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    flow_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_workflows_user_id ON workflows(user_id);
CREATE INDEX idx_workflows_is_public ON workflows(is_public);
CREATE INDEX idx_workflows_name ON workflows(name);
CREATE INDEX idx_workflows_created_at ON workflows(created_at);

-- JSONB indexes for flow_data queries
CREATE INDEX idx_workflows_flow_data_gin ON workflows USING GIN (flow_data);

-- Trigger for updated_at
CREATE TRIGGER update_workflows_updated_at BEFORE UPDATE ON workflows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 3. Workflow Templates Table (`workflow_templates`)
```sql
CREATE TABLE workflow_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) DEFAULT 'General',
    flow_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_workflow_templates_category ON workflow_templates(category);
CREATE INDEX idx_workflow_templates_name ON workflow_templates(name);
CREATE INDEX idx_workflow_templates_flow_data_gin ON workflow_templates USING GIN (flow_data);
```

#### 4. Workflow Executions Table (`workflow_executions`)
```sql
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    inputs JSONB,
    outputs JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance and analytics
CREATE INDEX idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX idx_workflow_executions_created_at ON workflow_executions(created_at);
CREATE INDEX idx_workflow_executions_started_at ON workflow_executions(started_at);

-- Composite indexes for complex queries
CREATE INDEX idx_workflow_executions_user_status ON workflow_executions(user_id, status);
CREATE INDEX idx_workflow_executions_workflow_status ON workflow_executions(workflow_id, status);

-- JSONB indexes for inputs/outputs analysis
CREATE INDEX idx_workflow_executions_inputs_gin ON workflow_executions USING GIN (inputs);
CREATE INDEX idx_workflow_executions_outputs_gin ON workflow_executions USING GIN (outputs);
```

#### 5. Execution Checkpoints Table (`execution_checkpoints`)
```sql
CREATE TABLE execution_checkpoints (
    execution_id UUID PRIMARY KEY REFERENCES workflow_executions(id) ON DELETE CASCADE,
    checkpoint_data JSONB NOT NULL,
    parent_checkpoint_id UUID,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_execution_checkpoints_parent ON execution_checkpoints(parent_checkpoint_id);
CREATE INDEX idx_execution_checkpoints_data_gin ON execution_checkpoints USING GIN (checkpoint_data);

-- Trigger for updated_at
CREATE TRIGGER update_execution_checkpoints_updated_at BEFORE UPDATE ON execution_checkpoints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 6. User Credentials Table (`user_credentials`)
```sql
CREATE TABLE user_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    encrypted_secret TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure unique credential names per user
    CONSTRAINT unique_user_credential_name UNIQUE (user_id, name)
);

-- Indexes
CREATE INDEX idx_user_credentials_user_id ON user_credentials(user_id);
CREATE INDEX idx_user_credentials_service_type ON user_credentials(service_type);

-- Trigger for updated_at
CREATE TRIGGER update_user_credentials_updated_at BEFORE UPDATE ON user_credentials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 7. Organizations Table (`organization`)
```sql
CREATE TABLE organization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    admin_user_id UUID REFERENCES users(id),
    default_ws_id UUID,
    organization_type VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_organization_admin_user_id ON organization(admin_user_id);
CREATE INDEX idx_organization_name ON organization(name);

-- Trigger for updated_at
CREATE TRIGGER update_organization_updated_at BEFORE UPDATE ON organization
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 8. Roles Table (`roles`)
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    permissions TEXT
);

-- Insert default roles
INSERT INTO roles (name, description, permissions) VALUES
('admin', 'Full system administrator', 'all'),
('user', 'Standard user with workflow creation', 'create_workflow,execute_workflow,manage_credentials'),
('viewer', 'Read-only access to shared workflows', 'view_workflows,execute_public_workflows');
```

#### 9. Organization Users Table (`organization_user`)
```sql
CREATE TABLE organization_user (
    organization_id UUID REFERENCES organization(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES users(id),
    updated_by UUID NOT NULL REFERENCES users(id),
    
    PRIMARY KEY (organization_id, user_id)
);

-- Indexes
CREATE INDEX idx_organization_user_role_id ON organization_user(role_id);
CREATE INDEX idx_organization_user_status ON organization_user(status);

-- Trigger for updated_at
CREATE TRIGGER update_organization_user_updated_at BEFORE UPDATE ON organization_user
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 10. Login Methods Table (`login_method`)
```sql
CREATE TABLE login_method (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    config TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ENABLE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

-- Indexes
CREATE INDEX idx_login_method_organization_id ON login_method(organization_id);
CREATE INDEX idx_login_method_status ON login_method(status);

-- Trigger for updated_at
CREATE TRIGGER update_login_method_updated_at BEFORE UPDATE ON login_method
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 11. Login Activity Table (`login_activity`)
```sql
CREATE TABLE login_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL,
    activity_code INTEGER NOT NULL,
    message VARCHAR(500) NOT NULL,
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for security monitoring
CREATE INDEX idx_login_activity_username ON login_activity(username);
CREATE INDEX idx_login_activity_attempted_at ON login_activity(attempted_at);
CREATE INDEX idx_login_activity_activity_code ON login_activity(activity_code);

-- Composite index for security analysis
CREATE INDEX idx_login_activity_username_attempted ON login_activity(username, attempted_at);
```

#### 12. Chat Messages Table (`chat_message`)
```sql
CREATE TABLE chat_message (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role VARCHAR(255) NOT NULL,
    chatflow_id UUID NOT NULL,
    content TEXT NOT NULL,
    source_documents VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_chat_message_chatflow_id ON chat_message(chatflow_id);
CREATE INDEX idx_chat_message_role ON chat_message(role);
CREATE INDEX idx_chat_message_created_at ON chat_message(created_at);

-- Composite index for chat history retrieval
CREATE INDEX idx_chat_message_chatflow_created ON chat_message(chatflow_id, created_at);
```

### Database Configuration & Setup

#### Production PostgreSQL Configuration
```ini
# postgresql.conf - Production Settings

# Memory Settings
shared_buffers = 256MB                    # 25% of RAM (for 1GB system)
effective_cache_size = 1GB               # 75% of RAM
work_mem = 4MB                           # Per-operation memory
maintenance_work_mem = 64MB              # Maintenance operations

# Connection Settings
max_connections = 100                     # Adjust based on expected load
listen_addresses = '*'                   # Allow connections from all IPs
port = 5432

# Write-Ahead Logging (WAL)
wal_level = replica                      # Enable replication
max_wal_size = 1GB
min_wal_size = 80MB
checkpoint_completion_target = 0.9

# Query Performance
random_page_cost = 1.1                   # SSD optimization
effective_io_concurrency = 200          # SSD concurrent I/O

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'all'                    # Log all statements (adjust in production)
log_min_duration_statement = 1000       # Log slow queries (>1 second)

# Autovacuum (for maintenance)
autovacuum = on
autovacuum_max_workers = 3
autovacuum_naptime = 1min
```

#### Database Connection Configuration
```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os

# Production Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://kai_user:secure_password@localhost:5432/kai_fusion_prod"
)

# Production Engine Configuration
engine = create_async_engine(
    DATABASE_URL,
    echo=False,                          # Disable SQL logging in production
    future=True,                         # Use SQLAlchemy 2.0 features
    pool_size=20,                        # Connection pool size
    max_overflow=30,                     # Additional connections beyond pool_size
    pool_pre_ping=True,                  # Validate connections before use
    pool_recycle=3600,                   # Recycle connections every hour
    connect_args={
        "server_settings": {
            "application_name": "KAI-Flow-api",
            "jit": "off",                # Disable JIT for consistent performance
        }
    }
)

# Session Factory
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)
```

### Database Security & Encryption

#### Database User & Permissions
```sql
-- Create dedicated database user
CREATE USER kai_user WITH PASSWORD 'your_secure_password_here';

-- Create database
CREATE DATABASE kai_fusion_prod OWNER kai_user;

-- Connect to kai_fusion_prod database
\c kai_fusion_prod

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE kai_fusion_prod TO kai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO kai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO kai_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO kai_user;

-- Future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kai_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO kai_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO kai_user;
```

#### Encryption for Sensitive Data
```sql
-- Enable pgcrypto extension for encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Example: Encrypt sensitive credential data
-- This is handled in application layer, but database supports it
SELECT crypt('password', gen_salt('bf', 8));
```

### Database Migration Strategy

#### Alembic Configuration (`alembic.ini`)
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql+asyncpg://kai_user:password@localhost:5432/kai_fusion_prod

[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -l 79 REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

#### Migration Commands
```bash
# Initialize Alembic (first time only)
alembic init alembic

# Generate new migration
alembic revision --autogenerate -m "Create initial tables"

# Apply migrations
alembic upgrade head

# Check current revision
alembic current

# Show migration history
alembic history

# Downgrade (if needed)
alembic downgrade -1
```

### Backup & Recovery Strategy

#### Daily Backup Script
```bash
#!/bin/bash
# backup_database.sh

DB_NAME="kai_fusion_prod"
DB_USER="kai_user"
BACKUP_DIR="/var/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_backup_$DATE.sql"

# Create backup directory if not exists
mkdir -p $BACKUP_DIR

# Create backup
pg_dump -h localhost -U $DB_USER -d $DB_NAME --no-password --clean --if-exists > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Remove backups older than 30 days
find $BACKUP_DIR -name "${DB_NAME}_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

#### Point-in-Time Recovery Setup
```bash
# Enable archive mode in postgresql.conf
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'
wal_level = replica

# Create archive directory
mkdir -p /var/lib/postgresql/archive
chown postgres:postgres /var/lib/postgresql/archive
```

### Performance Monitoring & Optimization

#### Key Performance Queries
```sql
-- Monitor slow queries
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Monitor index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Monitor table statistics
SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

-- Check connection statistics
SELECT datname, numbackends, xact_commit, xact_rollback, blks_read, blks_hit
FROM pg_stat_database
WHERE datname = 'kai_fusion_prod';
```

#### Database Maintenance Tasks
```sql
-- Weekly maintenance script
-- Analyze tables for query planner
ANALYZE;

-- Reindex if needed (during low-traffic periods)
REINDEX DATABASE kai_fusion_prod;

-- Update table statistics
VACUUM ANALYZE;

-- Clean up old data (example: old login activity)
DELETE FROM login_activity WHERE attempted_at < NOW() - INTERVAL '90 days';
```

### Production Deployment Checklist

#### Database Setup Steps
1. **Install PostgreSQL 14+**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install postgresql-14 postgresql-contrib-14
   
   # CentOS/RHEL
   sudo yum install postgresql14-server postgresql14-contrib
   ```

2. **Configure PostgreSQL**
   - Edit `/etc/postgresql/14/main/postgresql.conf`
   - Edit `/etc/postgresql/14/main/pg_hba.conf` for authentication
   - Restart PostgreSQL service

3. **Create Database and User**
   ```bash
   sudo -u postgres psql
   \i create_database.sql
   ```

4. **Run Initial Migration**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **Load Seed Data** (if any)
   ```bash
   psql -U kai_user -d kai_fusion_prod -f seed_data.sql
   ```

6. **Setup Backup Cron Job**
   ```bash
   # Add to crontab
   0 2 * * * /path/to/backup_database.sh
   ```

7. **Configure Monitoring**
   - Enable `pg_stat_statements` extension
   - Setup log rotation
   - Configure alerting for disk space and connections

### Database Operations
- **Connection Pooling**: SQLAlchemy async engine with optimized pool settings
- **Migration Management**: Alembic for version-controlled schema changes
- **Query Optimization**: Strategic indexing and JSONB optimization for workflow data
- **Transaction Management**: Automatic commit/rollback with proper isolation levels
- **Monitoring**: Built-in PostgreSQL statistics and custom performance queries

---

## API Integration

### External Service Integration

#### OpenAI Integration
```python
class OpenAIChatNode(BaseNode):
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.7, **kwargs):
        self.client = OpenAI(api_key=kwargs.get('api_key'))
        self.model_name = model_name
        self.temperature = temperature
    
    async def execute(self, inputs):
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=inputs['messages'],
            temperature=self.temperature
        )
        return {"content": response.choices[0].message.content}
```

#### Credential Validation
```python
async def validate_openai_credentials(api_key: str, model: str):
    try:
        client = OpenAI(api_key=api_key)
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        return {"valid": True, "message": "Credentials validated successfully"}
    except Exception as e:
        return {"valid": False, "message": str(e)}
```

### Streaming Execution
Server-sent events provide real-time workflow execution updates:

```python
async def stream_workflow_execution(workflow_data: Dict, input_text: str):
    async for chunk in engine.execute_stream(workflow_data, {"input": input_text}):
        yield f"data: {json.dumps(chunk)}\n\n"
```

---

## Testing Strategy

### Backend Testing (`pytest`)
```python
# test_react_workflow.py
class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_react_agent_execution(self):
        """Test ReactAgent workflow execution"""
        
    @pytest.mark.integration
    async def test_openai_integration(self):
        """Test OpenAI API integration"""
        
    @pytest.mark.unit
    def test_node_validation(self):
        """Test node input validation"""
```

#### Test Configuration (`pytest.ini`)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests
    integration: Integration tests
    api: API endpoint tests
    workflows: Workflow execution tests
    auth: Authentication tests
```

### Frontend Testing (`vitest`)
```typescript
// Component Testing
describe('FlowCanvas', () => {
  test('renders workflow canvas', () => {
    render(<FlowCanvas />);
    expect(screen.getByTestId('react-flow')).toBeInTheDocument();
  });
  
  test('handles node drag and drop', () => {
    // Test drag and drop functionality
  });
});

// API Service Testing
describe('WorkflowService', () => {
  test('creates workflow successfully', async () => {
    const workflow = await workflowService.create(mockWorkflowData);
    expect(workflow.id).toBeDefined();
  });
});
```

### Test Coverage Goals
- **Backend**: 80%+ line coverage
- **Frontend**: 70%+ line coverage
- **Critical Paths**: 95%+ coverage (auth, workflow execution)

---

## Deployment & Configuration

### Environment Configuration

#### Backend Environment Variables
```env
# Core Configuration
SECRET_KEY=your-32-character-secret-key
DEBUG=false
LOG_LEVEL=info

# Database
POSTGRES_DB=kai_fusion
POSTGRES_USER=kai_user
POSTGRES_PASSWORD=secure_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql://user:pass@host:port/db

# AI Service APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
TAVILY_API_KEY=...

# Redis
REDIS_URL=redis://localhost:6379

# CORS
ALLOWED_ORIGINS=["http://localhost:5173", "https://yourdomain.com"]
```

#### Frontend Environment Variables
```env
VITE_API_BASE_URL=http://localhost:8001
VITE_API_VERSION=/{API_START}/{API_VERSION_ONLY}
VITE_APP_NAME=KAI-Flow
VITE_ENABLE_ANALYTICS=false
```

### Docker Deployment
```dockerfile
# Backend Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

# Frontend Dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build
CMD ["npm", "run", "preview"]
```

### Production Considerations
- **Reverse Proxy**: Nginx for SSL termination and static serving
- **Database**: PostgreSQL with connection pooling
- **Caching**: Redis for session storage and caching
- **Monitoring**: Health check endpoints and logging
- **Security**: Environment variable encryption, HTTPS enforcement

---

## Performance & Monitoring

### Performance Optimizations

#### Backend Optimizations
- **Async/Await**: Non-blocking I/O operations
- **Connection Pooling**: Database connection reuse
- **Caching**: Redis for frequently accessed data
- **Lazy Loading**: On-demand node registration
- **Streaming**: Server-sent events for real-time updates

#### Frontend Optimizations
- **Code Splitting**: Dynamic imports for routes
- **Component Memoization**: React.memo for expensive components
- **Virtual Scrolling**: Large node lists optimization
- **Debounced Input**: Reduced API calls during user input
- **Progressive Loading**: Incremental data fetching

### Monitoring & Observability

#### Health Checks
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "database": await check_database(),
            "node_registry": check_node_registry(),
            "session_manager": check_sessions()
        }
    }
```

#### Logging Strategy
```python
import logging
import structlog

# Structured logging configuration
logger = structlog.get_logger()

# Request/Response logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    logger.info(
        "api_request",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration=duration
    )
    return response
```

#### Metrics Collection
- **Request Latency**: API response times
- **Error Rates**: Failed requests by endpoint
- **Node Execution Times**: Workflow performance tracking
- **Memory Usage**: Backend resource consumption
- **User Activity**: Workflow creation and execution statistics

---

## Future Development Roadmap

### Planned Features
1. **Enhanced Node Library**: 100+ nodes across more categories
2. **Collaborative Workflows**: Multi-user workflow editing
3. **Workflow Templates**: Pre-built workflow marketplace
4. **Advanced Analytics**: Detailed execution monitoring
5. **Enterprise Features**: RBAC, audit logs, compliance tools
6. **Mobile Interface**: Responsive design for mobile devices
7. **API Marketplace**: Third-party node integrations
8. **Workflow Versioning**: Git-like version control for workflows

### Technical Improvements
1. **Database Migrations**: Alembic integration for schema changes
2. **Comprehensive Testing**: 90%+ test coverage across all components
3. **Performance Monitoring**: APM integration (DataDog, New Relic)
4. **Container Orchestration**: Kubernetes deployment manifests
5. **CI/CD Pipeline**: Automated testing and deployment
6. **Documentation**: Auto-generated API docs and user guides

---

This documentation provides a comprehensive overview of the KAI-Flow platform architecture, implementation details, and development practices. For specific API endpoint documentation, refer to the accompanying `API_DOCUMENTATION.md` file.