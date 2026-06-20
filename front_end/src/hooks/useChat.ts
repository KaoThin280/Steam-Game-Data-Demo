"use client";

import { useCallback, useState } from "react";

import { apiPost, setStage } from "@/lib/api";
import type {
  ChatMessage,
  ChatRequestPayload,
  ChatResponse,
  E2BChatResponse,
} from "@/lib/types";

export type ChatMode = "agent" | "e2b";

interface UseChatOptions {
  defaultMode?: ChatMode;
}

/**
 * Chat hook supporting both the SQL+Chart.js agent (/ai/chat)
 * and the E2B Python workflow (/chat).
 */
export function useChat(opts: UseChatOptions = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [mode, setMode] = useState<ChatMode>(opts.defaultMode ?? "agent");
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
        if (mode === "agent") {
          setStage("generating", "/ai/chat");
          const r = await apiPost<ChatResponse>("/ai/chat", payload);
          setSessionId(r.session_id);
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              content: r.reply,
              charts: r.charts,
              tool_calls: r.tool_calls as ChatMessage["tool_calls"],
            },
          ]);
        } else {
          setStage("executing_e2b", "/chat");
          const r = await apiPost<E2BChatResponse>("/chat", payload);
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              content: r.user_response,
              tool_calls: r.events as unknown as ChatMessage["tool_calls"],
            },
          ]);
        }
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
    [mode, sessionId]
  );

  return { messages, sessionId, mode, setMode, isSending, send, reset };
}
