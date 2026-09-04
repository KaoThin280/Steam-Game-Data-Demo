"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import type { AgentEvent, AgentRunDetail, AgentSessionDetail, AgentSessionSummary } from "@/lib/types";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export function useAgentHarness() {
  const [sessions, setSessions] = useState<AgentSessionSummary[]>([]);
  const [session, setSession] = useState<AgentSessionDetail | null>(null);
  const [events, setEvents] = useState<Record<string, AgentEvent[]>>({});
  const [activeRun, setActiveRun] = useState<AgentRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const polling = useRef(false);

  const loadSessions = useCallback(async () => {
    const rows = await apiGet<AgentSessionSummary[]>("/agent-rpc/sessions");
    setSessions(rows);
    return rows;
  }, []);

  const selectSession = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const detail = await apiGet<AgentSessionDetail>(`/agent-rpc/sessions/${id}`);
      setSession(detail);
      const eventPairs = await Promise.all(detail.runs.map(async (run) => [run.run_id, await apiGet<AgentEvent[]>(`/agent-rpc/runs/${run.run_id}/events`)] as const));
      setEvents(Object.fromEntries(eventPairs));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadSessions().then((rows) => rows[0] && selectSession(rows[0].session_id)).finally(() => setLoading(false));
  }, [loadSessions, selectSession]);

  const createSession = useCallback(async (title: string) => {
    const created = await apiPost<{ session_id: string }>("/agent-rpc/sessions", { title });
    await loadSessions();
    await selectSession(created.session_id);
  }, [loadSessions, selectSession]);

  const deleteSession = useCallback(async (id: string) => {
    await apiDelete(`/agent-rpc/sessions/${id}`);
    setEvents((old) => {
      const next = { ...old };
      for (const run of session?.session_id === id ? session.runs : []) delete next[run.run_id];
      return next;
    });
    const rows = await loadSessions();
    if (session?.session_id === id) {
      const next = rows.find((item) => item.session_id !== id);
      if (next) await selectSession(next.session_id);
      else setSession(null);
    }
  }, [loadSessions, selectSession, session]);

  const renameSession = useCallback(async (id: string, title: string) => {
    const updated = await apiPatch<AgentSessionSummary>(`/agent-rpc/sessions/${id}`, { title });
    setSessions((old) => old.map((item) => item.session_id === id ? updated : item));
    setSession((old) => old?.session_id === id ? { ...old, title: updated.title, updated_at: updated.updated_at } : old);
  }, []);

  const monitor = useCallback(async (runId: string, sessionId: string) => {
    if (polling.current) return;
    polling.current = true;
    let cursor = 0;
    try {
      while (true) {
        const [run, newEvents] = await Promise.all([
          apiGet<AgentRunDetail>(`/agent-rpc/runs/${runId}`),
          apiGet<AgentEvent[]>(`/agent-rpc/runs/${runId}/events`, { after: cursor }),
        ]);
        setActiveRun(run);
        if (newEvents.length) {
          cursor = newEvents[newEvents.length - 1].sequence;
          setEvents((old) => ({ ...old, [runId]: [...(old[runId] ?? []), ...newEvents] }));
        }
        if (TERMINAL.has(run.status)) break;
        await new Promise((resolve) => setTimeout(resolve, 700));
      }
      await selectSession(sessionId);
      await loadSessions();
    } finally {
      polling.current = false;
      setActiveRun(null);
    }
  }, [loadSessions, selectSession]);

  const send = useCallback(async (message: string) => {
    if (!session || activeRun) return;
    const submitted = await apiPost<{ run_id: string; session_id: string }>(`/agent-rpc/sessions/${session.session_id}/tasks`, { message });
    setActiveRun({ run_id: submitted.run_id, session_id: submitted.session_id, status: "queued", current_step: 0, max_steps: 8, output: null, error: null, cancel_requested: false });
    const optimistic = { run_id: submitted.run_id, input: message, output: null, status: "queued" as const, created_at: new Date().toISOString() };
    setSession((old) => old ? { ...old, runs: [...old.runs, optimistic] } : old);
    setEvents((old) => ({ ...old, [submitted.run_id]: [] }));
    void monitor(submitted.run_id, submitted.session_id);
  }, [activeRun, monitor, session]);

  const cancel = useCallback(async () => {
    if (!activeRun) return;
    await apiPost(`/agent-rpc/runs/${activeRun.run_id}/cancel`);
  }, [activeRun]);

  return { sessions, session, events, activeRun, loading, createSession, renameSession, deleteSession, selectSession, send, cancel };
}
