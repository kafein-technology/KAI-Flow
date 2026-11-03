# Architecture

_A field marked **Repos:** applies only to those repositories; a field without the line is project-wide._

## TL;DR

### TL;DR

**Repos:** KAI-Flow

Three deliverables in one repository: a React SPA (client), an embeddable React chat widget (widget) and a single FastAPI backend.
The backend stores workflows as JSON in PostgreSQL 15, compiles them into LangGraph graphs at run time and streams results over SSE.
No external cache or broker: execution queue, canvas sessions, Kafka listeners and LangGraph checkpoints live in backend process memory; a single backend instance is therefore the supported deployment boundary (Cache Strategy › Shared state across backend instances).
Auth is local JWT (HS256) with optional Keycloak OIDC (RS256) and a single MASTER_API_KEY for automation. Chosen, not yet implemented: per-user API keys as identity for workflow execution and widget calls, session auth on all management endpoints, and an environment-driven CORS allow-list (see Security Checklist).
Triggers: webhook (test and production endpoints), timer/cron, Kafka consumer, error workflow.

_Summarised from main.py router wiring and lifespan tasks, core/checkpointer.py, core/execution_queue.py and docker-compose.yml; target rules from the user's Blueprint corrections._

## System Flow Diagram

### Flow: Sign-in and session refresh (F-AUTH)

**Repos:** KAI-Flow

1. User opens /signin (or /register when ENTERPRISE=false).
2. Local: POST /api/v1/auth/signin returns user + access token (30 min) + refresh token (7 days); tokens are stored in localStorage.
3. Keycloak (when configured): react-oidc-context signs the user in; AuthSynchronizer copies the OIDC token into the client token store; the backend validates RS256 via JWKS and JIT-creates a local user on first call.
4. api-client.ts attaches Bearer tokens; on 401 it queues requests, calls POST /api/v1/auth/refresh and retries with the new token.
5. Sign-out clears local tokens; POST /api/v1/auth/signout does not revoke tokens server-side.

_client/app/lib/api-client.ts TokenManager and interceptors; api/auth.py signin, refresh, signout; auth/dependencies.py get_current_user JIT provisioning._

### Flow: Build and save a workflow, optionally with the AI builder (F-BUILD)

**Repos:** KAI-Flow

1. User opens /canvas (optionally ?workflow=<id>); the client loads the node catalogue from GET /api/v1/nodes.
2. User drags nodes, connects handles and edits node fields (Monaco editor for code fields).
3. Save: POST /api/v1/workflows (new) or PUT /api/v1/workflows/{id}; flow_data is stored as JSONB; POST /api/v1/workflows/validate checks the graph.
4. AI builder: POST /api/v1/ai-builder/generate with a prompt and an LLM credential; the orchestrator produces a skeleton, parameterizes it, validates, diffs and auto-lays out the result.

_api/workflows.py CRUD + validate; api/ai_builder.py GenerateRequest (credential_id, model_name default gpt-4o); services/ai_builder modules._

### Flow: Run a workflow and chat with it (F-RUN)

**Repos:** KAI-Flow

1. Canvas run or chat message sends POST /api/v1/workflows/execute with flow_data and/or workflow_id, session_id/chatflow_id (Accept: text/event-stream).
2. Backend checks ownership (owner or public), acquires a per workflow+user slot in the in-memory execution queue and creates a workflow_executions row.
3. graph_builder compiles flow_data into a LangGraph graph; nodes execute and node events stream back over SSE.
4. Chat messages are stored in chat_message; buffer memory uses the session id.
5. Execution completes or fails; status, outputs and error are written; the user can cancel via POST /api/v1/executions/{id}/cancel and review runs on /executions.

_api/workflows.py execute_adhoc_workflow; core/execution_queue.py; client/app/services/executionService.ts uses text/event-stream; client/app/lib/useSSE.ts._

### Flow: Error workflow on failure (F-ERROR)

**Repos:** KAI-Flow

1. User links an error workflow to a workflow (workflows.error_workflow, set from the error-workflow modal).
2. A run of the main workflow fails.
3. The backend starts the linked workflow through its error trigger node with the failure details.
4. The canvas listens on GET /api/v1/workflows/error-trigger/{workflow_id}/stream for live error-trigger events.

_models/workflow.py error_workflow self-FK (SET NULL); nodes/triggers/error_trigger.py; api/workflows.py error-trigger stream; client modals include an error-workflow dialog._

### Flow: Webhook-triggered run (F-WEBHOOK)

**Repos:** KAI-Flow

1. A webhook trigger node registers a webhook_endpoints row with a webhook_id, path and secret token.
2. External caller hits /api/v1/webhook-test/{id} (test, streams to the canvas) or /api/v1/webhook/{id} (production), any of GET/POST/PUT/PATCH/DELETE; or POST /api/v1/webhooks/trigger/{id}.
3. Backend enforces the node's authentication (none, basic_auth or header_auth via a stored credential) and per-endpoint rate_limit_per_minute (default 60).
4. The request is logged in webhook_events and the workflow is executed through POST /api/v1/workflows/execute with X-Internal-Call.
5. A Respond to Webhook node can shape the HTTP response.

