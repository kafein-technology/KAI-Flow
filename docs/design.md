# Design

_A field marked **Repos:** applies only to those repositories; a field without the line is project-wide._

## Page List (Sitemap)

### Public pages

**Repos:** KAI-Flow

| # | Page | URL |
| --- | --- | --- |
| 1 | Sign in | /signin |
| 2 | Register (hidden when ENTERPRISE=true) | /register |

_client/app/App.tsx Routes; register route rendered only when !config.IS_ENTERPRISE. Paths are relative to VITE_BASE_PATH (vite.config.ts defaults to /kai, .env.example sets /)._

### Admin pages

**Repos:** KAI-Flow

| # | Page | URL |
| --- | --- | --- |
| 1 | Home dashboard | / |
| 2 | Workflows | /workflows |
| 3 | Canvas | /canvas?workflow=<id> |
| 4 | Executions | /executions |
| 5 | Credentials | /credentials |
| 6 | Variables | /variables |
| 7 | Marketplace (hidden when ENTERPRISE=true) | /marketplace |
| 8 | Pinned items | /pinned |
| 9 | Settings (profile) | /settings |
| 10 | Not found | * |

_client/app/App.tsx Routes; each listed route component wraps content in AuthGuard (client/app/routes)._

## Wireframes

### Sign in — wireframe

**Repos:** KAI-Flow

```
+------------------------------+
|  [logo]                      |
|  Sign in                     |
|  [ Email                   ] |
|  [ Password            (o) ] |
|  [        Sign in          ] |
|  [  Sign in with Keycloak  ] |
|  No account? Register        |
+------------------------------+
Desktop: same card centred, background gradient.
```

_Derived from routes/signin.tsx headings and components/KeycloakLoginButton.tsx; layout confirmed by the user._

### Sign in — notes

**Repos:** KAI-Flow

- Guarded by PublicOnlyGuard: signed-in users are redirected away.
- Keycloak button only when OIDC authority and client id are configured.
- Browser-native password reveal controls are hidden in favour of the custom toggle (app.css).
- States: idle, submitting, error (Incorrect email or password / Account is inactive).

_components/PublicOnlyGuard.tsx, components/KeycloakLoginButton.tsx, app/app.css, api/auth.py error details._

### Register — wireframe

**Repos:** KAI-Flow

```
+------------------------------+
|  Create account              |
|  [ Full name (John Doe)    ] |
|  [ Email                   ] |
|  [ Password            (o) ] |
|  [        Register         ] |
|  Have an account? Sign in    |
+------------------------------+
```

_Derived from routes/register.tsx placeholders; layout confirmed by the user._

### Register — notes

**Repos:** KAI-Flow

- Route exists only when ENTERPRISE=false; backend also returns 403 in enterprise mode.
- States: idle, submitting, error (User already exists), success (tokens stored, redirect).

_client/app/App.tsx; api/auth.py signup._

### Home dashboard — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Dashboard                     |
| bar  | [stat] [stat] [stat] [stat]   |
|      | +---------------------------+ |
|      | | Production Executions &   | |
|      | | Avg Runtime (chart)       | |
|      | +---------------------------+ |
+------+-------------------------------+
Mobile: sidebar collapses, cards stack.
```

_Derived from routes/home.tsx (DashboardChart title) and components/dashboard/DashboardSidebar; layout confirmed by the user._

### Home dashboard — notes

**Repos:** KAI-Flow

- Data from GET /api/v1/workflows/dashboard/stats/.
- Chart: Production Executions and Avg Runtime (recharts).
- States: loading, empty, populated.

_routes/home.tsx; components/DashboardChart.tsx; api/workflows.py dashboard stats._

### Workflows — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Workflows        [+ New]      |
| bar  | [ Search workflows...       ] |
|      | name | updated | public | ... |
|      | name | updated | public | ... |
|      | < pagination >                |
+------+-------------------------------+
```

_Derived from routes/workflows.tsx; layout confirmed by the user._

### Workflows — notes

**Repos:** KAI-Flow

- Search input 'Search workflows...'; create via 'Enter workflow name' modal.
- My workflows / External workflows tab navigation is commented out (DISABLED Tab Navigation).
- Actions map to duplicate, visibility, delete and export endpoints.

