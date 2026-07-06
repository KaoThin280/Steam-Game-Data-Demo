/**
 * Axios-based API client.
 *
 * - Reads base URL from NEXT_PUBLIC_API_URL.
 * - Attaches Bearer access_token from the auth store on every request.
 * - On 401, tries a single refresh via /auth/refresh before failing.
 * - Emits server-stage transitions through onStageChange (used by the
 *   server-status store / badge).
 */
import axios, { AxiosError, AxiosRequestConfig } from "axios";

import { useAuthStore } from "@/store/authStore";
import { useServerStatusStore } from "@/store/serverStatusStore";
import type { AuthTokens, ServerStage } from "@/lib/types";

const baseURL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL,
  timeout: 60_000,
  withCredentials: true, // Send httpOnly cookies on same-origin / CORS
});

// Listeners can subscribe to stage changes for a richer status UI.
type StageListener = (stage: ServerStage, detail?: string) => void;
const stageListeners = new Set<StageListener>();
export const onStageChange = (cb: StageListener) => {
  stageListeners.add(cb);
  return () => stageListeners.delete(cb);
};
const emitStage = (stage: ServerStage, detail?: string) => {
  useServerStatusStore.getState().setStage(stage, detail);
  stageListeners.forEach((cb) => cb(stage, detail));
};

// Map axios lifecycle -> ServerStage.
api.interceptors.request.use((cfg) => {
  // Skip stage emission for the dedicated status ping path to avoid
  // re-rendering the whole app on every periodic ping.
  if (!cfg.url?.includes("/dashboard/overview")) {
    emitStage("fetching", cfg.url);
  }
  const access = useAuthStore.getState().accessToken;
  if (access) {
    cfg.headers = cfg.headers ?? {};
    (cfg.headers as Record<string, string>).Authorization = `Bearer ${access}`;
  }
  return cfg;
});

api.interceptors.response.use(
  (res) => {
    if (!res.config.url?.includes("/dashboard/overview")) {
      emitStage("connected");
    }
    return res;
  },
  async (err: AxiosError) => {
    const original = err.config as AxiosRequestConfig & { _retry?: boolean };
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refresh = useAuthStore.getState().refreshToken;
        if (!refresh) throw err;
        // IMPORTANT: use `api` instance (not the bare `axios`) so that
        // withCredentials is honoured - the BE sets the refreshed
        // access_token cookie on this response, and we need the browser
        // to accept it.
        const { data } = await api.post<AuthTokens>(
          `${baseURL}/auth/refresh`,
          { refresh_token: refresh }
        );
        useAuthStore.getState().setTokens(data);
        (original.headers as Record<string, string> | undefined) ??= {};
        (original.headers as Record<string, string>).Authorization =
          `Bearer ${data.access_token}`;
        return api.request(original);
      } catch {
        useAuthStore.getState().clear();
        // Redirect to login page on auth failure (client-side only)
        if (typeof window !== "undefined") {
          const currentPath =
            window.location.pathname + window.location.search;
          if (
            currentPath !== "/login" &&
            currentPath !== "/register" &&
            !currentPath.startsWith("/login?")
          ) {
            // Use backticks so the template literal interpolates correctly.
            window.location.href = `/login?redirect=${encodeURIComponent(
              currentPath
            )}`;
          }
        }
      }
    }
    emitStage("error", err.message);
    throw err;
  }
);

// Helper wrappers used by hooks.
export const apiGet = async <T>(url: string, params?: Record<string, unknown>): Promise<T> => {
  const r = await api.get<T>(url, { params });
  return r.data;
};

export const apiPost = async <T, B = unknown>(url: string, body?: B, timeout?: number): Promise<T> => {
  const r = await api.post<T>(url, body, timeout ? { timeout } : undefined);
  return r.data;
};

export const apiDelete = async <T>(url: string): Promise<T> => {
  const r = await api.delete<T>(url);
  return r.data;
};

// Stage helpers exposed for chat / E2B flows that need finer control.
export const setStage = (stage: ServerStage, detail?: string) => emitStage(stage, detail);
