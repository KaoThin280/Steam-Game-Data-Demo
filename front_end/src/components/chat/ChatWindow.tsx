"use client";

import { useEffect, useRef, useState } from "react";
import { Eraser, Send } from "lucide-react";

import { ChatMessage } from "@/components/chat/ChatMessage";
import { useChat } from "@/hooks/useChat";
import { classNames } from "@/utils/format";

interface ChatWindowProps {
  /** Optional fixed-height container. Default fills its parent. */
  className?: string;
}

export function ChatWindow({ className }: ChatWindowProps) {
  const { messages, send, reset, isSending, workflowEvents } = useChat();
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const submit = async () => {
    const text = draft.trim();
    if (!text || isSending) return;
    setDraft("");
    await send(text);
  };

  return (
    <div
      className={classNames(
        "flex h-full min-h-[480px] flex-col rounded-md border border-white/10 bg-bg/60",
        className
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-white/5 px-3 py-2 text-xs">
        <span className="text-white/70">Ask the AI to query, analyse, or visualise Steam data</span>
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-[11px] text-white/70 hover:bg-white/5"
        >
          <Eraser className="h-3 w-3" />
          Reset
        </button>
      </header>

      <div ref={listRef} className="flex-1 overflow-y-auto px-3 py-3">
        {messages.length === 0 && (
          <div className="grid h-full place-items-center text-sm text-white/40">
            Ask anything about Steam games, reviews, or statistics.
            <br />
            Try: "Top 10 genres by count", or "Monthly reviews trend for 2023",
            or "Analyse review sentiment for top games".
          </div>
        )}
        {messages.map((m, i) => (
          <ChatMessage key={i} message={m} />
        ))}
        {isSending && (
          <div className="my-2 inline-flex items-center gap-2 rounded-md border border-white/10 bg-bg-soft px-3 py-2 text-xs text-white/60">
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
            Analysing data, running code, generating response...
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex gap-2 border-t border-white/5 p-2"
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          placeholder="Ask the AI to query, chart, or analyse Steam data..."
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          className="flex-1 resize-none rounded-md border border-white/10 bg-bg-soft px-3 py-2 text-sm focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={isSending || !draft.trim()}
          className="inline-flex items-center gap-1 self-end rounded-md border border-accent/40 bg-accent/20 px-3 py-2 text-sm text-accent hover:bg-accent/30 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          <span>Send</span>
        </button>
      </form>
    </div>
  );
}