_routes/workflows.tsx activeTab state and disabled tab block._

### Canvas — wireframe

**Repos:** KAI-Flow

```
+------------------------------------------------+
| Navbar: name | save | run | export | ...       |
+---------+------------------------+-------------+
| Node    |                        | Chat panel  |
| search  |   flow canvas          | (history,   |
| [....]  |   [node]--->[node]     |  messages,  |
| list    |        \-->[node]      |  input)     |
+---------+------------------------+-------------+
| Log panel (live execution events)              |
+------------------------------------------------+
Desktop-first; full-screen layout (h-screen).
```

_Derived from components/canvas (FlowCanvas, ChatComponent, ChatHistorySidebar, LogPanel, NodeContextMenu) and components/common (Navbar, Sidebar); layout confirmed by the user._

### Canvas — notes

**Repos:** KAI-Flow

- Wrapped in AuthGuard, ErrorBoundary and ReactFlowProvider; workflow loaded from ?workflow=<id>.
- Node sidebar search stays sticky while scrolling.
- Chat panel runs the workflow and streams responses; log panel shows live events; node context menu; fullscreen node modal.
- Modals: autosave, unsaved changes, export, error workflow, widget export, workflow edit; guided tutorial available.
- States: empty canvas, editing, running (live node status), error display.

_routes/canvas.tsx; components/canvas and components/modals listings; recent commit fixes sticky node search bar._

### Executions — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Executions      [Export CSV]  |
| bar  | [Search...] [workflow v] [x]  |
|      | id | workflow | status | time |
|      | id | workflow | status | time |
|      | < pagination >                |
+------+-------------------------------+
```

_Derived from routes/executions.tsx; layout confirmed by the user._

### Executions — notes

**Repos:** KAI-Flow

- Search 'Search executions...', workflow filter, 'Clear all filters', 'Export filtered executions as CSV'.
- Data from /api/v1/executions/page, /workflow-options, /export/csv.
- Empty state 'No executions yet'.

_routes/executions.tsx; api/executions.py._

### Credentials — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Credentials        [+ Add]    |
| bar  | [ Search credentials...     ] |
|      | [card] [card] [card]          |
|      | [card] [card]                 |
+------+-------------------------------+
```

_Derived from routes/credentials.tsx and components/credentials; layout confirmed by the user._

### Credentials — notes

**Repos:** KAI-Flow

- Add flow: service-selection modal, then dynamic form from the credential service catalogue.
- Actions: test connection, edit, delete, show using workflows.
- Secrets never returned in clear text to list views (encrypted at rest).

_components/credentials (cards, selector, dynamic forms, service-selection modal); api/credentials.py._

### Variables — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Variables          [+ Add]    |
| bar  | [ Search variables...       ] |
|      | name | type | value | [e][d]  |
+------+-------------------------------+
```

_Derived from routes/variables.tsx; layout confirmed by the user._

### Variables — notes

**Repos:** KAI-Flow

- Search 'Search variables...'; value input 'Enter variable value...'; row actions 'Edit variable', 'Delete variable'.
- Empty state 'No variables found'.

_routes/variables.tsx; api/variables.py._

### Marketplace — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Marketplace                   |
| bar  | [category chips]  [search]    |
|      | [template] [template]         |
|      | [template] [template]         |
+------+-------------------------------+
```

_Derived from routes/marketplace.tsx; layout confirmed by the user._

### Marketplace — notes

**Repos:** KAI-Flow

- Sources: six bundled template JSON files plus public workflows and templates from the API.
- Empty state 'No public workflows found'.
- Hidden when ENTERPRISE=true.

_client/app/data/templates; routes/marketplace.tsx; App.tsx._

