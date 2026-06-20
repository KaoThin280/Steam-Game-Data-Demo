"use client";

import { create } from "zustand";

import type { ServerStage } from "@/lib/types";

interface ServerStatusState {
  stage: ServerStage;
  detail: string | null;
  lastError: string | null;
  // Reset whenever a new request starts so the badge animates correctly.
  setStage: (stage: ServerStage, detail?: string) => void;
  setError: (msg: string | null) => void;
}

export const useServerStatusStore = create<ServerStatusState>((set) => ({
  stage: "idle",
  detail: null,
  lastError: null,
  setStage: (stage, detail) =>
    set({
      stage,
      detail: detail ?? null,
      lastError: stage === "error" ? detail ?? "Unknown error" : null,
    }),
  setError: (msg) => set({ lastError: msg, stage: msg ? "error" : "idle" }),
}));