_nodes/triggers/webhook_trigger.py routers and auth validation; api/webhooks.py trigger_router and internal execute call; models/webhook.py. Today api/workflows.py trusts X-Internal-Call from any caller; under Security Checklist › Unauthenticated management endpoints, the system-user switch is allowed only for this server-internal call._

### Flow: Scheduled run (F-TIMER)

**Repos:** KAI-Flow

1. A Timer Start node defines cron, interval or delay with a timezone (default UTC) and an optional max execution count.
2. scheduled_jobs stores the schedule; next_run_at is computed with croniter.
3. User starts, stops or triggers via /api/v1/timers/{id}/start|stop|trigger and watches /api/v1/timers/{id}/stream.
4. Each run is recorded in job_executions and linked to a workflow execution.

_models/scheduled_job.py; services/scheduled_job_service.py; api/timers.py; nodes/triggers/timer_start_node.py._

### Flow: Kafka-triggered run (F-KAFKA)

**Repos:** KAI-Flow

1. A Kafka Trigger node holds broker, topic and consumer settings.
2. KafkaListenerService starts a confluent-kafka consumer per listener inside the backend process.
3. Each consumed message executes the workflow; the canvas can watch /api/v1/kafka/listeners/{id}/stream and stop via /api/v1/kafka/listeners/{id}/stop.
4. kafka_reconciliation_loop periodically synchronises listeners; on shutdown all running listeners are stopped.

_nodes/triggers/kafka_trigger.py kafka_router and reconciliation loop; main.py lifespan._

### Flow: Embedded widget chat (F-WIDGET)

**Repos:** KAI-Flow

1. Host site embeds the widget as a React component or a script tag with data-workflow-id, data-target-url, data-auth-token, data-title, data-position, data-color; script assets are served by the backend at /widget.
2. Widget validates the token with GET /api/v1/auth/me.
3. Each message calls POST /api/v1/workflows/execute with Authorization Bearer and X-API-Key set to the same token and reads the SSE stream.
Chosen target, not yet implemented: the token is the site owner's per-user API key (never MASTER_API_KEY), reaching only that user's workflows, and the host site's origin is on the CORS allow-list.

_widget/src/embed.tsx, widget/src/KaiChatWidget.tsx; main.py mounts /widget StaticFiles. Target from Security Checklist › Per-user API keys and › Browser origin policy (CORS)._

### Flow: Credential management (F-CRED)

**Repos:** KAI-Flow

1. User opens /credentials, picks a service from the catalogue and fills a dynamic form.
2. POST /api/v1/credentials stores the secret Fernet-encrypted in user_credentials.encrypted_secret.
3. POST /api/v1/credentials/{id}/test or /test-raw checks connectivity; /list-models and /{id}/models list provider models.
4. Nodes reference credentials by id; GET /api/v1/credentials/{id}/workflows shows where a credential is used.

_api/credentials.py routes; core/encryption.py CredentialEncryption; models/user_credential.py._

### Flow: Model artifact upload and security scan (F-MODELSCAN)

**Repos:** KAI-Flow

1. Client reads limits from GET /api/v1/model-artifacts/capabilities and /status.
2. Upload via POST /api/v1/model-artifacts/upload or /upload-directory (browser, max 8 GiB) streams to the artifact volume; or a node points at a read-only local root or MinIO object.
3. The model scanner node runs modelaudit and fickling in a separate process (forkserver or spawn) with a memory limit (default 4 GiB).
4. A lease protects an artifact during scanning; the maintenance loop (every 900 s) expires uploads, recovers stale leases and enforces disk-pressure thresholds (75/85/90 percent).

_api/model_artifacts.py; services/model_artifact_store.py, model_scan_process.py, model_artifact_maintenance.py; docker-compose.yml KAI_MODEL_* settings._

### Flow: Export a workflow bundle (F-EXPORT)

**Repos:** KAI-Flow

1. User opens the export modal on a workflow.
2. POST /api/v1/export/workflows builds a bundle with the workflow and its required configuration.
3. backend/scripts import the bundle into another deployment (see export-docker/import_bundle).

_api/export.py; backend/scripts export/import; export-docker/import_bundle README._

## Service Topology

### Services

**Repos:** KAI-Flow

- Web client (client/) - React SPA for canvas, executions, credentials, variables, marketplace; served as static files by serve on port 3000
- Chat widget (widget/) - embeddable React chat window; npm package @kaifusion/widget and IIFE bundle served from backend /widget
- Backend API and workflow engine (backend/) - FastAPI on uvicorn port 8000: REST + SSE API, LangGraph execution, triggers (webhook, timer, Kafka), credential encryption, model scanning, background maintenance loops
- Application database - PostgreSQL 15
- Model artifact store - persistent volumes /data/model-artifacts and /data/model-scan-staging
- External (optional) - Keycloak (OIDC), OpenAI / OpenAI-compatible LLMs, Cohere, Tavily, Kafka brokers, MinIO, Google APIs (Gmail, Sheets), LangSmith, user databases (PostgreSQL/pgvector, MySQL, MongoDB, SQLite)

