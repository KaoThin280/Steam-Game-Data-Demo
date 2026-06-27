"use client";

import { useCallback, useState } from "react";

import { apiPost, setStage } from "@/lib/api";
import type {
  ChatMessage,
  ChatRequestPayload,
  ChatResponse,
  WorkflowEvent,
} from "@/lib/types";

/**
 * Unified chat hook — calls /ai/chat which has all 5 tools.
 * Tracks workflow events for real-time progress display.
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [workflowEvents, setWorkflowEvents] = useState<WorkflowEvent[]>([]);

  const reset = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setWorkflowEvents([]);
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      const userMsg: ChatMessage = { role: "user", content: text };
      setMessages((m) => [...m, userMsg]);
      setIsSending(true);
      setWorkflowEvents([]);

      const payload: ChatRequestPayload = {
        message: text,
        session_id: sessionId ?? undefined,
      };

      try {
        setStage("generating", "/ai/chat");
        const r = await apiPost<ChatResponse>("/ai/chat", payload, 180000); // 3 min timeout for E2B + retries
        setSessionId(r.session_id);
        setWorkflowEvents(r.workflow_events || []);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: r.reply,
            charts: r.charts,
            sandboxFiles: r.sandbox_files,
          },
        ]);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Chat failed";
        setMessages((m) => [
          ...m,
          { role: "system", content: `[Error] ${msg}` },
        ]);
      } finally {
        setIsSending(false);
        setStage("connected");
      }
    },
    [sessionId]
  );

  return { messages, sessionId, isSending, workflowEvents, send, reset };
}