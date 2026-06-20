"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Plug,
  Server,
  Terminal,
} from "lucide-react";

import { useServerStatus } from "@/hooks/useServerStatus";
import type { ServerStage } from "@/lib/types";
import { classNames } from "@/utils/format";

const STAGE_META: Record<ServerStage, {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  tone: "ok" | "warn" | "info" | "err";
}> = {
  idle:            { label: "Idle",            icon: Activity,    tone: "info" },
  connecting:      { label: "Connecting",      icon: Plug,        tone: "info" },
  connected:       { label: "Connected",       icon: CheckCircle2, tone: "ok" },
  fetching:        { label: "Fetching",        icon: Loader2,     tone: "info" },
  generating:      { label: "Generating",      icon: Terminal,    tone: "info" },
  querying:        { label: "Querying DB",     icon: Server,      tone: "info" },
  executing_e2b:   { label: "Running on E2B",  icon: Terminal,    tone: "warn" },
  error:           { label: "Error",           icon: AlertTriangle, tone: "err" },
};

const TONE_CLASS: Record<string, string> = {
  ok:   "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  info: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  warn: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  err:  "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

/**
 * Top-bar badge that always reflects what the back-end is doing.
 * - "connected" / "idle" : green dot
 * - "fetching" / "querying" : spinning loader
 * - "generating" / "executing_e2b" : amber pulse
 * - "error" : red with tooltip showing the last error
 */
export function ServerStatusBadge() {
  const { stage, detail, lastError } = useServerStatus();
  const meta = STAGE_META[stage];
  const Icon = meta.icon;
  const spinning = stage === "fetching" || stage === "querying" || stage === "generating" || stage === "connecting";

  return (
    <div
      className={classNames(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs",
        TONE_CLASS[meta.tone]
      )}
      title={lastError ?? detail ?? meta.label}
      data-stage={stage}
    >
      <Icon className={classNames("h-3.5 w-3.5", spinning && "animate-spin")} />
      <span className="font-medium">{meta.label}</span>
      {detail && stage !== "error" && (
        <span className="hidden text-[10px] opacity-70 sm:inline">
          {detail}
        </span>
      )}
    </div>
  );
}
