<p>
  <img src="./banner.png" alt="KAI‑Fusion Banner" width="100%" />
</p>

[![License](https://img.shields.io/github/license/kafein-product-space/KAI-Fusion)](./LICENSE)
![GitHub Repo stars](https://img.shields.io/github/stars/kafein-product-space/KAI-Fusion?style=social)
![GitHub forks](https://img.shields.io/github/forks/kafein-product-space/KAI-Fusion?style=social)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

KAI‑Fusion is an open‑source, visual workflow builder for AI agents. It features a robust **Python 3.11 (FastAPI 0.116)** backend with **LangChain** and **LangGraph**, a modern **React 19.1 (React Router 7, Vite 6.3, Tailwind 4, DaisyUI 5)** frontend, and uses **PostgreSQL** with **pgvector** for persistence.

You can run the full stack locally using Docker (with an external DB) or set up a development environment with Python and Node.js.

---

## 🎬 Showcase

<!-- Inline demo video (GitHub renders HTML) -->

<p>
  <img src="./demo.gif" alt="KAI-Fusion Demo" width="100%" />
</p>

<!-- Screenshot -->

<p>
  <img src="./demo.png" alt="KAI‑Fusion Screenshot" width="100%" />
</p>

---

### 🔗 Quick Links

* **Website (Preview)**: [https://kai-fusion-blond.vercel.app](https://kai-fusion-blond.vercel.app)
* **API Docs (local)**: [http://localhost:8000/docs](http://localhost:8000/docs) (FastAPI Swagger UI)
* **Star / Fork**: [https://github.com/kafein-product-space/KAI-Fusion](https://github.com/kafein-product-space/KAI-Fusion)

---

## 📚 Table of Contents

* ⚡ Quick Start (TL;DR)
* 🐘 PostgreSQL (Docker)
* 🔐 Environment Variables

  * Backend **migrations** `.env`
  * Backend runtime `.env`
  * Frontend `.env`
* 🧪 Local Development (Python venv / Conda)
* 🧭 VS Code Debugging (`.vscode/launch.json`)
* 🐳 Docker (Compose & Images)
* 🧱 Project Structure
* ✨ App Overview (What you can build)
* 📊 Repository Stats (⭐ Stars & ⬇️ Downloads)
* 🙌 Contributing (with user icons)
* 🆘 Troubleshooting
* 🤝 Code of Conduct
* 📝 License

---

## ⚡ Quick Start (TL;DR)

**Prerequisites**

* **Python** = 3.11
* **Node.js** ≥ 18.15 (Vite)
* **Docker** & **Docker Compose**

```bash
# 1) Start Postgres 15 in Docker (change values if you like)
docker run --name kai \
  -e POSTGRES_DB=kai \
  -e POSTGRES_USER=kai \
  -e POSTGRES_PASSWORD=kai \
  -p 5432:5432 -d postgres:15

# 2) Create env files (see sections below for full content)
#    - backend/migrations/.env
#    - backend/.env

# 3) Create virtual environment & install backend deps
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt

# 4) Initialize DB schema (runs inside your local machine)
python backend/migrations/database_setup.py

# 5) Run backend (choose one)
# a) VS Code debug (recommended) — see launch.json section below
# b) Or direct
python backend/app.py

# 6) Frontend
# create client/.env as shown below
cd client && npm install && npm run dev
# Open the printed Vite URL (e.g. http://localhost:5173)
```

> **Tip:** Replace all `kai` defaults (DB name/user/password) for your own environment in production.

---

## 🐘 PostgreSQL (Docker)

Run a local Postgres 15 instance. Feel free to change container name/ports.

```bash
docker run --name kai \
  -e POSTGRES_DB=kai \
  -e POSTGRES_USER=kai \
  -e POSTGRES_PASSWORD=kai \
  -p 5432:5432 -d postgres:15
```

* Container: `kai`
* Host port: `5432` → Container port: `5432`
* Default DB: `kai` (change if you want)

---

## 🔐 Environment Variables

KAI‑Fusion uses **two backend `.env` files** and **one frontend `.env`**.

> **Path note:** In your editor, `${workspaceFolder}` refers to the repository root.

### 1) Backend **migrations** `.env`

Create: `backend/migrations/.env`

```dotenv
ASYNC_DATABASE_URL=postgresql+asyncpg://kai:kai@localhost:5432/kai
DATABASE_URL=postgresql://kai:kai@localhost:5432/kai
CREATE_DATABASE=true
```

### 2) Backend runtime `.env`

Create: `backend/.env`

```dotenv
ASYNC_DATABASE_URL=postgresql+asyncpg://kai:kai@localhost:5432/kai
DATABASE_URL=postgresql://kai:kai@localhost:5432/kai
CREATE_DATABASE=false
POSTGRES_DB=kai
POSTGRES_PASSWORD=kai
ROOT_PATH="/api/kai"

# LangSmith / LangChain tracing (optional but recommended for debugging)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_api_key
LANGCHAIN_PROJECT=kai-fusion-workflows
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
ENABLE_WORKFLOW_TRACING=true
TRACE_MEMORY_OPERATIONS=true
TRACE_AGENT_REASONING=true

SSL_KEYFILE=cert\key.pem
SSL_CERTFILE=cert\cert.pem
```

### 3) Frontend `.env`

Create: `client/.env`

```dotenv
# Frontend env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_VERSION=/api/v1 (Derived from VITE_API_START and VITE_API_VERSION_ONLY)
VITE_API_START=api
VITE_API_VERSION_ONLY=v1
VITE_NODE_ENV=development
VITE_ENABLE_LOGGING=true
VITE_BASE_PATH=/kai
```

---

## 🧪 Local Development (Python venv / Conda)

You can use **venv** or **conda**. Below are both options.

### Option A — venv (recommended for simplicity)

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\\Scripts\\Activate.ps1

pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Option B — Conda

```bash
conda create -n kai-fusion python=3.11 -y
conda activate kai-fusion
pip install -r backend/requirements.txt
```

### Initialize the Database Schema

Ensure your Postgres container is running, then:

```bash
python backend/migrations/database_setup.py
```

### You can optionally run the project in a certified manner.

Before executing the commands below, enter your venv or conda environment. Then, while in the main directory of the project, execute the following two commands in order. After running these commands, you can proceed to the other steps.

```bash
cd backend/cert

$env:OPENSSL_CONF="C:\Program Files\Git\usr\ssl\openssl.cnf"; openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/C=TR/ST=Istanbul/L=Istanbul/O=KAI/OU=Dev/CN=localhost"
```


### Run the Backend

* **Via VS Code Debugger** (see next section), or
* **Directly**: `python backend/main.py`

### Run the Frontend

```bash
cd client
npm install
npm run dev
# Open the printed Vite URL (e.g. http://localhost:5173)
```

### Widget (Embeddable)
A standalone chat widget for embedding KAI-Fusion agents into other sites.

```bash
cd widget
npm install
npm run dev
```

---

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

> If you use the VS Code Python extension’s `envFile` feature instead, you can set `"envFile": "${workspaceFolder}/backend/.env"`.

---

## 🐳 Docker

### Docker Compose (recommended)

If your repo includes a `docker-compose.yml` at the root, simply run:

```bash
# Start Backend and Frontend
docker compose up -d
```

Then open the printed URLs:

* Frontend: e.g. [http://localhost:5173](http://localhost:5173) or [http://localhost:3000](http://localhost:3000)
* Backend: [http://localhost:8000](http://localhost:8000) (Swagger: `/docs`)

Stop containers:

```bash
docker compose stop
```

### Build & Run Images Manually

```bash
# Build the app image from the project root
docker build --no-cache -t kai-fusion:latest .

# Run (example for backend image; adjust ports/envs to your Dockerfile)
docker run -d --name kai-fusion \
  -p 8000:8000 \
  --env-file backend/.env \
  kai-fusion:latest
```

---

## 🧱 Project Structure

```
KAI-Fusion/
├─ backend/                 # FastAPI 0.116 Backend (Python 3.11)
│  ├─ app/
│  │  ├─ api/               # REST API endpoints
│  │  ├─ nodes/             # Workflow node definitions
│  │  │  ├─ agents/         # AI Agent nodes
│  │  │  ├─ llms/           # LLM provider nodes
│  │  │  ├─ tools/          # Tool nodes (web search, code, etc.)
│  │  │  ├─ memory/         # Memory/context nodes
│  │  │  ├─ embeddings/     # Embedding nodes
│  │  │  ├─ vector_stores/  # Vector store nodes
│  │  │  ├─ splitters/      # Text splitter nodes
│  │  │  ├─ triggers/       # Workflow trigger nodes
│  │  │  └─ document_loaders/
│  │  ├─ services/          # Business logic services
│  │  ├─ models/            # Database models
│  │  └─ core/              # Core utilities (graph builder, etc.)
│  ├─ migrations/           # DB setup scripts
│  ├─ main.py               # Application entrypoint
│  └─ requirements.txt      # Python dependencies
├─ client/                  # React 19.1 Frontend
│  ├─ app/
│  │  ├─ components/        # React components
│  │  │  ├─ canvas/         # Workflow canvas components
│  │  │  ├─ nodes/          # Node UI components
│  │  │  └─ modals/         # Configuration modals
│  │  ├─ routes/            # Page routes
│  │  ├─ services/          # API service layer
│  │  ├─ stores/            # Zustand state stores
│  │  └─ lib/               # Utilities
│  ├─ package.json          # React Router 7, Vite 6.3
│  └─ vite.config.ts
├─ widget/                  # Embeddable Chat Widget (@kaifusion/widget)
│  ├─ src/                  # Widget source
│  ├─ widget.js             # Pre-built widget bundle
│  └─ package.json          # v1.0.6
├─ docs/                    # Documentation
├─ docker-compose.yml       # Backend, Frontend, Widget services
└─ README.md
```

---

## ✨ App Overview (What you can build)

* **Visual Workflow Builder**: Drag-and-drop interface powered by XYFlow 12 for creating AI agents and chains.
* **Modern Tech Stack**: React 19.1, React Router 7, Vite 6.3, Tailwind 4.1, DaisyUI 5 (Frontend) + FastAPI 0.116, LangChain 0.3, LangGraph 0.6 (Backend).
* **AI/ML Framework**: Integrated LangChain, LangGraph, and LangSmith for building and debugging complex agent flows.
* **Vector Database**: PostgreSQL with pgvector for embedding storage and semantic search.
* **Node Types**: LLMs, Agents, Tools (Web Search, Code Execution), Memory, Embeddings, Vector Stores, Document Loaders, Text Splitters, Triggers.
* **Embeddable Widget**: Export your agents as an embeddable widget (`@kaifusion/widget` on npm).
* **Secure**: JWT-based authentication with Keycloak integration support.
* **Scheduling**: Built-in cron-based workflow scheduling with APScheduler.

---

## 📊 Repository Stats (⭐ Stars & ⬇️ Downloads)

### ⭐ Star History (auto‑updated)

[![Star History Chart](https://api.star-history.com/svg?repos=kafein-product-space/KAI-Fusion\&type=Date)](https://star-history.com/#kafein-product-space/KAI-Fusion)

### ⬇️ Downloads — Badges & Table

| Metric                   | Badge                                                                                                                                      |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **All releases (total)** | ![All Downloads](https://img.shields.io/github/downloads/kafein-product-space/KAI-Fusion/total?label=All%20downloads)                      |
| **Latest release**       | ![Latest Release Downloads](https://img.shields.io/github/downloads/kafein-product-space/KAI-Fusion/latest/total?label=Latest%20downloads) |
| **Stars (live)**         | ![GitHub Repo stars](https://img.shields.io/github/stars/kafein-product-space/KAI-Fusion?style=social)                                     |
| **Forks (live)**         | ![GitHub forks](https://img.shields.io/github/forks/kafein-product-space/KAI-Fusion?style=social)                                          |


## 🙌 Contributing (with user icons)

We welcome PRs! Please:

1. Open an issue describing the change/bug.
2. Fork → create a feature branch.
3. Add/adjust tests where applicable.
4. Open a PR with a clear description and screenshots/GIFs.

### 👥 Contributors 

<a href="https://github.com/kafein-product-space/KAI-Fusion/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=kafein-product-space/KAI-Fusion" alt="Contributors" />
</a>



### ⭐ Stargazers & 🍴 Forkers

[⭐ Stargazers repo roster for @kafein-product-space/KAI-Fusion](https://github.com/kafein-product-space/KAI-Fusion/stargazers) 

[🍴 Forkers repo roster for @kafein-product-space/KAI-Fusion](https://github.com/kafein-product-space/KAI-Fusion/network/members)


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

---

## 🤝 Code of Conduct

Please follow our [Contributor Covenant Code of Conduct](./CODE_OF_CONDUCT.md) to keep the community welcoming.

---

## 📝 License

Source code is available under the **Apache License 2.0** (see `LICENSE`).

---

### ℹ️ Repo Meta (auto‑generated by GitHub)

* Stars, watchers, forks: via badges above
* Contributors facepile: auto‑updated via contrib.rocks
* Star history: auto‑updated via star‑history.com