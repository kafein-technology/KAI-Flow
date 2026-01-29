# Contributing to KAI‑Fusion

We appreciate **any** form of contribution — from starring the repo to deep core changes. This guide explains the ways you can help and the workflow we use.

---

## ⭐ Star & Share

* Star the repository and share it with your network to help the project grow.

## 🙋 Q\&A

* Check the **Q\&A** in GitHub Discussions first. If you can’t find an answer, create a new post — others with the same question will benefit too.
* Discussions (placeholders):

  * Q\&A: `discussions/categories/q-a`
  * Ideas: `iscussions/categories/ideas`
  * Show & Tell: `discussions/categories/show-and-tell`

## 🙌 Share Workflows

* Sharing how you use KAI‑Fusion is a great contribution.
* Export your workflow as **JSON**, attach a screenshot/GIF, and post it in **Show & Tell**.

## 💡 Ideas

* Propose features (new nodes, app integrations, deployment targets), UX improvements, or performance ideas in **Ideas**.

## 🐞 Report Bugs

* Use **Issues** with a minimal repro (steps, expected vs. actual, logs, screenshots). Include versions and OS.

## 👨‍💻 Contribute to Code

Not sure where to start? Ideas:

* Create new **nodes/components** (tools, memory, retrievers, model adapters)
* Extend existing nodes (parameters, error‑handling, tests)
* Improve backend APIs (pagination, auth, tracing)
* Frontend UX (canvas interactions, node inspector, dark mode polish)

### Nodes

| NodeType   | Node Name                  |
| ---------- | ------------------------- |
| Provider   | OpenAINode                |
| Provider   | OpenAIEmbeddingsProvider  |
| Provider   | TavilySearchNode          |
| Provider   | RetrieverProvider         |
| Provider   | CohereRerankerNode        |
| Processor  | ReactAgentNode            |
| Processor  | CodeNode                  |
| Processor  | ConditionNode             |
| Processor  | StringInputNode           |
| Processor  | ChunkSplitterNode         |
| Processor  | HttpClientNode            |
| Processor  | WebScraperNode            |
| Processor  | DocumentLoaderNode        |
| Processor  | VectorStoreOrchestrator   |
| Terminator | StartNode                 |
| Terminator | EndNode                   |
| Terminator | WebhookTriggerNode        |
| Terminator | TimerStartNode            |
| Memory     | ConversationMemoryNode    |
| Memory     | BufferMemoryNode          |

#### 1. PROVIDER (Factory Pattern)

**Purpose:** Creates and configures LangChain objects from user inputs.

**Features:**
- No dependency on other nodes
- Pure configuration-to-object transformation
- Stateless operation
- High reusability across workflows

**Examples:** OpenAINode, TavilySearchNode, OpenAIEmbeddingsProvider, BaseRetriever

**Output Type:** LangChain objects (Runnable, BaseTool, BaseRetriever)

#### 2. PROCESSOR (Orchestrator Pattern)

**Purpose:** Combines and orchestrates multiple LangChain objects.

**Features:**
- Multi-input dependency management
- Complex business logic orchestration
- Stateful operation with memory
- Context-aware processing

**Examples:** ReactAgentNode, CodeNode, ConditionNode, StartNode

**Input Source:** Connected nodes + user configuration

**Output Type:** Composed Runnable or execution results

#### 3. TERMINATOR (Transformer Pattern)

**Purpose:** Transforms, formats, or terminates workflow outputs.

**Features:**
- Single input focused (previous node output)
- Output formatting and transformation
- Result validation and sanitization
- Chain termination logic

**Examples:** EndNode, WebhookTriggerNode, TimerStartNode

**Input Source:** Previous node output + formatting rules

**Output Type:** Formatted/transformed final results

#### 4. MEMORY (Persistence Pattern)

**Purpose:** Manages conversation state and context persistence.

**Features:**
- Session-aware state management
- Conversation history persistence
- Context injection capabilities
- Multi-turn conversation support

**Examples:** ConversationMemoryNode, BufferMemoryNode

**Input Source:** Session context + conversation state

**Output Type:** Conversation-stateful memory objects

---

## 👩‍ Developers

KAI‑Fusion is a dual‑stack app:

