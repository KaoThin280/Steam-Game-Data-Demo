"use client";

import { Loader2, CheckCircle2, AlertCircle, Cpu, Database, BarChart3, FileSearch, Sparkles } from "lucide-react";
import type { WorkflowEvent } from "@/lib/types";
import { classNames } from "@/utils/format";

interface WorkflowProgressProps {
  events: WorkflowEvent[];
  isActive: boolean;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  EXECUTE_QUERY: <Database className="h-3.5 w-3.5" />,
  CHARTING: <BarChart3 className="h-3.5 w-3.5" />,
  EXECUTE_PYTHON_CODE: <Cpu className="h-3.5 w-3.5" />,
  LIST_DATA_FILES: <FileSearch className="h-3.5 w-3.5" />,
  GET_DATA_CONTEXT: <FileSearch className="h-3.5 w-3.5" />,
};

const STAGE_ICONS: Record<string, React.ReactNode> = {
  init: <Sparkles className="h-3.5 w-3.5" />,
  llm: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
  tool: <Cpu className="h-3.5 w-3.5" />,
  result: <CheckCircle2 className="h-3.5 w-3.5" />,
  error: <AlertCircle className="h-3.5 w-3.5" />,
  final: <CheckCircle2 className="h-3.5 w-3.5" />,
};

const TOOL_LABELS: Record<string, string> = {
  EXECUTE_QUERY: "Running SQL query",
  CHARTING: "Creating chart",
  LIST_DATA_FILES: "Listing data files",
  GET_DATA_CONTEXT: "Analysing data structure",
  EXECUTE_PYTHON_CODE: "Executing Python code",
};

function getToolKey(msg: string): string | null {
  for (const tool of Object.keys(TOOL_LABELS)) {
    if (msg.includes(tool)) return tool;
  }
  return null;
}

function getEventIcon(event: WorkflowEvent, isSettled: boolean): React.ReactNode {
  const msg = event.message || "";
  const tool = getToolKey(msg);

  // If settled and was a tool, keep the icon but remove animation
  if (isSettled && tool && tool in TOOL_ICONS) {
    return TOOL_ICONS[tool];
  }
  if (tool && tool in TOOL_ICONS) {
    return TOOL_ICONS[tool];
  }

  // If "llm" and settled, show a static sparkle instead of spinning
  if (event.stage === "llm" && isSettled) {
    return <Sparkles className="h-3.5 w-3.5" />;
  }

  return STAGE_ICONS[event.stage] || <Loader2 className="h-3.5 w-3.5" />;
}

function getEventLabel(event: WorkflowEvent): string {
  const msg = event.message || "";
  const tool = getToolKey(msg);
  if (tool) return TOOL_LABELS[tool];
  return msg;
}

export function WorkflowProgress({ events, isActive }: WorkflowProgressProps) {
  if (events.length === 0 && !isActive) return null;

  return (
    <div className="my-2 space-y-1">
      {events.map((event, i) => {
        const isLatest = i === events.length - 1;
        const isError = event.type === "error";
        const isDone = event.type === "done";
        // Check if any *later* event in the list is terminal (done/error)
        const isSettled = events.slice(i).some((e) => e.type === "done" || e.type === "error");
        const isAnimating = isLatest && isActive && !isSettled;

        let bgClass = "bg-white/5 text-white/60 border border-white/5";
        if (isError) {
          bgClass = "bg-red-500/10 text-red-300 border border-red-500/20";
        } else if (isDone) {
          bgClass = "bg-green-500/10 text-green-300 border border-green-500/20";
        } else if (isAnimating) {
          bgClass = "bg-accent/10 text-accent border border-accent/20 animate-pulse";
        }

        return (
          <div key={i} className={classNames("flex items-center gap-2 rounded-md px-3 py-1.5 text-xs transition-all duration-300", bgClass)}>
            <span className="shrink-0">{getEventIcon(event, isSettled)}</span>
            <span className="flex-1 leading-relaxed">{getEventLabel(event)}</span>
            {isDone && <CheckCircle2 className="h-3 w-3 shrink-0 text-green-400" />}
            {isError && <AlertCircle className="h-3 w-3 shrink-0 text-red-400" />}
          </div>
        );
      })}
    </div>
  );
}