### Pinned items — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Pinned Items                  |
| bar  | [pinned item] [pinned item]   |
+------+-------------------------------+
```

_Derived from routes/pinned.tsx; layout confirmed by the user._

### Pinned items — notes

**Repos:** KAI-Flow

- Pin and unpin via the shared PinButton; section rendered by PinnedItemsSection.
- States: empty, populated.

_routes/pinned.tsx; components/common/PinButton.tsx, PinnedItemsSection.tsx._

### Settings — wireframe

**Repos:** KAI-Flow

```
+------+-------------------------------+
| Side | Settings                      |
| bar  | Profile          [Edit]       |
|      | [ First name ] [ Last name ]  |
|      | [ Email                     ] |
|      | [Save] [Cancel]               |
+------+-------------------------------+
```

_Derived from routes/settings.tsx; layout confirmed by the user._

### Settings — notes

**Repos:** KAI-Flow

- Form fields first_name, last_name, email; full_name is split on load and joined on save via PUT /api/v1/auth/me.
- Validation: first and last name required.
- States: view, editing, saving, success/error snackbar.

_routes/settings.tsx SettingsLayout; api/auth.py update profile._

## Design System

### Color palette

**Repos:** KAI-Flow

- Mode: light (html color-scheme: light).
- Primary: Tailwind blue (blue-600 most used, blue-500/700 hover and pressed, blue-100 tints).
- Accent: purple-600 to blue-600 gradient on page titles; purple-500.
- Neutrals: gray-100 surfaces, gray-700/800/900 and slate-700/800 dark surfaces and text.
- Semantic: success green, error red, warning and info via daisyUI defaults.
- Widget default colour #526cfe (configurable).

_Tailwind utility frequency in client/app (bg-blue-600 x70, bg-gray-100 x62, bg-blue-500 x56, bg-gray-800 x55); app.css; widget README._

### Typography

**Repos:** KAI-Flow

- Font: Inter (Google Fonts, variable weight 100-900).
- Scale: Tailwind defaults xs to 4xl; page titles text-4xl font-bold, auth titles text-3xl font-semibold.
- Markdown output: @tailwindcss/typography prose, KaTeX for math.

_app/app.css imports Inter and typography plugin; routes h1 classes._

### Spacing

**Repos:** KAI-Flow

- Base unit 4 px (Tailwind spacing scale: 1 = 0.25rem).
- Common steps 2, 3, 4, 6, 8.

_Tailwind 4 default scale; no custom spacing tokens are defined in app.css._

### Border radius

**Repos:** KAI-Flow

- Most used: rounded-lg (cards, inputs), rounded-full (pills, avatars, icon buttons), rounded-md, rounded-xl, rounded-2xl (modals and large cards).

_Utility frequency in client/app: rounded-lg x231, rounded-full x144, rounded-md x78, rounded-xl x76, rounded-2xl x42._

### Component patterns

**Repos:** KAI-Flow

- Buttons: solid blue primary, gray secondary, icon buttons (lucide-react icons).
- Inputs: Formik-managed forms; Monaco editor for code fields; JSON editor.
- Cards: credential and template cards (rounded-lg, light surface).
- Modals: body scroll locked (.modal-open) with scrollbar compensation.
- Notifications: notistack snackbars, container offset 4 percent from top.

_client/package.json (daisyui, formik, lucide-react, notistack, @monaco-editor/react); app.css; components/common._

### Responsive breakpoints

**Repos:** KAI-Flow

- sm 640px (most used, 94 occurrences)
- md 768px
- lg 1024px
- xl 1280px (rare)

_Tailwind 4 defaults; prefix frequency in client/app: sm x94, md x24, lg x20, xl x2._

### Animation

**Repos:** KAI-Flow

- animate-slide-up: 0.3s cubic-bezier(0.4, 0, 0.2, 1), translateY(100%) to 0 with fade.
- motion library for component transitions (client and widget).

_app/app.css @layer utilities; client and widget package.json include motion._

## Framework Config

### Framework Config

**Repos:** KAI-Flow

/* client/app/app.css */
@import "tailwindcss";
@plugin "daisyui";
@plugin "@tailwindcss/typography";
@import "@xyflow/react/dist/style.css";
@import "katex/dist/katex.min.css";
html { color-scheme: light; font-family: "Inter", sans-serif; }

// vite.config.ts: @tailwindcss/vite + @vitejs/plugin-react, base = VITE_BASE_PATH (default /kai),
// dev proxy /api/kai -> VITE_API_BASE_URL. Runtime config: public/config.js written by docker-entrypoint.sh.

_client/app/app.css; client/vite.config.ts; client/Dockerfile copies public/config.js and runs docker-entrypoint.sh._