* **backend/** — Python **FastAPI** serving REST APIs, tracing hooks, and persistence
* **client/** — **React (Vite)** visual builder and runtime UI
* **postgres** — workflow/run storage

### Prerequisites

* **Python** = 3.11
* **Node.js** ≥ 18.15 (Vite)
* **Docker** & **Docker Compose**

---

## 🛠️ Step‑by‑Step Dev Setup

### 1) Fork & Clone

```bash
git clone https://github.com/<your-username>/REPO.git
cd REPO
git remote add upstream https://github.com/OWNER/REPO.git
```

### 2) Create a Branch

Use Conventional Names:

* Feature: `feature/<short-title>`
* Fix: `bugfix/<short-title>`

```bash
git checkout -b feature/canvas-zoom
```

### 3) Start PostgreSQL (Docker)

```bash
docker run --name kai \
  -e POSTGRES_DB=kai \
  -e POSTGRES_USER=kai \
  -e POSTGRES_PASSWORD=kai \
  -p 5432:5432 -d postgres:15
```

> Replace the default `kai` credentials for your local security if you like.

### 4) Environment Files

Create three `.env` files:

* `backend/migrations/.env`
* `backend/.env`
* `client/.env`

> **Copy exact keys/values from [README](./README.md).** Make sure `CREATE_DATABASE=true` in **migrations** env and `false` in **backend** env.

### 5) Python Environment & Backend Deps

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 6) Initialize Database Schema

```bash
python backend/migrations/database_setup.py
```

### 7) Frontend Deps

```bash
cd client
npm install
cd ..
```

### 8) Run the App

* **Backend**: `python backend/app.py`
  (or use VS Code debug config in `.vscode/launch.json`)
* **Frontend**: `cd client && npm run dev`

Open the loggered Vite URL (e.g. `http://localhost:5173`). Backend runs at `http://localhost:8000` (Swagger at `/docs`).

### 9) Docker Compose (Optional)

If your repo includes `docker-compose.yml` at root:

```bash
docker compose up -d
```

---

## 🧪 Tests & Quality

* **Backend**: `pytest` (add tests under `backend/tests/`)
* **Frontend**: if present, run `npm test`
* **Linters/Formatters** (if configured):

  * Python: `black`, `isort`, `flake8`
  * JS/TS: `eslint`, `prettier`

### Commit Conventions

Use **Conventional Commits**:

* `feat: add retriever node`
* `fix: prevent null pointer on run stop`
* `docs: update README quick start`
* `chore: bump deps`

### Pull Request Checklist

* [ ] Linked issue (if any) & clear description
* [ ] Screenshots/GIFs for UI changes
* [ ] Tests updated/added where reasonable
* [ ] `README`/docs updated if behavior changed

---

## 🌱 Env Variables (quick reference)

> Full list and explanations live in [README](./README.md). Here’s a quick view:

| Key                    | Where                                          | Example                                           |
| ---------------------- | ---------------------------------------------- | ------------------------------------------------- |
| `ASYNC_DATABASE_URL`   | backend/migrations, backend                    | `postgresql+asyncpg://kai:kai@localhost:5432/kai` |
| `DATABASE_URL`         | backend/migrations, backend                    | `postgresql://kai:kai@localhost:5432/kai`         |
| `CREATE_DATABASE`      | backend/migrations (`true`), backend (`false`) | `true` / `false`                                  |
| `LANGCHAIN_TRACING_V2` | backend                                        | `true`                                            |
| `LANGCHAIN_API_KEY`    | backend                                        | `your_langchain_api_key`                          |
| `VITE_API_BASE_URL`    | client                                         | `http://localhost:8000`                           |

You can also pass envs to Docker via `--env-file backend/.env`.

---

## 📖 Contribute to Docs

* Improve **README**, add **tutorials**, or write **how‑tos** in `/docs/`.
* Add GIFs/screenshots to `docs/media/`.

## 🏷️ PR Process

* Opening a PR automatically notifies maintainers. You can also ping us in **Discord**.

## 📜 Code of Conduct

By participating, you agree to our [Code of Conduct](./CODE_OF_CONDUCT.md). Report unacceptable behavior to **[contact@example.com](mailto:contact@example.com)** (replace with your email).

---

## 📎 Footer — Project Directory & Stats (Optional)

> Replace `OWNER/REPO` with your actual repo path.

### About

**KAI‑Fusion** — Build AI Agents, Visually

### Resources

* [README](./README.md) · [Code of Conduct](./CODE_OF_CONDUCT.md) 

### Topics

`react` · `javascript` · `typescript` · `python` · `fastapi` · `postgresql` · `chatbot` · `artificial‑intelligence` · `openai` · `multiagent-systems` · `agents` · `workflow-automation` · `low-code` · `no-code` · `rag` · `large-language-models` · `langchain` · `agentic-workflow` · `agentic-ai`

### GitHub Statistics

* Stars: ![Stars](https://img.shields.io/github/stars/OWNER/REPO?style=social)
* Watchers: ![Watchers](https://img.shields.io/github/watchers/OWNER/REPO?style=social)
* Forks: ![Forks](https://img.shields.io/github/forks/OWNER/REPO?style=social)
* Star history: [![Star History](https://api.star-history.com/svg?repos=OWNER/REPO\&type=Date)](https://star-history.com/#OWNER/REPO)
* Contributors: <a href="https://github.com/OWNER/REPO/graphs/contributors"><img src="https://contrib.rocks/image?repo=OWNER/REPO" alt="Contributors" /></a>

### Releases & Downloads

* Latest: ![Latest tag](https://img.shields.io/github/v/release/OWNER/REPO)
* Downloads (all): ![All Downloads](https://img.shields.io/github/downloads/OWNER/REPO/total)
* Downloads (latest): ![Latest Downloads](https://img.shields.io/github/downloads/OWNER/REPO/latest/total)

### Deployments (optional)

* Add your environments via badges or a short note here.

---

> © KAI‑Fusion contributors. 
