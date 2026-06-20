"use client";

import { create } from "zustand";

import { clearTokens, readAccessToken, readRefreshToken, writeTokens } from "@/lib/auth";
import type { AuthTokens, RoleName, User } from "@/lib/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  hydrated: boolean;
  hydrate: () => void;
  setTokens: (t: AuthTokens) => void;
  setUser: (u: User | null) => void;
  clear: () => void;
  hasRole: (...roles: RoleName[]) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  hydrated: false,

  hydrate: () => {
    const access = readAccessToken();
    const refresh = readRefreshToken();
    set({ accessToken: access, refreshToken: refresh, hydrated: true });
  },

  setTokens: (t) => {
    writeTokens(t.access_token, t.refresh_token);
    set({ accessToken: t.access_token, refreshToken: t.refresh_token });
  },

  setUser: (u) => set({ user: u }),

  clear: () => {
    clearTokens();
    set({ accessToken: null, refreshToken: null, user: null });
  },

  hasRole: (...roles) => {
    const u = get().user;
    if (!u) return false;
    return roles.some((r) => u.roles.includes(r));
  },
}));
