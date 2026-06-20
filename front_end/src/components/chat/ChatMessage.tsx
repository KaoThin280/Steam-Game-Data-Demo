"use client";

import { Bot, User, AlertCircle } from "lucide-react";

import { ChartRenderer } from "@/components/analytics/ChartRenderer";
import type { ChatMessage as Msg } from "@/lib/types";
import { classNames } from "@/utils/format";

interface ChatMessageProps {
  message: Msg;
}

/**
 * A single chat bubble.
 * - user: right-aligned, accent border
 * - assistant: left-aligned, shows reply text and any rendered charts
 * - system: warning style
 */
export function ChatMessage({ message }: ChatMessageProps) {
  if (message.role === "system") {
    return (
      <div className="my-2 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    );
  }

  const isUser = message.role === "user";

  return (
    <div
      className={classNames(
        "my-2 flex items-start gap-2",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/20 text-accent">
          <Bot className="h-4 w-4" />
        </div>
      )}
      <div
        className={classNames(
          "max-w-[85%] space-y-3 rounded-md p-3 text-sm leading-relaxed",
          isUser
            ? "rounded-tr-sm border border-accent/30 bg-accent/10"
            : "rounded-tl-sm border border-white/10 bg-bg-soft"
        )}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>

        {message.charts && message.charts.length > 0 && (
          <div className="space-y-4">
            {message.charts.map((chart, i) => (
              <div
                key={i}
                className="rounded-md border border-white/5 bg-bg/60 p-2"
              >
                <div className="mb-1 text-xs font-medium text-white/70">
                  {chart.chart_title}
                </div>
                <ChartRenderer spec={chart} height={260} />
              </div>
            ))}
          </div>
        )}

        {message.tool_calls && message.tool_calls.length > 0 && (
          <details className="text-[11px] text-white/50">
            <summary className="cursor-pointer">
              {message.tool_calls.length} tool call(s)
            </summary>
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-bg/60 p-2 font-mono text-[10px]">
              {JSON.stringify(message.tool_calls, null, 2)}
            </pre>
          </details>
        )}
      </div>
      {isUser && (
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/10 text-white/80">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}
