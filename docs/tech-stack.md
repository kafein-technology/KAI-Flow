# Tech Stack

_A field marked **Repos:** applies only to those repositories; a field without the line is project-wide._

## Frontend

### Selection

**Repos:** KAI-Flow

React 19 SPA (TypeScript, Vite 8, React Router 7, zustand, TanStack Query, @xyflow/react, Tailwind CSS 4 + daisyUI 5); widget: React library + IIFE bundle on Vite 6

_client/package.json pins react 19.2.8, react-router 7.18.3, vite 8.2.2, zustand 5.0.15, @tanstack/react-query 5.102.8, @xyflow/react 12.11.6, axios 1.20.0, tailwindcss 4.3.3, daisyui 5.7.27, monaco editor, recharts, keycloak-js / react-oidc-context. widget/package.json publishes @kaifusion/widget 1.1.0 (peer React 18 or 19) with a library build and a standalone build._

## Backend

### Selection

**Repos:** KAI-Flow

Python 3.11, FastAPI 0.141 on uvicorn, SQLAlchemy 2 (async, asyncpg), Pydantic 2, LangChain 1.3 + LangGraph 1.2

_backend/requirements.txt is fully pinned for Python 3.11 (fastapi 0.141.1, uvicorn 0.52.4, sqlalchemy 2.0.52, asyncpg 0.31.0, pydantic 2.13.5, langchain 1.3.18, langgraph 1.2.11). Dockerfile builds FROM python:3.11 and runs uvicorn main:app. Node library adds OpenAI, Cohere, Tavily, scrapling/playwright, modelaudit, fickling, deepteam/deepeval, confluent-kafka, APScheduler/croniter._

## Database

### Selection

**Repos:** KAI-Flow

PostgreSQL 15

_docker-compose.yml runs postgres:15-alpine; README local setup uses postgres:15; CI service container is postgres:15-alpine. Vector-store nodes use langchain-postgres PGVector against a user-supplied connection string or credential. MySQL, MongoDB and SQLite appear only as workflow node targets, not as platform storage._

## Auth / Identity

### Selection

**Repos:** KAI-Flow

Built-in email/password with JWT (HS256) + optional Keycloak OIDC (RS256, JIT provisioning) + MASTER_API_KEY

_core/security.py hashes passwords with pwdlib (Argon2 primary, bcrypt verify) and issues HS256 access (30 min) and refresh (7 days) tokens; verify_token also validates Keycloak RS256 tokens via JWKS. auth/dependencies.py JIT-creates a local user for an unknown Keycloak subject and accepts MASTER_API_KEY via X-API-Key or Bearer on selected endpoints. Client wires react-oidc-context when Keycloak authority and client id are configured. Per-user API keys are created and stored hashed (api_keys) but not yet accepted for authentication; the chosen target is recorded in architecture › Security Checklist › Per-user API keys._

## Infrastructure / Deployment

### Selection

**Repos:** KAI-Flow

Docker images (backend, frontend) + Docker Compose reference deployment; multi-arch images published to Docker Hub

_docker-compose.yml defines db, kai-flow-backend (port 23056 to 8000, runs migrations/database_setup.py then uvicorn) and kai-flow-frontend (port 23058 to 3000, static build served by serve). Images are built for linux/amd64 and linux/arm64. The production hosting platform that runs these images is not described in the repository. A single backend container is the supported deployment boundary (architecture › Cache Strategy › Shared state across backend instances)._

## Storage / Object Store

### Selection

**Repos:** KAI-Flow

Persistent filesystem volume for managed model artifacts and scan staging + MinIO (S3-compatible, boto3) and read-only mounted model roots as scan sources

_docker-compose.yml mounts kai_model_artifacts and kai_model_scan_staging volumes and KAI_MODEL_LOCAL_ALLOWED_ROOTS defaults to /models. services/minio_service.py uses boto3. Browser uploads are capped at 8 GiB; local/MinIO artifacts at 256 GiB by default._

