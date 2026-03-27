<p>
  <img src="./banner.png" alt="KAI‑Flow Banner" width="100%" />
</p>

<div>
    <h4 align="center">
        <a href="https://kaiflow.io/" target="_blank">
            <img src="https://img.shields.io/badge/Website-kaiflow.io-blue">
        </a>
        <a href="https://www.kaiflow.io/docs" target="_blank">
            <img src="https://img.shields.io/badge/Docs-API%20Documentation-orange">
        </a>
        <a href="https://github.com/kafein-product-space/KAI-Flow/stargazers" target="_blank">
            <img src="https://img.shields.io/github/stars/kafein-product-space/KAI-Flow?style=social">
        </a>
        <a href="https://github.com/kafein-product-space/KAI-Flow/network/members" target="_blank">
            <img src="https://img.shields.io/github/forks/kafein-product-space/KAI-Flow?style=social">
        </a>
        <a href="https://github.com/kafein-product-space/KAI-Flow/pulls" target="_blank">
            <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
        </a>
        <a href="https://github.com/kafein-product-space/KAI-Flow/blob/main/LICENSE" target="_blank">
            <img src="https://img.shields.io/github/license/kafein-product-space/KAI-Flow">
        </a>
    </h4>
</div>

<div align="center">
<h1>KAI Flow: a visual platform for building AI-powered assistants </h1>
</div>


Using a simple drag-and-drop interface, you can design workflows that answer questions, search the web, process documents, and automate tasks. All workflows are created and managed on a visual canvas, allowing you to see how each component works together. You can test your assistants in real time, adjust their behavior, and deploy them with confidence.


## 🎬 Showcase

<p>
  <img src="./demo.gif" alt="KAI‑Flow Demo" width="100%" />
</p>

<p>
  <img src="./demo.png" alt="KAI‑Flow Screenshot" width="100%" />
</p>

---

## 📚 Table of Contents

