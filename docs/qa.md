# QA

_A field marked **Repos:** applies only to those repositories; a field without the line is project-wide._

## Test Strategy

### Existing automated tests

**Repos:** KAI-Flow

- Frontend: client/app/components/canvas/ChatComponent.test.tsx (Vitest + Testing Library, jsdom)
- Frontend: jest + jest-axe accessibility script (test:a11y) configured, no matching test files
- Backend: pytest configured in CI against tests/, but backend/tests does not exist (the Merge gate decision requires creating it)

_find for *.test.* and test_*.py; client/vitest.config.ts; client/jest.config.js; .github/workflows/backend-ci.yml._

### Test levels

**Repos:** KAI-Flow

- Unit - backend pytest + pytest-asyncio with database and LLM providers replaced by test doubles; frontend Vitest + Testing Library
- Integration (API + PostgreSQL) - pytest against the postgres:15 service container; CI only - DIJJI does not run it (backend-ci.yml lint-and-test job)
- E2E - critical flows against a deployed environment (DIJJI e2e stage)
- Accessibility and performance - Lighthouse CI thresholds from client/lighthouse.config.js on the built client

_Unit + API integration + E2E chosen because the backend is API-heavy with SSE streaming that unit tests cannot cover end to end; integration needs a running PostgreSQL that this environment does not have, so it stays in CI._

### Coverage targets

**Repos:** KAI-Flow

- Unit: at least 70 percent line coverage on new and modified backend and client modules
- E2E: 11 critical flows (one per architecture flow)

_No coverage threshold is enforced today (Codecov upload with fail_ci_if_error false); targets confirmed by the user._

### Coverage targets — Lighthouse

**Repos:** KAI-Flow

- Performance >= 0.8
- Accessibility >= 0.9
- Best practices >= 0.8
- SEO >= 0.8