_Matches the owned C2 parts in the decision context and main.py/docker-compose.yml wiring._

### Database tables

**Repos:** KAI-Flow

- users - accounts (email, password hash, role, status)
- organization, roles, organization_user, login_method, login_activity - organisation and login scaffolding
- api_keys - hashed per-user API keys
- workflows, workflow_templates - workflow definitions (flow_data JSONB) and templates
- workflow_executions, execution_checkpoints - run records and checkpoint snapshots
- node_configurations, node_registry - per-workflow node configs and registered node types
- user_credentials, variable - encrypted secrets and user/workflow variables
- chat_message, memories - chat history and conversation memory
- document_collections, documents, document_chunks, document_access_logs, document_versions - document store
- vector_collections, vector_documents - per-workflow vector collections
- webhook_endpoints, webhook_events - webhook registrations and request log
- scheduled_jobs, job_executions - timers and their runs
- external_workflows - registered remote workflows
- managed_model_artifacts, managed_model_artifact_leases - uploaded model files and scan leases

___tablename__ values in backend/app/models; tables are created and column-synced by migrations/database_setup.py._

### Connection diagram

**Repos:** KAI-Flow

```
+-------------+       REST + SSE        +---------------------------+
| Web client  | ----------------------> |                           |
| (React SPA) |                         |  Backend API + engine     |
+-------------+                         |  FastAPI / LangGraph      |
+-------------+  /widget assets, SSE    |                           |
| Chat widget | ----------------------> |  - triggers: webhook,     |
| (host site) |                         |    timer, Kafka, error    |
+-------------+                         |  - in-memory queue,       |
+-------------+  webhook HTTP           |    checkpoints, sessions  |
| External    | ----------------------> |                           |
| callers     |                         +---------------------------+
+-------------+                            |      |        |      |
                       SQL (asyncpg) <-----+      |        |      +----> Keycloak (JWKS)
                     +--------------+            |        |
                     | PostgreSQL 15|            |        +----> LLM / search APIs,
                     +--------------+            |               Kafka, MinIO, Google,
                     +------------------------+  |               user databases
                     | Model artifact volume  |<-+
                     +------------------------+
```

_Derived from client/app/lib/api-client.ts, widget/src/KaiChatWidget.tsx, main.py routers and lifespan, docker-compose.yml volumes._

## Database Design

### users table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | email UNIQUE | PostgreSQL table | full_name, password_hash, role, credential, temp_token, token_expiry, status, active_workspace_id, last_login, created_at, updated_at |

_Relational adaptation of the template: PK = primary key, SK = unique/foreign keys, Type = storage object. Source models/user.py._

### organization, roles, organization_user tables

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| organization.id (UUID) | admin_user_id FK users | PostgreSQL table | name, default_ws_id, organization_type, created_at, updated_at |
| roles.id (UUID) | - | PostgreSQL table | name, description, permissions (text) |
| organization_user (organization_id, user_id) | role_id FK roles; created_by/updated_by FK users | PostgreSQL table | status (default ACTIVE), timestamps |

_models/organization.py. No API router for organizations was observed in main.py._

### login_method, login_activity tables

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| login_method.id (UUID) | organization_id FK organization | PostgreSQL table | name, config (text), status (default ENABLE), created_by, updated_by |
| login_activity.id (UUID) | - | PostgreSQL table | username, activity_code, message, attempted_at |

_models/auth.py. Signin in api/auth.py does not write login_activity (observed)._

### api_keys table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | hashed_key UNIQUE; user_id FK users | PostgreSQL table | key_name, created_at, last_used_at |

_models/api_key.py; services/api_key_service.py._

### workflows table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | user_id FK users (CASCADE); error_workflow FK workflows (SET NULL) | PostgreSQL table | name, description, category, is_public, version, flow_data JSONB, created_at, updated_at |

_models/workflow.py._

### workflow_templates table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | - | PostgreSQL table | name, description, category (default General), flow_data JSONB, created_at |

_models/workflow.py WorkflowTemplate. The marketplace page also ships six static template JSON files in client/app/data/templates._

### workflow_executions table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | workflow_id FK workflows (CASCADE); user_id FK users (CASCADE) | PostgreSQL table | status (default pending), inputs JSONB, outputs JSONB, error_message, started_at, completed_at, created_at |

_models/execution.py WorkflowExecution._

### execution_checkpoints table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| execution_id (UUID) FK workflow_executions (CASCADE) | - | PostgreSQL table | checkpoint_data JSONB, parent_checkpoint_id, updated_at |

_models/execution.py ExecutionCheckpoint. LangGraph checkpointing itself is created by core/checkpointer.py, which falls back to in-memory MemorySaver when PostgresSaver cannot be imported._

### node_configurations table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID, gen_random_uuid) | workflow_id FK workflows (CASCADE) | PostgreSQL table | node_id, node_type, configuration JSON, position JSON, created_at, updated_at |

