"use client";

import { useCallback, useState } from "react";

import { apiPost, setStage } from "@/lib/api";
import type {
  ChatMessage,
  ChatRequestPayload,
  ChatResponse,
} from "@/lib/types";

/**
 * Unified chat hook — calls /ai/chat which has all 5 tools.
 *
 * Workflow events (tool calls, LLM steps) are attached per-message
 * on the assistant ChatMessage so each bubble can show its own
 * progress inline.
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  const reset = useCallback(() => {
    setMessages([]);
    setSessionId(null);
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      const userMsg: ChatMessage = { role: "user", content: text };
      setMessages((m) => [...m, userMsg]);
      setIsSending(true);

      const payload: ChatRequestPayload = {
        message: text,
        session_id: sessionId ?? undefined,
      };

      try {
        setStage("generating", "/ai/chat");
        const r = await apiPost<ChatResponse>("/ai/chat", payload, 180000); // 3 min timeout for E2B + retries
        setSessionId(r.session_id);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: r.reply,
            charts: r.charts,
            plotlySpecs: r.plotly_specs,
            plotlyTitle: r.plotly_title,
            sandboxFiles: r.sandbox_files,
            workflowEvents: r.workflow_events || [],
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

  return { messages, sessionId, isSending, send, reset };
}
