# Front-end - Steam Game Data Demo

The user-facing web application for the project. Deployed on **Vercel** and
talks to the back-end VPS only through the public REST API.

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Framework | **Next.js 14+ (App Router)** | SSR + first-class Vercel support |
| Language | **TypeScript** (strict) | Type-safe contracts that mirror the BE schema |
| Styling | **Tailwind CSS** + semantic CSS variables | Light-first themes with an optional dark class |
| State (auth + status) | **Zustand** | Tiny, no boilerplate |
| Data fetching | **SWR** | Cache + revalidate, plays well with axios |
| HTTP | **Axios** | Interceptors for auth header + server-status events |
| Charts | **Chart.js + react-chartjs-2**, **Plotly.js** | Theme-aware dashboard charts and interactive Agent Harness charts |
| Icons | **lucide-react** | Lightweight, tree-shakeable |
| Forms | **react-hook-form + zod** | Type-safe validation |

## Folder layout

```
front_end/
  src/
    app/                       # Next.js App Router
      layout.tsx               # Root layout (Header + Sidebar + status boot)
      page.tsx                 # Entry: redirect to /login or /dashboard or /games
      globals.css              # Light/dark semantic colour tokens
      login/page.tsx           # Login + register (zod-validated forms)
      games/
        page.tsx               # Games list (filter/sort/search + pagination)
        [appid]/page.tsx       # Game detail + reviews (filter/sort/search)
      dashboard/page.tsx       # Full-width analytics dashboard (no chat)
      chat/page.tsx            # Durable Agent Harness workspace
      admin/page.tsx           # Admin-only: users + roles (gated)
    components/
      layout/
        Header.tsx             # App title + ServerStatusBadge + user menu
        Sidebar.tsx            # Role-aware nav (viewer / analyst / admin)
        ServerStatusBadge.tsx  # Always-on indicator (idle / fetching / ...)
      common/
        DataTable.tsx          # Generic sortable table with loading row
        FilterBar.tsx          # Renders search/text/number/select/boolean filters
        Pagination.tsx         # Prev/Next + total + last-page
        SearchInput.tsx        # Search-icon input
      analytics/
        ChartRenderer.tsx      # Chart.js wrapper for dashboard chart output
        StatsCards.tsx         # Top-row KPI cards
      games/
        GameListTable.tsx      # Filterable/sortable games table
        GameDetailPanel.tsx    # Header + reviews list (filterable)
      chat/
        AgentChatWorkspace.tsx # Sessions, runs, tool events, cancel and charts
      Renderers/
        PlotlyChartRenderer.tsx # Interactive Agent Harness chart payloads
      auth/
        RoleGuard.tsx          # Client-side role gate
    hooks/
      useAuth.ts               # login / register / logout / me / hasRole
      useGames.ts              # SWR-backed games + reviews list/detail
      useDashboard.ts          # SWR-backed /dashboard/* endpoints
      useAgentHarness.ts       # /agent-rpc durable conversation workflow
      useServerStatus.ts       # Periodic ping + axios interceptor listener
      useFilters.ts            # Generic filter state container
    lib/
      api.ts                   # Axios client + interceptors + stage emitter
      auth.ts                  # localStorage token helpers
      types.ts                 # Shared TS types (mirror backend)
    store/
      authStore.ts             # Zustand: tokens, user, hasRole
      serverStatusStore.ts     # Zustand: stage, detail, lastError
    utils/
      permissions.ts           # Role/permission matrix
      format.ts                # Number/date formatters + classNames helper
  package.json
  tsconfig.json
  next.config.mjs
  tailwind.config.ts
  postcss.config.mjs
  .env.local.example
  .gitignore
```

## Role-based UI

The app distinguishes four roles (matching `back_end/app/models/user.py`):

| Role | Default page | What they see |
| --- | --- | --- |
| `viewer` | `/games` | Games list + game detail with reviews |
| `analyst` | `/dashboard` | Analytics dashboard and durable AI Agent workspace |
| `scientist` | `/dashboard` | Analytics dashboard and durable AI Agent workspace |
| `admin` | `/dashboard` | Dashboard, AI Agent and `/admin` management |

`src/components/auth/RoleGuard.tsx` is a client-side gate that wraps protected
pages. The back-end still enforces RBAC via JWT + role checks; the FE guard is
only for UX (redirect before flashing protected content).

## Server-status indicator

A persistent badge in the top header (`src/components/layout/ServerStatusBadge.tsx`)
shows what the back-end is doing. The states come from two sources:

1. **Axios request/response interceptors** (`src/lib/api.ts`) emit
   `fetching / connected / error` for every HTTP call.
2. Agent RPC polling exposes queued/running/completed status in the chat UI.
3. A periodic ping (`src/hooks/useServerStatus.ts`) refreshes
   `connected / error` every 30 s.

Stages (`src/lib/types.ts`):

```
idle | connecting | connected | fetching | generating
| querying | executing_e2b | error
```

## Filtering, sorting, search

- `src/components/common/FilterBar.tsx` produces inputs from a `FilterField[]`
  spec (search/text/number/select/boolean).
- `src/components/common/DataTable.tsx` provides column-level sorting and a
  generic `rowKey` for stable rendering.
- `src/hooks/useFilters.ts` keeps the filter object in `useState` and exposes
  a deterministic SWR key.
- `src/hooks/useGames.ts` translates the filter object into the back-end
  query parameters (`/games?search=...&genre=...&sort_by=...`).

## Chat

The UI has one workflow only: `/agent-rpc`. It creates, renames and deletes
durable sessions, sends multiple tasks per session, polls run/events, exposes
cancellation and renders persisted MCP chart payloads with Plotly hover, zoom,
pan and export controls. The dashboard intentionally contains no chat panel.

## Talking to the back-end

All requests go through one environment variable:

```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
```

`src/lib/api.ts` reads this, attaches the Bearer access token from the auth
store, and refreshes it once on a `401` via `/auth/refresh`.

## Local development

Start the complete stack from the repository root:

```powershell
.\scripts\start_local_stack.ps1
```

This is the recommended path because the API on `8000` requires the internal
MCP tool server on `8001`. The browser communicates only with `8000`; it never
needs the MCP shared secret.

To start only Next.js against backend services that are already running:

```bash
cd front_end
npm install
cp .env.local.example .env.local       # then point to your BE URL
npm run dev                            # http://localhost:3000
```

Make sure MCP is running on port `8001` and the product API is running on port
`8000` (see `../back_end/README.md`).

## Deploying to Vercel

1. Push the front-end code to this repo's `front_end/` directory.
2. In Vercel: **Add New -> Project -> Import Git Repository**.
3. Set **Root Directory** to `front_end`.
4. Vercel auto-detects Next.js. Override the build command if needed (`next build`).
5. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = the public URL of the back-end.
6. Click **Deploy**. Vercel issues `https://<project>.vercel.app` immediately.

Subsequent pushes to `main` automatically trigger a new Vercel deployment.

## Current boundaries

- The admin page lists users only; role assignment UI remains separate.
- Agent events are incrementally polled so Bearer authentication works across
  Vercel/backend origins. The backend SSE endpoint remains available.