* [⚡ Quick Start with Docker](#-quick-start-with-docker-)
* [🔐 Environment Variables](#-environment-variables)
* [🧪 Local Development (Python venv / Conda)](#-local-development-python-venv--conda)
* [🧭 VS Code Debugging](#-vs-code-debugging-vscodelaunchjson)
* [🧱 Project Structure](#-project-structure)
* [✨ App Overview](#-app-overview-what-you-can-build)
* [📊 Repository Stats](#-repository-stats--stars---downloads)
* [🙌 Contributing](#-contributing-with-user-icons)
* [🆘 Troubleshooting](#-troubleshooting)
* [🤝 Code of Conduct](#-code-of-conduct)
* [📝 License](#-license)



## ⚡ Quick Start with Docker 🐳

**Prerequisites**

* **Python** 3.11
* **Node.js** ≥ 18.15
* **Docker** & **Docker Compose**

### Step 1 — Set Up a Python Environment

Choose **one** of the following:

#### Option A — venv (recommended)

```bash
python -m venv .venv

# Windows (Command Prompt)
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -r backend/requirements.txt
```

#### Option B — Conda

```bash
conda create -n kai-flow python=3.11 -y
conda activate kai-flow
pip install -r backend/requirements.txt
```

### Step 2 — Configure Environment Variables

Rename `.env.example` to `.env` in the project root directory and update the values as needed.

### Step 3 — Start PostgreSQL

```bash
docker run --name kai ^
  -e POSTGRES_DB=kai ^
  -e POSTGRES_USER=kai ^
  -e POSTGRES_PASSWORD=kai ^
  -p 5432:5432 -d postgres:15
```


### Step 4 — Initialize the Database Schema

```bash
python backend/migrations/database_setup.py
```

### Step 5 — Start the Backend & Frontend

```bash
docker compose up -d
```

Once running, open:

* **Frontend:** [http://localhost:23058](http://localhost:23058)
* **Backend (Swagger):** [http://localhost:23056/docs](http://localhost:23056/docs)


## 🔐 Environment Variables

Create: `.env` in Main Directory end paste below content.

```dotenv
# Core Application Settings
SECRET_KEY=your-secret-key-here-change-in-production
MASTER_API_KEY=your-api-key-to-access-workflows
CREDENTIAL_MASTER_KEY=credential-master-key-here
ENVIRONMENT=development
BACKEND_PORT=23056
BACKEND_DEBUG=true
PYTHONUNBUFFERED=1
ROOT_PATH=/api/kai

# Database Configuration
DATABASE_URL=postgresql://kai:kai@127.0.0.1:5432/kai
ASYNC_DATABASE_URL=postgresql+asyncpg://kai:kai@127.0.0.1:5432/kai
POSTGRES_DB=kai
POSTGRES_USERNAME=kai
POSTGRES_PASSWORD=kai
DATABASE_SSL=false
DISABLE_DATABASE=false
CREATE_DATABASE=true

# SSL Certificates
SSL_CERTFILE=cert/cert.pem
SSL_KEYFILE=cert/key.pem

# LangSmith / LangChain Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langchain_api_key
LANGCHAIN_PROJECT=kai-fusion-workflows
ENABLE_WORKFLOW_TRACING=true
TRACE_AGENT_REASONING=true
TRACE_MEMORY_OPERATIONS=true

# Frontend Settings
VITE_BASE_PATH=/
VITE_API_BASE_URL=http://localhost:23056
VITE_API_VERSION=/api/v1
VITE_NODE_ENV=development
VITE_ENABLE_LOGGING=true

# Logging
LOG_LEVEL=DEBUG
ALLOWED_ORIGINS=*

# Keycloak (SSO)
KEYCLOAK_ENABLED=true
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_VERIFY_SSL=false
KEYCLOAK_REALM=agenticgro-dev
KEYCLOAK_CLIENT_ID=agenticgro
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=agenticgro-dev
VITE_KEYCLOAK_CLIENT_ID=agenticgro
```

> **Docker note:** If the backend runs inside a Docker container and PostgreSQL runs on the host, replace `127.0.0.1` with `host.docker.internal` in `DATABASE_URL`.

---

## 🧪 Local Development (Python venv / Conda)

You can use **venv** or **conda**. Below are both options.

### Option A — venv (recommended)

```bash
python -m venv .venv

# Windows (Command Prompt)
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Option B — Conda

```bash
conda create -n kai-flow python=3.11 -y
conda activate kai-flow
pip install -r backend/requirements.txt
```

### Initialize the Database Schema

Ensure your PostgreSQL container is running, then:

```bash
python backend/migrations/database_setup.py
```

### Run the Backend

```bash
python backend/main.py
```

### Run the Frontend

```bash
cd client
npm install
npm run dev
# Open the printed Vite URL (e.g. http://localhost:5173)
```

### SSL Certificates (Optional)

To run the backend with HTTPS locally, generate self-signed certificates:

```bash
cd backend/cert

# Windows (PowerShell)
$env:OPENSSL_CONF="C:\Program Files\Git\usr\ssl\openssl.cnf"; openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/C=TR/ST=Istanbul/L=Istanbul/O=KAI/OU=Dev/CN=localhost"

# macOS / Linux
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/C=TR/ST=Istanbul/L=Istanbul/O=KAI/OU=Dev/CN=localhost"
```

### Widget (Embeddable)

A standalone chat widget for embedding KAI‑Flow agents into other sites.

```bash
cd widget
npm install
npm run dev
```


## 🧭 VS Code Debugging (`.vscode/launch.json`)

Create the folder: `.vscode/` at the repository root and add `launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Backend Main",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/backend/app.py",
      "console": "integratedTerminal",
      "env": { "DOTENV_PATH": "${workspaceFolder}/backend/.env" }
    }
  ]
}
```






## 🧱 Project Structure

```
KAI-Flow/
├─ backend/                 # FastAPI Backend (Python 3.11)
│  ├─ app/
│  │  ├─ api/               # REST API endpoints
│  │  ├─ auth/              # Authentication logic
│  │  ├─ core/              # Core utilities (config, engine, etc.)
│  │  ├─ middleware/         # Custom middleware
│  │  ├─ models/            # SQLAlchemy database models
│  │  ├─ nodes/             # Workflow node definitions
│  │  │  ├─ agents/         # AI Agent nodes
│  │  │  ├─ llms/           # LLM provider nodes
│  │  │  ├─ tools/          # Tool nodes (web search, code, etc.)
│  │  │  ├─ memory/         # Memory / context nodes
│  │  │  ├─ embeddings/     # Embedding nodes
│  │  │  ├─ vector_stores/  # Vector store nodes
│  │  │  ├─ splitters/      # Text splitter nodes
│  │  │  ├─ triggers/       # Workflow trigger nodes
│  │  │  └─ document_loaders/
│  │  ├─ schemas/           # Pydantic schemas
│  │  ├─ services/          # Business logic services
│  │  └─ routes/            # Route definitions
│  ├─ migrations/           # Database setup scripts
│  ├─ main.py               # Application entry point
│  └─ requirements.txt      # Python dependencies
├─ client/                  # React 19 Frontend
│  ├─ app/
│  │  ├─ components/        # React components
│  │  │  ├─ canvas/         # Workflow canvas
│  │  │  ├─ nodes/          # Node UI components
│  │  │  └─ modals/         # Configuration modals
│  │  ├─ routes/            # Page routes
│  │  ├─ services/          # API service layer
│  │  ├─ stores/            # Zustand state stores
│  │  └─ lib/               # Utilities
│  ├─ package.json
│  └─ vite.config.ts
├─ widget/                  # Embeddable Chat Widget
│  ├─ src/                  # Widget source
│  ├─ widget.js             # Pre-built widget bundle
│  └─ package.json
├─ docs/                    # Documentation (MkDocs)
├─ .env.example             # Environment variable template
├─ docker-compose.yml       # Docker Compose configuration
├─ Dockerfile               # Backend Docker image
└─ README.md
```


## ✨ App Overview (What you can build)

* **Visual Workflow Builder**: Drag-and-drop interface powered by XYFlow 12 for creating AI agents and chains.
* **Modern Tech Stack**: React 19.1, React Router 7, Vite 6.3, Tailwind 4.1, DaisyUI 5 (Frontend) + FastAPI 0.116, LangChain 0.3, LangGraph 0.6 (Backend).
* **AI/ML Framework**: Integrated LangChain, LangGraph, and LangSmith for building and debugging complex agent flows.
* **Vector Database**: PostgreSQL with pgvector for embedding storage and semantic search.
* **Node Types**: LLMs, Agents, Tools (Web Search, Code Execution), Memory, Embeddings, Vector Stores, Document Loaders, Text Splitters, Triggers.
* **Embeddable Widget**: Export your agents as an embeddable widget (`@kaiFlow/widget` on npm).
* **Secure**: JWT-based authentication with Keycloak integration support.
* **Scheduling**: Built-in cron-based workflow scheduling with APScheduler.


## 📊 Repository Stats (⭐ Stars & ⬇️ Downloads)

### ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=kafein-product-space/KAI-Flow&type=Date)](https://star-history.com/#kafein-product-space/KAI-Flow)

### ⬇️ Downloads

| Metric                   | Badge                                                                                                                                      |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **All releases (total)** | ![All Downloads](https://img.shields.io/github/downloads/kafein-product-space/KAI-Flow/total?label=All%20downloads)                      |
| **Latest release**       | ![Latest Release Downloads](https://img.shields.io/github/downloads/kafein-product-space/KAI-Flow/latest/total?label=Latest%20downloads) |
| **Stars (live)**         | ![GitHub Repo stars](https://img.shields.io/github/stars/kafein-product-space/KAI-Flow?style=social)                                     |
| **Forks (live)**         | ![GitHub forks](https://img.shields.io/github/forks/kafein-product-space/KAI-Flow?style=social)                                          |



## 🙌 Contributing

We welcome PRs! Please:

1. Open an issue describing the change or bug.
2. Fork the repo and create a feature branch.
3. Add or adjust tests where applicable.
4. Open a PR with a clear description and screenshots/GIFs.

### 👥 Contributors

<a href="https://github.com/kafein-product-space/KAI-Flow/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=kafein-product-space/KAI-Flow" alt="Contributors" />
</a>

### ⭐ Stargazers & 🍴 Forkers

[⭐ Stargazers](https://github.com/kafein-product-space/KAI-Flow/stargazers) · [🍴 Forkers](https://github.com/kafein-product-space/KAI-Flow/network/members)



## 🆘 Troubleshooting

**Port 5432 already in use**

* Stop any existing Postgres: `docker ps`, then `docker stop <container>`
* Or change the host port mapping: `-p 5433:5432`

**Cannot connect to Postgres**

* Verify envs in both `backend/.env` and `backend/migrations/.env`
* Ensure container is healthy: `docker logs kai`

**Migrations didn’t run / tables missing**

* Re-run: `python backend/migrations/database_setup.py`
* Ensure `CREATE_DATABASE=true` in **migrations** `.env` (and `false` in runtime `.env`)

**Frontend cannot reach backend**

* Check `client/.env` → `VITE_API_BASE_URL=http://localhost:8000`
* CORS: ensure backend CORS is configured for your dev origin

**VS Code doesn’t load env**

* Using our snippet? Make sure your app reads `DOTENV_PATH`
* Alternative: VS Code `"envFile": "${workspaceFolder}/backend/.env"`


## 🤝 Code of Conduct

Please follow our [Contributor Covenant Code of Conduct](./CODE_OF_CONDUCT.md) to keep the community welcoming.


## 📝 License

Source code is available under the **Apache License 2.0** — see [`LICENSE`](./LICENSE) for details.