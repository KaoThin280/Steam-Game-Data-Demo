"use client";

import { useCallback, useEffect } from "react";

import { apiGet, apiPost } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import type { AuthTokens, LoginPayload, RegisterPayload, User } from "@/lib/types";

// Module-level singleton: only ONE /auth/me call is in flight across
// the entire app, even if many components mount useAuth at the same
// time. Subsequent callers attach to the same promise.
let _mePromise: Promise<User | null> | null = null;

async function fetchMeOnce(): Promise<User | null> {
  if (_mePromise) return _mePromise;
  _mePromise = apiGet<User>("/auth/me")
    .then((u) => u)
    .catch(() => null)
    .finally(() => {
      // keep the resolved value briefly so late subscribers still get it
      // immediately; clear on next tick to allow a forced refresh.
      setTimeout(() => {
        _mePromise = null;
      }, 0);
    });
  return _mePromise;
}

/**
 * Auth hook:
 *  - hydrates tokens from localStorage on mount
 *  - exposes login / register / logout
 *  - exposes role helpers (hasRole, isAnalyst, isViewer)
 *  - automatically fetches /auth/me when we have a token but no user yet
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

  // Hydrate tokens from localStorage exactly once.
  useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  // Whenever we have a token but no user, fetch /auth/me exactly once
  // for the whole app. Subscribing to `user` makes the effect run again
  // when the user is set, at which point we just return.
  useEffect(() => {
    if (!hydrated) return;
    if (!accessToken) return;
    if (user) return;

    let cancelled = false;
    fetchMeOnce()
      .then((u) => {
        if (cancelled) return;
        if (u) {
          // Defensive: ensure `roles` is always an array, even if the
          // back-end omits the field for some reason.
          const normalised: User = {
            ...u,
            roles: Array.isArray(u.roles) ? u.roles : [],
          };
          setUser(normalised);
        } else {
          clear();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [hydrated, accessToken, user, setUser, clear]);

  const login = useCallback(
    async (payload: LoginPayload): Promise<User> => {
      const tokens = await apiPost<AuthTokens>("/auth/login", payload);
      setTokens(tokens);
      // Force a fresh /auth/me: clear the module singleton first.
      _mePromise = null;
      const me = await fetchMeOnce();
      if (!me) {
        // Shouldn't happen if login succeeded, but fail safely.
        throw new Error("Failed to load user profile after login");
      }
      setUser(me);
      return me;
    },
    [setTokens, setUser]
  );

  const register = useCallback(
    async (payload: RegisterPayload): Promise<User> => {
      await apiPost("/auth/register", payload);
      return login({ email: payload.email, password: payload.password });
    },
    [login]
  );

  const logout = useCallback(async () => {
    try {
      if (refreshToken) {
        await apiPost("/auth/logout", { refresh_token: refreshToken });
      }
    } catch {
      /* ignore */
    }
    _mePromise = null;
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
