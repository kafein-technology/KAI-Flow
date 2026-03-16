# KAI-Flow User Guide

Welcome to the KAI-Flow User Guide! This comprehensive documentation will help you setup, navigate, and master the KAI-Flow platform.

## Table of Contents

1.  [Introduction](#introduction)
2.  [Before Installation](#before-installation)
3.  [Hardware Requirements](#hardware-requirements)
4.  [Network Requirements](#network-requirements)
5.  [Docker Installation](#docker-installation)
6.  [Extracting Packages](#extracting-packages)
7.  [Loading Docker Images](#loading-docker-images)
8.  [Deployment](#deployment)
9.  [Local Installation (Development)](#local-installation)
10. [Widget Integration](#widget-integration)
11. [Monitoring](#monitoring)
12. [Interface Overview](#interface-overview)
13. [Core Concepts](#core-concepts)
14. [Node Reference](#node-reference)
15. [Tutorial: Building a Research Agent](#tutorial-building-a-research-agent)
16. [Troubleshooting](#troubleshooting)
17. [License](#license)

---

## <a name="introduction"></a>Introduction

KAI-Flow is a tool that helps you create smart assistants. These assistants can answer questions, search for information on the internet, read documents, and complete tasks automatically. You do not need to know how to write code to use it.

Think of it like building with blocks. You pick the pieces you need, connect them together, and your assistant is ready to work. For example, you can create an assistant that searches the web for news and summarizes it for you. Or one that reads your documents and answers questions about them.

The platform shows everything visually on a canvas. You can see how your assistant works, test it by chatting with it, and make changes easily. When you are happy with your assistant, you can share it with others or add it to your website.

KAI-Flow is designed for everyone. Whether you are a business owner who wants to automate customer support, a researcher who needs help processing documents, or simply curious about what AI can do, this tool makes it possible without any technical background.


## <a name="before-installation"></a>Before Installation

Before installing KAI-Flow, make sure you have the following ready:

*   **Docker**: KAI-Flow runs inside containers. You need Docker installed on your computer.
*   **Git**: Required to download the project files.
*   **Environment Files**: You will need to set up configuration files (`.env`) for the backend and frontend.
*   **Database**: PostgreSQL is required. You can run it inside Docker or use an existing database.

---

## <a name="hardware-requirements"></a>Hardware Requirements

To ensure smooth operation, particularly when orchestrating multiple concurrent AI agents, we recommend the following hardware specifications:

### Minimum Specifications
*   **CPU**: 2 vCPUs
*   **RAM**: 4 GB
*   **Storage**: 10 GB free disk space (SSD recommended)

### Recommended Specifications (Production)
*   **CPU**: 4+ vCPUs
*   **RAM**: 8 GB+ (16 GB for heavy vector store usage)
*   **Storage**: 20 GB+ NVMe SSD

---

## <a name="network-requirements"></a>Network Requirements

KAI-Flow runs on a microservices architecture. Ensure the following network configurations are set:

### Internal Ports (Docker Network)
The services communicate internally via the `kai_network` bridge network:
*   **Backend**: Internal communication on port `8000`.
*   **Frontend**: Internal communication on port `3000`.
*   **Database**: PostgreSQL default port `5432`.

### External Access Ports
These ports must be exposed or allowed through your firewall:
*   **Backend API**: Mapped to host port `${BACKEND_PORT:-23056}` (default: **23056**).
*   **Frontend UI**: Mapped to host port **23058**.
*   **Widget**: Mapped to host port **23059**.

### Outbound Connectivity
The backend requires outbound internet access to reach external AI providers and tool services:
*   `api.openai.com` (OpenAI API)
*   `api.tavily.com` (Search Tool)
*   `api.smith.langchain.com` (LangSmith Tracing)

---

## <a name="docker-installation"></a>Docker Installation

Docker is the primary deployment method for KAI-Flow.

### 1. Install Docker Engine
*   **Windows & macOS**: Download and install **Docker Desktop** from [docs.docker.com](https://docs.docker.com/engine/install/).
*   **Linux (Ubuntu/Debian)**:
    ```bash
    sudo apt-get update
    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

### 2. Verify Installation

After installation, open your terminal and run these commands one by one to make sure Docker is working:

```bash
docker info
docker compose version
```

---

## <a name="extracting-packages"></a>Extracting Packages

If you are deploying from source code:

1.  **Clone the Repository**: Open your terminal and run these commands one by one:

    ```bash
    git clone https://github.com/kafein-product-space/KAI-Flow.git
    cd KAI-Flow
    ```

If you have received a release archive (`.zip` or `.tar.gz`):

1.  **Unzip the Archive**:
    *   **Windows**: Right-click -> "Extract All".
    *   **Linux/macOS**:
        ```bash
        unzip kai-Flow-release.zip
        # or
        tar -xvzf kai-Flow-release.tar.gz
        ```
2.  **Navigate to Directory**: Open your terminal and go into the project folder:

    ```bash
    cd kai-Flow
    ```

---

## <a name="loading-docker-images"></a>Loading Docker Images

You can deploy KAI-Flow by building images locally or pulling them from a registry (if configured).

### Option A: Build Locally (Recommended)

This builds the `kaiFlow-be`, `kaiFlow-fe`, and `kai-widget` images from source. Open your terminal in the project folder and run:

```bash
docker compose build
```

### Option B: Pull Pre-built Images

If you are using a registry, open your terminal and run this command:

```bash
docker compose pull
```

---

## <a name="deployment"></a>Deployment

Follow these steps to launch the KAI-Flow stack.

### 1. Configuration (`.env`)

You must configure the environment variables before starting.

#### Backend Migrations `.env`

Create: `backend/migrations/.env`

```dotenv
ASYNC_DATABASE_URL=postgresql+asyncpg://kai:kai@localhost:5432/kai
DATABASE_URL=postgresql://kai:kai@localhost:5432/kai
CREATE_DATABASE=true
```

#### Backend Runtime `.env`

Create: `backend/.env`

```dotenv
ASYNC_DATABASE_URL=postgresql+asyncpg://kai:kai@localhost:5432/kai
DATABASE_URL=postgresql://kai:kai@localhost:5432/kai
CREATE_DATABASE=false
POSTGRES_DB=kai
POSTGRES_PASSWORD=kai

# LangSmith / LangChain tracing (optional but recommended for debugging)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_api_key
LANGCHAIN_PROJECT=kai-Flow-workflows
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
ENABLE_WORKFLOW_TRACING=true
TRACE_MEMORY_OPERATIONS=true
TRACE_AGENT_REASONING=true
```

#### Frontend `.env`

Create: `client/.env`

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_API_VERSION=/api/v1 (Derived from VITE_API_START and VITE_API_VERSION_ONLY)
VITE_API_START=api
VITE_API_VERSION_ONLY=v1
VITE_NODE_ENV=development
VITE_ENABLE_LOGGING=true
```

### 2. Start Services

Once your configuration files are ready, open your terminal in the project folder and run this command to start all services:

```bash
docker compose up -d
```

### 3. Verify Health

After starting the services, run this command to check if everything is running:

```bash
docker compose ps
```

*   **Frontend Dashboard**: [http://localhost:23058](http://localhost:23058)
*   **Backend API Docs**: [http://localhost:23056/docs](http://localhost:23056/docs)
*   **Chat Widget**: [http://localhost:23059](http://localhost:23059)

---

## <a name="local-installation"></a>Local Installation (Development)

For development purposes or if you prefer running without Docker Compose, you can run the services individually.

#### 1. Backend Setup
1.  **Run Database**: You need a registered PostgreSQL instance.
    ```bash
    docker run --name kai -e POSTGRES_DB=kai -e POSTGRES_USER=kai -e POSTGRES_PASSWORD=kai -p 5432:5432 -d postgres:15
    ```
2.  **Setup Python Environment**:
    ```bash
    cd backend
    python -m venv .venv
    # Windows: .venv\Scripts\Activate.ps1 | Linux/Mac: source .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Initialize DB & Run**: Run these commands one by one to set up the database and start the backend:

    ```bash
    python migrations/database_setup.py
    python main.py
    ```

#### 2. Frontend Setup

1.  **Install & Run**: Open a new terminal, go to the client folder, and run these commands one by one:

    ```bash
    cd client
    npm install
    npm run dev
    ```

    When finished, open your browser and go to `http://localhost:5173`.

---

## <a name="widget-integration"></a>Widget Integration

Embed KAI-Flow agents into any website using the standalone widget.

### Installation

The widget source is located in `widget/`. Open your terminal and run these commands one by one:

```bash
cd widget
npm install
npm run dev
```

### Embedding
Include the script in your HTML page:
```html
<script src="http://localhost:23059/widget.js" 
        data-agent-id="YOUR_AGENT_ID" 
        data-api-url="http://localhost:YOUR_BACKEND_PORT">
</script>
```

---

## <a name="monitoring"></a>Monitoring

To keep track of your agents and system health:

### System Logs
View real-time logs from all containers:
```bash
docker compose logs -f
```

### LangSmith Tracing
For detailed AI observability, configure LangSmith variables in `backend/.env`:
*   `LANGCHAIN_TRACING_V2=true`
*   `LANGCHAIN_API_KEY=<your-key>`
*   `LANGCHAIN_PROJECT=kai-Flow-workflows`

This allows you to inspect every step of your agent's reasoning, tool calls, and latency usage in the LangSmith dashboard.

---

## <a name="interface-overview"></a>Interface Overview

The platform is designed with a streamlined user flow:

### 1. Sign In

When you first open the platform, you can create a new account by signing up with your email and password. After that, you can sign in anytime using your credentials.

### 2. Dashboard
The central hub for managing your work.
*   **Active Workflows**: Grid view of all your agents.
*   **Execution History**: Logs of past agent runs (status/time).
*   **System Status**: Health checks for database and API.

### 3. Workflow Canvas
The main builder interface.
*   **Node Sidebar**: Drag-and-drop nodes (Agents, LLMs, Tools).
*   **Infinite Canvas**: Visual workspace for connecting logic.
*   **Properties Panel**: Configure node details (e.g., set `Temperature` for LLMs).
*   **Interaction Panel**: Integrated Chat and Trace view to test and debug agents in real-time.

---

## <a name="core-concepts"></a>Core Concepts

*   **Nodes**: Functional blocks (LLMs, Tools, Agents).
*   **Edges**: Connections defining data and control flow.
*   **Agents**: "Brains" that decide which tools to use.
*   **Workflows**: The complete graph of connected nodes.

---

## <a name="node-reference"></a>Node Reference

### Agents & LLMs
*   **React Agent**: The reasoning engine. Uses tools to solve complex tasks using ReAct logic.
*   **OpenAI Chat**: Integrates OpenAI's GPT models (GPT-4o, etc.).

### Tools
*   **Tavily Search**: Optimized web search for AI agents.
*   **HTTP Client**: Generic API connector (GET/POST/PUT).
*   **Retriever**: Fetches relevant documents from Vector Memory.
*   **Cohere Reranker**: improves retrieval accuracy by re-ranking results.

### Memory & Data
*   **Buffer Memory**: Stores short-term conversation context.
*   **Conversation Memory**: Manages persistent chat history.
*   **Vector Store**: Interface for PostgreSQL/pgvector operations.
*   **OpenAI Embeddings**: Generates vector embeddings for text.

### Document Processing
*   **Document Loader**: Ingests files (PDF, TXT, CSV).
*   **Web Scraper**: Extracts content from websites.
*   **Chunk Splitter**: Breaks documents into tokens for embedding.

### Triggers & Flow
*   **Start / End**: Define workflow entry and exit points.
*   **Timer Trigger**: Scheduled executions (Cron jobs).
*   **Webhook Trigger**: External HTTP event triggers.

---

## <a name="tutorial-building-a-research-agent"></a>Tutorial: Building a Research Agent

1.  **Drag Nodes**: Add **OpenAI Chat**, **Tavily Search**, and **React Agent**.
2.  **Configure**: Set API Keys and Model (GPT-4o).
3.  **Connect**:
    *   OpenAI `llm` -> Agent `llm`
    *   Tavily `tool` -> Agent `tools`
4.  **Run**: Open Chat, ask a question ("Latest AI news?"), and watch the agent research and answer.

---

## <a name="troubleshooting"></a>Troubleshooting

### Backend Startup Issues

**`ModuleNotFoundError: No module named '...'`**
*   Ensure you activated your virtual environment: `source .venv/bin/activate` or `.venv\Scripts\activate`.
*   Run `pip install -r backend/requirements.txt` again to ensure all dependencies are installed.
*   Verify you are running the command from the project root.

**`Address already in use` / `Port 8000 is occupied`**
*   Another instance of the backend might be running. Check your terminal tabs.
*   Kill the process using port 8000: `lsof -i :8000` (Mac/Linux) or `netstat -ano | findstr :8000` (Windows).

**`Failed to initialize node registry`**
*   Check the logs for specific node import errors.
*   Ensure all new nodes in `backend/app/nodes` have valid structure and imports.

### Database & Migrations

**`CREATE_DATABASE environment variable is not set to 'true'`**
*   When running `database_setup.py`, ensure your `backend/migrations/.env` file exists and contains `CREATE_DATABASE=true`.
*   Load the variables explicitly if needed: `export $(grep -v '^#' backend/migrations/.env | xargs)` (Linux/Mac) before running the script.

**`Connection refused` / `Cannot connect to Postgres`**
*   Ensure the Docker container is running: `docker ps`.
*   Check if port 5432 is correctly mapped.
*   Verify `DATABASE_URL` in `.env` matches your Docker configuration (default: `postgresql://kai:kai@localhost:5432/kai`).

**`relation "..." does not exist`**
*   The tables haven't been created yet. Run `python backend/migrations/database_setup.py`.
*   Check `database_setup.log` in the `backend` directory for detailed error messages during migration.

**Syncing Columns / Schema Mismatches**
*   The setup script attempts to auto-sync columns. If you see warnings about "Type Mismatches", you may need to manually adjust your DB or Model definitions.
*   Use `--force` with `database_setup.py` to recreate tables (WARNING: Data loss) if you are in early development.

### Frontend & Connectivity

**`Proxy error` or `ETIMEDOUT` in frontend console**
*   The frontend cannot reach the backend at `http://localhost:8000`.
*   Ensure the backend is running and healthy (`http://localhost:8000/health` or `http://localhost:8000/api/health`).
*   Check the terminal where `npm run dev` is running—the proxy logs will show if requests are being attempted.

**CORS Errors (`Access-Control-Allow-Origin`)**
*   Verify `backend/main.py` has the correct `allow_origins`.
*   In development, the proxy in `vite.config.ts` handles most requests, but direct calls might trigger CORS if not configured.

**Changes not reflecting**
*   Vite uses HMR (Hot Module Replacement). If the app state gets stuck, try a hard refresh (Ctrl+Shift+R / Cmd+Shift+R).
*   For backend changes, ensure `uvicorn` is running with `--reload`.

### Logging & Debugging

*   **Backend Logs**: The backend uses enhanced logging. Check the terminal output for formatted logs.
*   **Database Setup Logs**: Check `database_setup.log` in the `backend` directory.
*   **Frontend Logs**: Check the browser console (F12) and the terminal running Vite.

---

## <a name="license"></a>License
**Apache License 2.0**. Open usage for commercial and private projects. See `LICENSE` for details.