_client/lighthouse.config.js assertions (3 runs against http://localhost:4173); no workflow invokes Lighthouse._

## Test Case List

### E2E scenarios

**Repos:** KAI-Flow

| # | Scenario | Steps |
| --- | --- | --- |
| 1 | Sign in and silent refresh (F-AUTH) | Sign in with valid user; land on dashboard; expire access token; next API call succeeds after refresh; wrong password shows generic error |
| 2 | Build and save workflow (F-BUILD) | Open canvas; add Start, agent and End nodes; connect; save; reload /canvas?workflow=id shows same graph; AI builder generates a draft from a prompt |
| 3 | Run and chat (F-RUN) | Open saved workflow; send chat message; streamed reply appears; execution listed on /executions with completed status; cancel a long run |
| 4 | Error workflow (F-ERROR) | Link an error workflow; run a workflow that fails; error workflow execution appears |
| 5 | Webhook trigger (F-WEBHOOK) | Create webhook node with header auth; call production URL with and without header; 2xx vs 401; event logged; exceed rate limit returns rejection |
| 6 | Scheduled run (F-TIMER) | Create interval timer; start; run appears in job executions; stop; no further runs |
| 7 | Kafka trigger (F-KAFKA) | Configure Kafka trigger on a reachable test broker; publish message; workflow execution recorded; stop listener |
| 8 | Widget chat (F-WIDGET) | Embed widget script on a test page; send message; streamed answer shown; invalid token shows auth error |
| 9 | Credential lifecycle (F-CRED) | Add OpenAI-compatible credential; test connection; use in a node; list using workflows; delete |
| 10 | Model scan (F-MODELSCAN) | Upload a small benign and a malicious pickle; scan via scanner node; malicious flagged; artifact expires after retention |
| 11 | Export bundle (F-EXPORT) | Export a workflow; bundle downloads with workflow and configuration |

_One scenario per System Flow Diagram flow; run against a deployed environment, not bound to a local container suite._

### Unit coverage

**Repos:** KAI-Flow

- Backend core/graph_builder - flow_data to LangGraph compilation, connection validation, control-flow routing
- Backend services/workflow_executor + core/execution_queue - slot acquisition, cancel, status transitions
- Backend auth/dependencies + core/security - JWT verify, Keycloak JIT, master key, refresh
- Backend core/encryption - Fernet round trip, key derivation, rotate_key
- Backend triggers - webhook auth (basic, header), rate limit, timer next_run_at via croniter, Kafka listener reconcile
- Backend services/model_artifact_store + maintenance - retention, leases, disk-pressure thresholds
- Backend services/ai_builder - validator, diff engine, layout engine
- Backend nodes/processing/code_node - AST guards and timeout
- Widget KaiChatWidget - SSE parsing and auth header construction
- Client lib/api-client - token attach, 401 refresh queue, logout on refresh failure
- Client lib/useSSE + liveExecution - stream parsing and node status updates
- Client pages - signin, register, home, workflows, canvas (ChatComponent existing), executions, credentials, variables, marketplace, pinned, settings: render, empty and error states

_At least one target per backend service in Service Topology and per page in the sitemap._

## CI/CD Integration

### Pipeline flow

**Repos:** KAI-Flow

PR opened / push touching backend/**: ruff check + format (non-blocking), mypy (non-blocking), pytest tests/ with coverage on a postgres:15 service (non-blocking), Codecov upload. Push only: Trivy fs scan uploaded as SARIF.
PR opened / push touching client/**: npm ci, eslint (non-blocking), tsc (non-blocking), vitest run --coverage (non-blocking), Codecov upload, vite build (blocking).
Push to main: build and push multi-arch backend and frontend images to Docker Hub tagged latest and commit SHA.
Tag push v* or manual dispatch: build and push both images tagged with the version and SHA; create GitHub release with generated notes.

_.github/workflows/backend-ci.yml, frontend-ci.yml, deploy.yml; continue-on-error and '|| echo ::warning' on lint, type and test steps. Current behaviour; the chosen blocking gate is Merge gate below._

### Run frequency

**Repos:** KAI-Flow

| Test type | When |
| --- | --- |
| Backend lint, type check, unit/integration tests | Every push and PR touching backend/** |
| Backend Trivy scan | Every push touching backend/** |
| Frontend lint, type check, unit tests, build | Every push and PR touching client/** |
| Image build and push | Push to main (per changed side); v* tag or manual dispatch (both) |
| Lighthouse | Not scheduled (config only) |
| E2E | Not present in CI |

_on: push/pull_request paths filters and job if conditions in .github/workflows._

### Merge gate

**Repos:** KAI-Flow

<!-- dijji-decision: {"schemaVersion":1,"decision":{"id":"decision_ci_merge_gate","category":"ci","scope":{"kind":"parts","partIds":["node_application_22a2fb6cbffb","node_application_a4498e12e133"]},"adoption":"new-and-modified","review":"proposed"},"value":"Test, type-check and lint failures block the PR; a backend test directory is created so the backend test step runs real tests","rationale":"Chosen by the user over blocking on tests only or keeping the warning-only model, because images are published automatically on every push to main. Not implemented yet: backend-ci.yml and frontend-ci.yml mark ruff/mypy/pytest and eslint/tsc/vitest steps continue-on-error with '|| echo ::warning'; Codecov fail_ci_if_error is false; backend/tests is absent while pytest targets tests/; the docker-build jobs depend on lint-and-test, which therefore always passes. Once the checks block, a failing check also stops the image publication that depends on them.","source":"user correction: qa › CI/CD Integration › Merge gate; code: KAI-Flow/.github/workflows"} -->

Test, type-check and lint failures block the PR; a backend test directory is created so the backend test step runs real tests

_Chosen by the user over blocking on tests only or keeping the warning-only model, because images are published automatically on every push to main. Not implemented yet: backend-ci.yml and frontend-ci.yml mark ruff/mypy/pytest and eslint/tsc/vitest steps continue-on-error with '|| echo ::warning'; Codecov fail_ci_if_error is false; backend/tests is absent while pytest targets tests/; the docker-build jobs depend on lint-and-test, which therefore always passes. Once the checks block, a failing check also stops the image publication that depends on them._

## Bug Tracking

### Labels

**Repos:** KAI-Flow

- type: bug, enhancement, security, docs
- severity: critical, high, medium, low
- area: backend, client, widget, nodes, triggers, model-security, ci
- status: needs-triage, confirmed, in-progress

_No issue templates or label config found in .github; label set confirmed by the user._

### Bug template

**Repos:** KAI-Flow

Title: <short description>
Area: backend | client | widget | node <type> | trigger <type>
Steps to reproduce: 1. ... 2. ... 3. ...
Expected result:
Actual result:
Workflow export or node configuration (secrets removed):
Environment: version tag / commit, deployment (compose, native), browser, ENTERPRISE and KEYCLOAK_ENABLED flags
Logs: backend log excerpt, execution id

_No .github/ISSUE_TEMPLATE present; template tailored to workflow debugging, confirmed by the user._

## Manual Test Checklist

### Manual Test Checklist

**Repos:** KAI-Flow

- Widget embedded on third-party pages with conflicting CSS, left and right positions, custom colour, mobile viewport
- Long-running streamed responses on slow networks: stream continues, cancel works, no duplicated messages
- Keycloak sign-in, logout sync and JIT provisioning with a real realm
- Large model upload close to the 8 GiB browser cap; resume after page refresh shows correct state
- Disk-pressure behaviour at 75/85/90 percent on the artifact volume
- Canvas keyboard-only use (focus order, delete, context menu) and screen-reader labels on node forms
- Base path deployment under /kai behind a reverse proxy (routing, assets, API calls)
- Enterprise mode hides register and marketplace and blocks signup

_Derived from the surfaces that unit and E2E tests cannot exercise reliably (third-party embedding, real IdP, large files, disk pressure, assistive technology)._
