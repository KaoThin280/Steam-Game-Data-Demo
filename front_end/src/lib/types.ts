/**
 * Shared TypeScript types mirroring the back-end schema.
 * Keep this file in sync with back_end/app/schemas/* and SCHEMA_DOCUMENTATION.md.
 */

// ---------- Auth ----------
export type RoleName = "admin" | "analyst" | "scientist" | "viewer";

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  roles: RoleName[];
  permissions?: string[];
  created_at: string | null;
  last_login: string | null;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  confirm_password: string;
  full_name?: string;
}

// ---------- Games ----------
// NOTE: schema backend đã loại bỏ các cột CSV
// (supported_languages / categories / genres) khỏi bảng public.games
// để tiết kiệm storage. FE không còn hiển thị / lọc theo các field này.
export interface Game {
  steam_appid: number;
  name: string;
  is_free: boolean;
  required_age: number;
  release_date: string | null;
  publishers: string | null;
  developers: string | null;
  price_text: string | null;
  created_at: string | null;
  /** Genre names from game_genres junction table (populated by backend). */
  genres: string[];
}

export interface GameFilter {
  search?: string;
  genre?: string;
  category?: string;
  developer?: string;
  publisher?: string;
  is_free?: boolean;
  year?: number;
  sort_by?: "release_date" | "name" | "required_age";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Review {
  recommendationid: number;
  steam_appid: number;
  steamid: number;
  language: string | null;
  review_text: string | null;
  timestamp_created: string | null;
  timestamp_updated: string | null;
  refunded: boolean;
  received_for_free: boolean;
  written_during_early_access: boolean;
  primarily_steam_deck: boolean;
  playtime_at_review: number;
  playtime_last_two_weeks: number;
  playtime_forever: number;
  created_at: string | null;
}

export interface ReviewFilter {
  language?: string;
  refunded?: boolean;
  received_for_free?: boolean;
  primarily_steam_deck?: boolean;
  min_playtime_forever?: number;
  page?: number;
  page_size?: number;
}

// ---------- Dashboard ----------
export interface OverviewStats {
  total_games: number;
  total_reviews: number;
  free_games: number;
  paid_games: number;
  total_developers: number;
  total_languages: number;
}

export interface DistributionItem {
  label?: string;
  genre?: string;
  language?: string;
  year?: number;
  count: number;
}

// ---------- AI agent (charting + execute_query) ----------
export type ServerStage =
  | "idle"
  | "connecting"
  | "connected"
  | "generating"
  | "querying"
  | "executing_e2b"
  | "fetching"
  | "error";

export interface AiToolCall {
  name: "execute_query" | "charting";
  arguments: Record<string, unknown>;
}

export interface AiToolResult {
  columns?: string[];
  rows?: unknown[][];
  row_count?: number;
  truncated?: boolean;
  chart_id?: number;
  chart_type?: string;
  chart_title?: string;
  error?: string;
}

export interface AiChartSpec {
  chart_type: string;
  chart_title: string;
  x_axis_label?: string | null;
  y_axis_label?: string | null;
  series_label?: string | null;
  config: {
    labels: string[];
    datasets: Array<{ label: string; data: number[]; [k: string]: unknown }>;
    options?: Record<string, unknown>;
  };
  source_query?: string | null;
  notes?: string | null;
  chart_id?: number;
}

/**
 * A Plotly figure spec (the raw {data: [...], layout: {...}} dict).
 * 
 * Backend returns this directly in `plotly_specs` — a JSON-serialized
 * Plotly figure generated via fig.to_json() / fig.to_dict() in Python.
 */
export type PlotlySpec = Record<string, unknown>;

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  /**
   * Rendered charts (Chart.js specs). Backend may attach these even
   * though the raw tool_calls are hidden.
   */
  charts?: AiChartSpec[];
  /**
   * Sandbox-generated Plotly figures as JSON specs (the result of
   * fig.to_dict() / fig.to_json() in Python). Rendered directly via
   * react-plotly.js (no iframe, no CSP / X-Frame-Options issues).
   */
  plotlySpecs?: PlotlySpec[];
  /**
   * Optional title for the latest Plotly figure.
   */
  plotlyTitle?: string;
  /**
   * Sandbox-generated files (.html = legacy interactive Plotly iframe,
   * .png = static image) accessible at /api/v1/temp_data/{filename}.
   */
  sandboxFiles?: string[];
  /**
   * Workflow events captured for this message (tool calls, LLM steps,
   * errors). Shown inline as a collapsible progress timeline.
   */
  workflowEvents?: WorkflowEvent[];
  /**
   * @deprecated Internal-only. Kept for backwards compatibility; the
   * server no longer populates this field.
   */
  tool_calls?: Array<{ name: string; result: unknown }>;
  created_at?: string;
}

export interface ChatSession {
  session_id: string;
  last_active?: string | null;
}

export interface ChatRequestPayload {
  message: string;
  session_id?: string;
}

/**
 * Response from POST /api/v1/ai/chat (SQL + Chart agent).
 * The user only sees `reply` (natural-language) and `charts` (rendered
 * Chart.js specs). Internal `tool_calls` are intentionally omitted from
 * the server response.
 */
export interface WorkflowEvent {
  stage: string;
  message: string;
  type: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  charts: AiChartSpec[];
  plotly_specs?: PlotlySpec[];
  plotly_title?: string;
  sandbox_files: string[];
  workflow_events: WorkflowEvent[];
  status?: "success" | "error";
}

// ---------- Durable Agent Harness RPC ----------
export type AgentRunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface AgentSessionSummary {
  session_id: string;
  title: string | null;
  status: "active" | "archived";
  updated_at: string;
}

export interface AgentRunSummary {
  run_id: string;
  input: string;
  output: string | null;
  status: AgentRunStatus;
  created_at: string;
}

export interface AgentSessionDetail extends AgentSessionSummary {
  runs: AgentRunSummary[];
}

export interface AgentChartPayload {
  type: string;
  title: string;
  x: string[];
  y: number[];
  x_label?: string;
  y_label?: string;
}

export interface AgentEvent {
  sequence: number;
  type: string;
  payload: {
    step?: number;
    name?: string;
    answer?: string;
    code?: string;
    message?: string;
    result?: { content?: { chart?: AgentChartPayload; truncated?: boolean } };
  };
  created_at: string;
}

export interface AgentRunDetail {
  run_id: string;
  session_id: string;
  status: AgentRunStatus;
  current_step: number;
  max_steps: number;
  output: string | null;
  error: { code: string; message: string } | null;
  cancel_requested: boolean;
}