_models/node_configuration.py._

### node_registry table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | node_type UNIQUE | PostgreSQL table | node_class, category, version (default 1.0.0), schema_definition JSON, ui_schema JSON, is_active, created_at |

_models/node_registry.py. Runtime discovery is code-based (core/node_discovery.py, node_registry.discover_nodes at startup)._

### user_credentials table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | user_id FK users (CASCADE) | PostgreSQL table | name, service_type, encrypted_secret (Fernet), created_at, updated_at |

_models/user_credential.py; core/encryption.py._

### variable table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | user_id FK users (CASCADE); workflow_id FK workflows (CASCADE, nullable) | PostgreSQL table | name, value, type, createdDate, updatedDate |

_models/variable.py (timestamp columns are named createdDate/updatedDate)._

### chat_message table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | user_id FK users (CASCADE); workflow_id FK workflows (CASCADE, nullable) | PostgreSQL table | role, chatflow_id (indexed), content, source_documents, created_at |

_models/chat.py._

### memories table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | user_id FK users (nullable); session_id indexed | PostgreSQL table | content, context, memory_metadata JSON, source_type (chat, webhook, api), chatflow_id, created_at, updated_at |

_models/memory.py; services/memory._

### document tables

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| document_collections.id (UUID) | user_id FK users (CASCADE) | PostgreSQL table | name, description, doc_metadata JSONB, is_active, timestamps |
| documents.id (UUID) | user_id FK users; collection_id FK document_collections (CASCADE) | PostgreSQL table | title, content, document_format, source_url, file_path, source_type, content_hash (SHA-256), quality_score, processing_status, tags[], is_public, version, is_archived, timestamps |
| document_chunks.id (UUID) | document_id FK documents; user_id FK users | PostgreSQL table | content, chunk_index, splitter_strategy, chunk_size_config, chunk_overlap_config, embedding_model, embedding_vector float[], timestamps |
| document_access_logs.id (UUID) | document_id FK documents; user_id FK users | PostgreSQL table | access_type, access_method, session_id, workflow_id, node_id, access_timestamp |
| document_versions.id (UUID) | document_id FK documents; user_id FK users | PostgreSQL table | version_number, change_type, content_snapshot, metadata_snapshot, changed_fields[], created_at |

_models/document.py._

### vector tables

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| vector_collections.id (UUID) | workflow_id FK workflows (CASCADE); UNIQUE (workflow_id, collection_name) | PostgreSQL table | collection_name, embedding_dimension, distance_strategy (cosine), index_type (ivfflat), index_params JSONB, document_count |
| vector_documents.id (UUID) | collection_id FK vector_collections (CASCADE) | PostgreSQL table | content, document_metadata JSONB, embedding (string), source_url, source_type, chunk_index, created_at |

_models/vector_collection.py, models/vector_document.py. Vector-store workflow nodes write to langchain-postgres PGVector tables in the user-supplied database instead._

### webhook tables

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| webhook_endpoints.id (UUID) | webhook_id UNIQUE; workflow_id FK workflows (CASCADE) | PostgreSQL table | node_id, endpoint_path, secret_token, config JSONB, is_active, node_behavior (auto, start_only, trigger_only), last_triggered, trigger_count, avg_response_time_ms, error_count |
| webhook_events.id (UUID) | webhook_id FK webhook_endpoints.webhook_id | PostgreSQL table | event_type, payload JSONB, correlation_id, source_ip INET, user_agent, request_method, request_headers, response_status, response_body, execution_time_ms, error_message, created_at |

_models/webhook.py._

### scheduled job tables

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| scheduled_jobs.id (UUID) | workflow_id FK workflows (CASCADE) | PostgreSQL table | node_id, job_name, timer_type, cron_expression, interval_seconds, delay_seconds, timezone (UTC), max_executions, current_executions, is_enabled, next_run_at, last_run_at |
| job_executions.id (UUID) | job_id FK scheduled_jobs (CASCADE) | PostgreSQL table | execution_id, started_at, completed_at, status, result JSONB, error_message, execution_time_ms |

_models/scheduled_job.py._

### external_workflows table

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| id (UUID) | user_id FK users | PostgreSQL table | name, description, host, port, is_secure, api_key (stored as plain string), api_key_required, external_workflow_id, external_url, workflow_structure JSON, capabilities JSON, status, last_health_check, last_error, is_active |

_models/external_workflow.py; the api_key column comment states 'Encrypted in real implementation'._

### model artifact tables

**Repos:** KAI-Flow

| PK | SK | Type | Attributes |
| --- | --- | --- | --- |
| managed_model_artifacts.id (UUID) | storage_key UNIQUE; owner_key indexed | PostgreSQL table | storage_backend (filesystem), name, size_bytes, sha256, format_hint, source_kind, source_file_count, workflow_id, node_id, state (uploading...), scan_count, last_accessed_at, last_scanned_at, expires_at, last_error |
| managed_model_artifact_leases.id (UUID) | artifact_id FK managed_model_artifacts (CASCADE) | PostgreSQL table | acquired_at, expires_at |