## Queue / Async Messaging

### Selection

**Repos:** KAI-Flow

No message broker for platform jobs (in-process asyncio tasks and an in-memory execution queue); Kafka via confluent-kafka only as a workflow trigger and producer node

_main.py lifespan starts the model-artifact maintenance loop and the Kafka reconciliation loop as asyncio tasks. core/execution_queue.py keeps running and pending executions in process memory keyed by workflow and user. nodes/triggers/kafka_trigger.py and nodes/processing/kafka_producer.py use confluent-kafka 2.15. This process-local design relies on the single-backend-instance boundary (architecture › Cache Strategy › Shared state across backend instances)._

## Observability

### Selection

**Repos:** KAI-Flow

Built-in enhanced logging (stdout, optional daily-rotated files, development-only live log stream) + optional LangSmith tracing + workflow tracing flags

_core/enhanced_logging.py keeps an in-memory log history streamed by GET /api/v1/logs/stream only when ENVIRONMENT=development. KAI_FLOW_FILE_LOGGING writes application.log, workflow.log, workflow_errors.log with 30 daily archives. LANGCHAIN_TRACING_V2 enables LangSmith. Request, database-query and security logging middleware are registered in main.py._

## CI/CD

### Selection

**Repos:** KAI-Flow

GitHub Actions (backend-ci, frontend-ci, deploy on v* tags) + Docker Hub + Trivy + Codecov

_backend-ci runs ruff, mypy, pytest with a postgres:15 service, Trivy fs scan on push, and pushes the backend image on main. frontend-ci runs eslint, tsc, vitest coverage and vite build on Node 22 and pushes the frontend image on main. deploy.yml builds both images on v* tags or manual dispatch and creates a GitHub release. All lint, type and test steps use continue-on-error today; the chosen merge gate (qa › CI/CD Integration › Merge gate) makes them blocking and is not yet implemented._

## Email / Notification

### Selection

**Repos:** KAI-Flow

No platform email service; Gmail workflow node (Google APIs) for workflow email; notistack for in-app notifications

_No transactional email provider appears in requirements or services; nodes/processing/gmail_node.py uses google-api-python-client. client uses notistack snackbars._

## Summary (TL;DR)

### Stack summary

**Repos:** KAI-Flow

| Layer | Selection | Version | Repo |
| --- | --- | --- | --- |
| Frontend (web client) | React + Vite + React Router + zustand + @xyflow/react + Tailwind/daisyUI | React 19.2, Vite 8.2, Tailwind 4.3 | KAI-Flow |
| Frontend (chat widget) | React library + IIFE bundle | @kaifusion/widget 1.1.0, Vite 6 | KAI-Flow |
| Backend | FastAPI + SQLAlchemy async + LangChain/LangGraph | Python 3.11, FastAPI 0.141, LangGraph 1.2 | KAI-Flow |
| Database | PostgreSQL | 15 | KAI-Flow |
| Auth / Identity | Local JWT + optional Keycloak OIDC + master API key | PyJWT 2.15, keycloak-js 26 | KAI-Flow |
| Infrastructure / Deployment | Docker images + Docker Compose | python:3.11, node:22-alpine | KAI-Flow |
| Storage / Object Store | Persistent volume + MinIO (S3 API) + read-only model mounts | boto3 1.43 | KAI-Flow |
| Queue / Async Messaging | In-process asyncio; Kafka as workflow integration | confluent-kafka 2.15 | KAI-Flow |
| Observability | Enhanced logging + optional LangSmith | langsmith 0.12 | KAI-Flow |
| CI/CD | GitHub Actions + Docker Hub + Trivy + Codecov | - | KAI-Flow |
| Email / Notification | Gmail workflow node; notistack in UI | google-api-python-client 2.200 | KAI-Flow |

_Derived from the per-category selections above; versions from backend/requirements.txt, client/package.json and widget/package.json._
