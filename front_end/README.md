# Front-end - Steam Game Data Demo

The user-facing web application for the project. Deployed on **Vercel** and
talks to the back-end VPS only through the public REST API.

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Framework | **Next.js 14+ (App Router)** | SSR + first-class Vercel support |
| Language | **TypeScript** (strict) | Type-safe contracts that mirror the BE schema |
| Styling | **Tailwind CSS** + custom dark palette | Fast to iterate, tiny CSS payload |
| State (auth + status) | **Zustand** | Tiny, no boilerplate |
| Data fetching | **SWR** | Cache + revalidate, plays well with axios |
| HTTP | **Axios** | Interceptors for auth header + server-status events |
| Charts | **Chart.js + react-chartjs-2** | Renders the AI `charting` tool output as-is |
| Icons | **lucide-react** | Lightweight, tree-shakeable |
| Forms | **react-hook-form + zod** | Type-safe validation |

## Folder layout

```
front_end/
  src/
    app/                       # Next.js App Router
      layout.tsx               # Root layout (Header + Sidebar + status boot)
      page.tsx                 # Entry: redirect to /login or /dashboard or /games
      globals.css              # Tailwind + scrollbar + dark palette
      login/page.tsx           # Login + register (zod-validated forms)
      games/
        page.tsx               # Games list (filter/sort/search + pagination)
        [appid]/page.tsx       # Game detail + reviews (filter/sort/search)
      dashboard/page.tsx       # Analyst/scientist: 2 tabs + chat panel
      chat/page.tsx            # Standalone chat with both modes side-by-side
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
        ChartRenderer.tsx      # Chart.js wrapper for AI charting tool output
        StatsCards.tsx         # Top-row KPI cards
      games/
        GameListTable.tsx      # Filterable/sortable games table
        GameDetailPanel.tsx    # Header + reviews list (filterable)
      chat/
        ChatWindow.tsx         # Mode toggle (SQL+Chart | Python E2B) + bubbles
        ChatMessage.tsx        # Single bubble with chart rendering
      auth/
        RoleGuard.tsx          # Client-side role gate
    hooks/
      useAuth.ts               # login / register / logout / me / hasRole
      useGames.ts              # SWR-backed games + reviews list/detail
      useDashboard.ts          # SWR-backed /dashboard/* endpoints
      useChat.ts               # Chat hook supporting both /ai/chat and /chat
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
| `analyst` | `/dashboard` | Dashboard with 2 tabs (Games / Steam Users) + chat panel |
| `scientist` | `/dashboard` | Same as analyst (analyst chat + dashboard) |
| `admin` | `/dashboard` | Dashboard + chat + `/admin` users/roles management |

`src/components/auth/RoleGuard.tsx` is a client-side gate that wraps protected
pages. The back-end still enforces RBAC via JWT + role checks; the FE guard is
only for UX (redirect before flashing protected content).

## Server-status indicator

A persistent badge in the top header (`src/components/layout/ServerStatusBadge.tsx`)
shows what the back-end is doing. The states come from two sources:

1. **Axios request/response interceptors** (`src/lib/api.ts`) emit
   `fetching / connected / error` for every HTTP call.
2. The chat hook (`src/hooks/useChat.ts`) emits `generating / executing_e2b`
   when the AI is mid-stream.
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

`src/components/chat/ChatWindow.tsx` supports two modes:

| Mode | Endpoint | Tools used | When to use |
| --- | --- | --- | --- |
| **SQL + Chart** | `POST /ai/chat` | `execute_query` + `charting` | Fast read-only answers and Chart.js charts |
| **Python (E2B)** | `POST /chat` | `query_table` + `E2B_EXE` | pandas/matplotlib, file generation in `temp_data/` |

The `/dashboard` page embeds a single chat panel (default `agent` mode). The
`/chat` page embeds both modes side-by-side for power users.

## Talking to the back-end

All requests go through one environment variable:

```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
```

`src/lib/api.ts` reads this, attaches the Bearer access token from the auth
store, and refreshes it once on a `401` via `/auth/refresh`.

## Local development

```bash
cd front_end
npm install
cp .env.local.example .env.local       # then point to your BE URL
npm run dev                            # http://localhost:3000
```

Make sure the back-end is running on port 8000 (see `../back_end/README.md`).

## Deploying to Vercel

1. Push the front-end code to this repo's `front_end/` directory.
2. In Vercel: **Add New -> Project -> Import Git Repository**.
3. Set **Root Directory** to `front_end`.
4. Vercel auto-detects Next.js. Override the build command if needed (`next build`).
5. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = the public URL of the back-end.
6. Click **Deploy**. Vercel issues `https://<project>.vercel.app` immediately.

Subsequent pushes to `main` automatically trigger a new Vercel deployment.

## What is intentionally minimal in this skeleton

- The Steam Users dashboard tab currently reuses `/dashboard/languages` as a
  preview. The dedicated `/dashboard/users` endpoint can be plugged in later
  without touching the page structure.
- The admin page lists users only; role assignment UI is a TODO on top of
  `POST /admin/users/{user_id}/roles`.
- The chat uses REST (not SSE). The `/ai/chat/stream` and `/chat/stream`
  endpoints are already wired in the BE and can replace `useChat.send` later.