_models/model_artifact.py; services/model_artifact_store.py._

### GSIs

**Repos:** KAI-Flow

| GSI name | PK | SK | Purpose |
| --- | --- | --- | --- |
| idx_workflows_user_created | user_id | created_at | List a user's workflows by date |
| idx_workflows_public_created | is_public | created_at | List public workflows (marketplace) |
| idx_workflows_user_public | user_id | is_public | Filter a user's workflows by visibility |
| idx_vector_collections_workflow | workflow_id | - | Collections of a workflow |
| idx_vector_collections_name | collection_name | - | Collection lookup by name |
| idx_vector_documents_collection | collection_id | - | Documents of a collection |
| idx_vector_documents_metadata (GIN) | document_metadata | - | Metadata filtering |
| idx_webhook_workflow / _active / _behavior / _created | workflow_id / is_active / node_behavior / created_at | - | Webhook endpoint lookups |
| idx_webhook_logs_webhook / _created / _status / _type / _correlation | webhook_id / created_at / response_status / event_type / correlation_id | - | Webhook event log queries |

_PostgreSQL secondary indexes (the template's GSI column maps to index name, PK/SK to leading/second column). Single-column index=True also exists on users.email, chat_message (user_id, workflow_id, chatflow_id, created_at), document tables, memories.session_id, managed_model_artifacts (owner_key, workflow_id, state, expires_at)._

### TTL

**Repos:** KAI-Flow

| Type | Duration | Field |
| --- | --- | --- |
| Access token | 30 min | JWT exp (ACCESS_TOKEN_EXPIRE_MINUTES) |
| Refresh token | 7 days | JWT exp (REFRESH_TOKEN_EXPIRE_DAYS) |
| Managed model upload | 86400 s | managed_model_artifacts.expires_at (KAI_MODEL_MANAGED_RETENTION_SECONDS) |
| Model upload after scan | 3600 s | KAI_MODEL_MANAGED_POST_SCAN_RETENTION_SECONDS |
| Incomplete upload | 3600 s | KAI_MODEL_INCOMPLETE_RETENTION_SECONDS |
| Scan staging files | 7200 s | KAI_MODEL_STAGING_RETENTION_SECONDS |
| Upload reservation | 7200 s | KAI_MODEL_UPLOAD_RESERVATION_SECONDS |
| Scan lease | until lease expiry | managed_model_artifact_leases.expires_at |
| Artifact GC interval | 900 s | KAI_MODEL_ARTIFACT_GC_INTERVAL_SECONDS |

_core/constants.py token lifetimes; docker-compose.yml KAI_MODEL_* defaults; cleanup performed by the maintenance loop, not database TTL._

## API Endpoint List

### API Endpoint List

**Repos:** KAI-Flow

| Method | Path | Description | Auth required |
| --- | --- | --- | --- |
| GET | /health, /api/health, /info, /api/v1/info, / | Health and service info | No |
| POST | /api/v1/auth/signup, /signin, /refresh, /signout | Register (blocked in enterprise mode), sign in, refresh tokens, sign out | No |
| GET, PUT | /api/v1/auth/me | Current user profile | JWT or master key (GET); JWT (PUT) |
| GET | /api/v1/auth/test/users | Development user list (email, role) | No |
| GET, POST, PUT, DELETE | /api/v1/api-keys[/{key_id}] | Manage per-user API keys | JWT |
| GET, POST | /api/v1/workflows | List / create workflows | JWT (GET); JWT or master key (POST) |
| GET, PUT, DELETE | /api/v1/workflows/{id} | Read / update / delete workflow | JWT |
| POST, PATCH | /api/v1/workflows/validate, /{id}/duplicate, /{id}/visibility, /{id}/create-template | Validate, duplicate, change visibility, save as template | JWT |
| GET | /api/v1/workflows/public/, /templates/, /templates/categories/ | Public workflows and templates | Optional JWT |
| GET, POST | /api/v1/workflows/search/, /stats/, /dashboard/stats/, /queue/status, /debug/workflow/{id}, /templates/ | Search, statistics, queue status, debug, create template | JWT |
| POST | /api/v1/workflows/execute, /execute-node | Run workflow or single node, SSE stream | JWT or master key |
| POST | /api/v1/workflows/{id}/execute-timer-node | Run a timer node | JWT |
| GET | /api/v1/workflows/error-trigger/{id}/stream | Error-trigger event stream (SSE) | No |
| GET, POST, DELETE | /api/v1/executions[/page, /workflow-options, /export/csv, /{id}] | List, page, filter, export CSV, read, delete executions | JWT |
| POST | /api/v1/executions/{id}/cancel, /executions/workflows/{id_or_name}/cancel | Cancel executions | JWT or master key |
| GET, POST, PUT, DELETE | /api/v1/credentials[/{id}, /{id}/workflows, /{id}/models, /{id}/test, /list-models, /test-raw] | Manage, test and list models for credentials | JWT |
| GET, POST, PUT, DELETE | /api/v1/variables[/{id}, /name/{name}, /type/{type}] | Manage variables | JWT |
| GET, POST, PUT, DELETE | /api/v1/chat[/{chatflow_id}, /{chatflow_id}/interact, /workflow/{id}, /chatflow/{id}, /active-session/id] | Chat sessions and messages | JWT |
| POST | /api/v1/ai-builder/generate | Generate or edit a workflow with an LLM | JWT |
| GET, POST | /api/v1/nodes[/categories, /{type}, /validate-config, /registry/stats, /search/{q}, /{type}/options] | Node catalogue for the canvas | JWT on some routes |
| GET, POST, PUT, DELETE, PATCH | /api/v1/nodes/registry[/{node_type}, /{node_type}/toggle, /stats/summary, /categories/list] | Node registry CRUD | No |
| GET, POST, PUT, DELETE | /api/v1/node-configurations[...] | Per-workflow node configuration | JWT |
| GET, POST, DELETE | /api/v1/documents/documents/[collections, search, bulk-store, {id}, {id}/chunks, stats/overview] | Document store (router prefix is applied twice) | JWT |
| GET, POST, DELETE | /api/v1/vectors/collections[/{id}, /stats, /documents, /search] | Vector collections | JWT |
| GET, POST, PUT, DELETE | /api/v1/webhooks[/{id}, /{id}/logs, /{id}/stats, /{id}/health] | Manage webhook endpoints | JWT (stats, health optional) |
| POST, GET | /api/v1/webhooks/trigger/{id}, /{id}/info | Trigger webhook | Webhook config + rate limit |
| GET, POST, PUT, PATCH, DELETE | /api/v1/webhook-test/{id}, /api/v1/webhook/{id} (+ /stream) | Test and production webhook entry points | Node auth: none, basic or header |
| POST, GET | /api/v1/webhooks/{id}/start-listening, /stop-listening, /stats | Webhook listener control | No |
| GET, POST | /api/v1/jobs/scheduled[/{id}, /{id}/trigger, /{id}/executions] | Scheduled jobs | JWT |
| GET, POST | /api/timers/{id}/status\|start\|stop\|trigger\|stream (also /api/v1/timers) | Timer control and SSE | No |
| GET, POST | /api/v1/kafka/listeners/{id}/stream, /stop, /debug/{node_id} | Kafka listener control | JWT on some routes |
| GET, POST | /api/http-client, /{node_id}/test, /{node_id}/stats | HTTP client node test | No |
| GET, POST, DELETE | /api/v1/model-artifacts/capabilities, /status, /upload, /upload-directory, /{id} | Model artifact upload and lifecycle | JWT |
| POST | /api/v1/export/workflows | Export workflow bundle | JWT |
| GET, POST, DELETE | /api/v1/external[/register, /{id}/info, /{id}/chat, /{id}/status, /{id}/sessions...] | External workflow registry and chat | JWT |
| GET | /api/v1/logs/stream | Live backend logs (development only) | No (404 outside development) |
| GET | /widget/* | Static widget assets | No |

_Router prefixes from main.py include_router (API_START=api, API_VERSION=v1) plus router-level prefixes; auth from Depends(get_current_user / get_current_user_or_master_api_key / get_optional_user) per route. api/workflow_integration.py is not included in main.py. The table records current behaviour; the chosen protection for the routes marked No is in Security Checklist › Unauthenticated management endpoints._

## Cache Strategy

### Cache layers

**Repos:** KAI-Flow

- Backend: no Redis or shared cache. Node outputs are kept in the LangGraph workflow state (core/output_cache.py reads them back); execution slots, canvas sessions and Kafka listeners are process-local; LangGraph checkpoints use MemorySaver unless PostgresSaver is importable.
- Frontend: TanStack Query caches server state; zustand stores hold UI and entity state.
- Invalidation: process restart clears all backend in-memory state; client caches refetch per TanStack Query defaults.

_core/output_cache.py, core/execution_queue.py, core/checkpointer.py; requirements.txt pins langgraph-checkpoint but not a Postgres checkpoint package; no redis import found in backend/app._

### Shared state across backend instances

**Repos:** KAI-Flow

<!-- dijji-decision: {"schemaVersion":1,"decision":{"id":"decision_backend_single_instance","category":"scalability","scope":{"kind":"parts","partIds":["node_application_22a2fb6cbffb"]},"adoption":"new-and-modified","review":"proposed"},"value":"Single backend instance is the supported deployment boundary; process-local shared state is kept as is","rationale":"Chosen by the user over moving shared state to the database or a shared cache. core/execution_queue.py keeps running executions and locks in a process dict; kafka_trigger.py KafkaListenerService is process-local; core/checkpointer.py falls back to MemorySaver; main.py starts the maintenance and Kafka reconciliation loops per process. With more than one replica the same workflow could run concurrently, Kafka messages could be processed twice and in-flight state is lost on restart, so multi-replica operation is out of scope and would be a separate, larger change. docker-compose.yml runs one kai-flow-backend container, which matches this boundary.","source":"user correction: architecture › Cache Strategy › Shared state across backend instances; code: KAI-Flow/backend/app/core/execution_queue.py; code: KAI-Flow/docker-compose.yml"} -->

Single backend instance is the supported deployment boundary; process-local shared state is kept as is

_Chosen by the user over moving shared state to the database or a shared cache. core/execution_queue.py keeps running executions and locks in a process dict; kafka_trigger.py KafkaListenerService is process-local; core/checkpointer.py falls back to MemorySaver; main.py starts the maintenance and Kafka reconciliation loops per process. With more than one replica the same workflow could run concurrently, Kafka messages could be processed twice and in-flight state is lost on restart, so multi-replica operation is out of scope and would be a separate, larger change. docker-compose.yml runs one kai-flow-backend container, which matches this boundary._

## Security Checklist

### Security Checklist

**Repos:** KAI-Flow

| Control | Implementation |
| --- | --- |
| Password hashing | pwdlib Argon2 (bcrypt accepted for verification) |
| JWT secret | HS256 signed with SECRET_KEY from environment; Keycloak tokens verified as RS256 via JWKS |
| Token rotation | Refresh issues a new access + refresh pair; old refresh tokens are not revoked; signout is client-side only |
| Brute force | No login attempt limit or lockout; login_activity table is not written by signin |
| Email enumeration | Signin returns a generic 'Incorrect email or password'; signup returns 'User already exists' |
| Reset / verify token | No password reset or email verification flow |
| Credential storage | Fernet encryption with CREDENTIAL_MASTER_KEY (PBKDF2 derivation when not a Fernet key); a random key is generated with a warning if unset |
| Machine access | Single MASTER_API_KEY compared with secrets.compare_digest, mapped to a system user; per-user API keys are stored hashed but not accepted yet (target: Per-user API keys) |
| Management endpoint auth | Node registry, timer control, webhook listener control, HTTP client test and the development user list need no auth; X-Internal-Call from any client selects the system user (target: Unauthenticated management endpoints) |
| Rate limiting | Per webhook endpoint (rate_limit_per_minute, default 60); RATE_LIMIT_* constants exist but no global middleware applies them |
| CSRF + XSS | Bearer tokens in localStorage (no cookies, so no CSRF surface); rehype-raw renders raw HTML in markdown output |
| CORS | CORSMiddleware allow_origins=['*'] with allow_credentials=True; ALLOWED_ORIGINS env is not read (target: Browser origin policy (CORS)) |
| Code execution node | Python run in a subprocess with a 30 s timeout and AST guards; documented in code as not a full sandbox |
| Model scanning | modelaudit + fickling in a separate process with a memory limit; artifacts streamed to disk, local roots allow-listed and read-only |
| Supply chain | Trivy filesystem scan on backend push; pinned dependency versions |

_Current implementation from core/security.py, auth/dependencies.py, api/auth.py, api/node_registry.py, api/timers.py, api/workflows.py, core/encryption.py, main.py CORSMiddleware, api/webhooks.py check_rate_limit, nodes/processing/code_node.py, services/model_scan_process.py, .github/workflows/backend-ci.yml. Chosen targets are the decision fields that follow in this section._

### Per-user API keys

**Repos:** KAI-Flow

<!-- dijji-decision: {"schemaVersion":1,"decision":{"id":"decision_per_user_api_keys","category":"authentication","scope":{"kind":"parts","partIds":["node_application_22a2fb6cbffb","node_application_ff2c090afd77"]},"adoption":"new-and-modified","review":"proposed"},"value":"Per-user API keys are accepted as caller identity for workflow execution and widget requests and reach only the key owner's workflows","rationale":"Chosen by the user over removing the per-user key feature. Not implemented yet: api/api_key.py and services/api_key_service.py create, list, update and delete hashed keys (api_keys table), but no authentication dependency reads them; auth/dependencies.py get_current_user_or_master_api_key accepts only MASTER_API_KEY or a JWT. widget/src/KaiChatWidget.tsx sends the configured token as both Bearer and X-API-Key. MASTER_API_KEY maps to the system user and reaches the whole system, so it must not be embedded in host sites. Untested: no test covers this rule yet.","source":"user correction: architecture › Security Checklist › Per-user API keys; code: KAI-Flow/backend/app/auth/dependencies.py; code: KAI-Flow/backend/app/api; code: KAI-Flow/widget"} -->

Per-user API keys are accepted as caller identity for workflow execution and widget requests and reach only the key owner's workflows

_Chosen by the user over removing the per-user key feature. Not implemented yet: api/api_key.py and services/api_key_service.py create, list, update and delete hashed keys (api_keys table), but no authentication dependency reads them; auth/dependencies.py get_current_user_or_master_api_key accepts only MASTER_API_KEY or a JWT. widget/src/KaiChatWidget.tsx sends the configured token as both Bearer and X-API-Key. MASTER_API_KEY maps to the system user and reaches the whole system, so it must not be embedded in host sites. Untested: no test covers this rule yet._

### Unauthenticated management endpoints

**Repos:** KAI-Flow

<!-- dijji-decision: {"schemaVersion":1,"decision":{"id":"decision_management_endpoint_auth","category":"authorization","scope":{"kind":"parts","partIds":["node_application_22a2fb6cbffb"]},"adoption":"new-and-modified","review":"proposed"},"value":"All management endpoints require an authenticated session; node registry changes are admin-only; the development user list endpoint is removed; the system-user switch is allowed only for the server's own internal calls","rationale":"Chosen by the user over keeping the open behaviour behind a trusted-network requirement, because these operations act directly on data and triggers. Not implemented yet: api/node_registry.py and api/timers.py routes depend only on get_db_session; api/auth.py GET /test/users has no auth dependency; webhook start/stop-listening and http-client test routes also lack user auth. api/workflows.py execute_adhoc_workflow switches to executor.get_or_create_master_user whenever the request carries X-Internal-Call: true, a header any client can send; api/webhooks.py sets it for its internal execute call. Under this rule a client-supplied header alone must not select the system user. Untested: no test covers this rule yet.","source":"user correction: architecture › Security Checklist › Unauthenticated management endpoints; code: KAI-Flow/backend/app/api"} -->

All management endpoints require an authenticated session; node registry changes are admin-only; the development user list endpoint is removed; the system-user switch is allowed only for the server's own internal calls

_Chosen by the user over keeping the open behaviour behind a trusted-network requirement, because these operations act directly on data and triggers. Not implemented yet: api/node_registry.py and api/timers.py routes depend only on get_db_session; api/auth.py GET /test/users has no auth dependency; webhook start/stop-listening and http-client test routes also lack user auth. api/workflows.py execute_adhoc_workflow switches to executor.get_or_create_master_user whenever the request carries X-Internal-Call: true, a header any client can send; api/webhooks.py sets it for its internal execute call. Under this rule a client-supplied header alone must not select the system user. Untested: no test covers this rule yet._

### Browser origin policy (CORS)

**Repos:** KAI-Flow

<!-- dijji-decision: {"schemaVersion":1,"decision":{"id":"decision_cors_allow_list","category":"security","scope":{"kind":"parts","partIds":["node_application_22a2fb6cbffb"]},"adoption":"new-and-modified","review":"proposed"},"value":"CORS allow-list is read from the ALLOWED_ORIGINS environment setting; in production only the web client origin and the origins of sites embedding the widget are allowed","rationale":"Chosen by the user over leaving every origin open as an accepted risk. Not implemented yet: main.py adds CORSMiddleware with allow_origins=['*'] and allow_credentials=True; docker-compose.yml passes ALLOWED_ORIGINS (default *) and .env.example defines it, but main.py does not read it. Untested: no test covers this rule yet.","source":"user correction: architecture › Security Checklist › Browser origin policy (CORS); code: KAI-Flow/backend/main.py; code: KAI-Flow/docker-compose.yml; code: KAI-Flow/.env.example"} -->

CORS allow-list is read from the ALLOWED_ORIGINS environment setting; in production only the web client origin and the origins of sites embedding the widget are allowed

_Chosen by the user over leaving every origin open as an accepted risk. Not implemented yet: main.py adds CORSMiddleware with allow_origins=['*'] and allow_credentials=True; docker-compose.yml passes ALLOWED_ORIGINS (default *) and .env.example defines it, but main.py does not read it. Untested: no test covers this rule yet._

## ADRs

### ADRs

**Repos:** KAI-Flow

- ADR-001: Workflow runtime - canvas JSON (flow_data) is compiled into a LangGraph graph at execution time by core/graph_builder; nodes are Python classes discovered at startup
- ADR-002: Persistence - single PostgreSQL 15 database; schema created and additively column-synced by migrations/database_setup.py on container start instead of versioned Alembic migrations (alembic is pinned but unused)
- ADR-003: Identity - local JWT (HS256) with optional Keycloak OIDC (RS256 + JIT user provisioning) and a single MASTER_API_KEY for automation; per-user API keys are the chosen identity for workflow execution and widget calls (not yet implemented, see Security Checklist › Per-user API keys)
- ADR-004: Secrets - user credentials encrypted at rest with Fernet keyed by CREDENTIAL_MASTER_KEY
- ADR-005: Background work - in-process asyncio tasks and an in-memory execution queue instead of a job broker; a single backend instance is the supported deployment boundary (Cache Strategy › Shared state across backend instances)
- ADR-006: Model scanning isolation - scans run in a separate process (forkserver/spawn) with a memory ceiling; artifacts streamed to persistent disk, never held in RAM
- ADR-007: Results streaming - workflow, webhook-test, timer, Kafka and error-trigger events are delivered to the UI over Server-Sent Events
- ADR-008: Widget distribution - widget published as npm package @kaifusion/widget and as a script bundle served by the backend at /widget

_Each ADR is grounded in the code paths named in its line; see main.py, core/, services/, migrations/database_setup.py, widget/._
