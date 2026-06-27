"use client";

import { useCallback, useEffect } from "react";

import { api, apiGet, apiPost } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import type { AuthTokens, LoginPayload, RegisterPayload, User } from "@/lib/types";

// Module-level flag to prevent duplicate /auth/me calls across hook instances
let _fetchingMe = false;

/**
 * Auth hook:
 *  - hydrates tokens from localStorage on mount
 *  - exposes login / register / logout / fetchMe
 *  - exposes role helpers (hasRole, isAnalyst)
 */
export function useAuth() {
  const {
    accessToken,
    refreshToken,
    user,
    hydrated,
    hydrate,
    setTokens,
    setUser,
    clear,
    hasRole,
  } = useAuthStore();

  useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  // Track in-flight /auth/me to avoid duplicate calls
  useEffect(() => {
    if (hydrated && accessToken && !user && !_fetchingMe) {
      _fetchingMe = true;
      apiGet<User>("/auth/me")
        .then((u) => setUser(u))
        .catch(() => clear())
        .finally(() => { _fetchingMe = false; });
    }
  }, [hydrated, accessToken, user, setUser, clear]);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const tokens = await apiPost<AuthTokens>("/auth/login", payload);
      setTokens(tokens);
      const me = await apiGet<User>("/auth/me");
      setUser(me);
      return me;
    },
    [setTokens, setUser]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      await api.post("/auth/register", payload);
      return login({ email: payload.email, password: payload.password });
    },
    [login]
  );

  const logout = useCallback(async () => {
    try {
      if (refreshToken) await api.post("/auth/logout", { refresh_token: refreshToken });
    } catch {
      /* ignore */
    }
    clear();
  }, [refreshToken, clear]);

  return {
    accessToken,
    user,
    hydrated,
    isAuthenticated: !!accessToken,
    login,
    register,
    logout,
    hasRole,
    isAnalyst: hasRole("admin", "analyst", "scientist"),
    isViewer: hasRole("viewer") && !hasRole("admin", "analyst", "scientist"),
  };
}
