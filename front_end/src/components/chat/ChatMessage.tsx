"use client";

import { useState } from "react";
import { Bot, User, AlertCircle, FileText, ChevronDown, ChevronRight, ListChecks } from "lucide-react";

import { ChartRenderer } from "@/components/analytics/ChartRenderer";
import { PlotlyHtmlRenderer } from "@/components/Renderers/PlotlyHtmlRenderer";
import { DataTableViewer } from "@/components/Renderers/DataTableViewer";
import { VisualizationViewer } from "@/components/Renderers/VisualizationViewer";
import { WorkflowProgress } from "@/components/chat/WorkflowProgress";
import type { ChatMessage as Msg } from "@/lib/types";
import { classNames } from "@/utils/format";

interface ChatMessageProps {
  message: Msg;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * A single chat bubble.
 * - user: right-aligned, accent border
 * - assistant: left-aligned, shows reply text and any rendered charts / sandbox files
 * - system: warning style
 *
 * Sandbox files:
 *   .html -> rendered inside an interactive iframe (Plotly interactive charts)
 *   .png  -> rendered as an image (static charts)
 *   .csv  -> shown as a download link
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

        {/* Workflow progress — collapsible timeline for assistant messages */}
        {!isUser && message.workflowEvents && message.workflowEvents.length > 0 && (
          <WorkflowTimeline events={message.workflowEvents} />
        )}

        {/* VisualizationViewer — groups charts, HTML, PNG into tabs/carousel */}
        <VisualizationViewer
          charts={message.charts}
          plotlySpecs={message.plotlySpecs}
          plotlyTitle={message.plotlyTitle}
          sandboxFiles={message.sandboxFiles}
        />

        {/* CSV files → DataTableViewer (sort + pagination) */}
        {message.sandboxFiles && message.sandboxFiles.filter(f => f.endsWith('.csv')).length > 0 && (
          <div className="space-y-3">
            {message.sandboxFiles
              .filter(f => f.endsWith('.csv'))
              .map((filename, i) => (
                <DataTableViewer
                  key={i}
                  filename={filename}
                  title={filename}
                />
              ))}
          </div>
        )}

        {/* Other files (txt, json, etc.) → download links */}
        {message.sandboxFiles && message.sandboxFiles.filter(
          f => !f.endsWith('.html') && !f.endsWith('.png') && !f.endsWith('.csv')
        ).length > 0 && (
          <div className="space-y-2">
            {message.sandboxFiles
              .filter(f => !f.endsWith('.html') && !f.endsWith('.png') && !f.endsWith('.csv'))
              .map((filename, i) => (
                <div key={i} className="rounded-md border border-white/5 bg-bg/60 p-2">
                  <div className="flex items-center gap-2 text-xs font-medium text-white/70">
                    <FileText className="h-3.5 w-3.5" />
                    <span>{filename}</span>
                    <a
                      href={`${API_BASE}/temp_data/${filename}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto text-accent hover:underline"
                    >
                      Download
                    </a>
                  </div>
                </div>
              ))}
          </div>
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

function WorkflowTimeline({ events }: { events: import("@/lib/types").WorkflowEvent[] }) {
  const [collapsed, setCollapsed] = useState(false);

  // Count errors and tools
  const toolCount = events.filter(e => e.stage === "tool_call").length;
  const errorCount = events.filter(e => e.type === "error").length;

  return (
    <div className="mt-2 border border-white/10 rounded-md overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-xs text-white/60 hover:bg-white/5 transition-colors"
      >
        {collapsed ? (
          <ChevronRight className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
        <ListChecks className="h-3 w-3" />
        <span>{toolCount} tool{toolCount !== 1 ? "s" : ""}</span>
        {errorCount > 0 && (
          <span className="text-red-400">({errorCount} error{errorCount !== 1 ? "s" : ""})</span>
        )}
      </button>
      {!collapsed && (
        <div className="px-1 pb-1">
          <WorkflowProgress events={events} isActive={false} />
        </div>
      )}
    </div>
  );
}
