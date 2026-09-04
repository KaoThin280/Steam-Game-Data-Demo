"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Database, Loader2, MessageSquarePlus, Pencil, Plus, Send, Square, Trash2, User, Wrench } from "lucide-react";
import { PlotlyChartRenderer } from "@/components/Renderers/PlotlyChartRenderer";
import { useAgentHarness } from "@/hooks/useAgentHarness";
import { useTheme } from "@/components/layout/ThemeProvider";
import type { AgentChartPayload, AgentEvent } from "@/lib/types";

export function AgentChatWorkspace() {
  const { sessions, session, events, activeRun, loading, createSession, renameSession, deleteSession, selectSession, send, cancel } = useAgentHarness();
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.runs.length, events]);

  const sendDraft = async () => {
    const value = draft.trim();
    if (!value || !session || activeRun) return;
    setDraft("");
    await send(value);
  };
  const submit = async (event: FormEvent) => { event.preventDefault(); await sendDraft(); };

  const addSession = async () => {
    const title = window.prompt("Session name", `Analysis ${sessions.length + 1}`);
    if (title?.trim()) await createSession(title.trim());
  };

  const removeSession = async (id: string, title: string | null) => {
    if (!window.confirm(`Delete "${title || "Untitled conversation"}" and all of its messages? This cannot be undone.`)) return;
    try {
      await deleteSession(id);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Could not delete the conversation");
    }
  };

  const editSession = async (id: string, currentTitle: string | null) => {
    const title = window.prompt("Rename conversation", currentTitle || "Untitled conversation");
    if (!title?.trim() || title.trim() === currentTitle) return;
    try {
      await renameSession(id, title.trim());
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Could not rename the conversation");
    }
  };

  return (
    <div className="grid h-full min-h-0 grid-rows-[minmax(150px,28vh)_minmax(0,1fr)] overflow-hidden rounded-2xl border border-line bg-panel shadow-sm lg:grid-cols-[280px_minmax(0,1fr)] lg:grid-rows-1">
      <aside className="flex min-h-0 flex-col overflow-hidden border-b border-line bg-bg-soft/70 p-3 lg:border-b-0 lg:border-r">
        <button onClick={addSession} className="flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-accent-soft"><Plus className="h-4 w-4" /> New conversation</button>
        <p className="px-2 pb-2 pt-5 text-[11px] font-semibold uppercase tracking-[.14em] text-muted">Recent sessions</p>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain pr-1">
          {sessions.map((item) => <div key={item.session_id} className={`group flex items-center rounded-xl transition ${session?.session_id === item.session_id ? "bg-panel text-accent shadow-sm ring-1 ring-line" : "text-muted hover:bg-panel hover:text-fg"}`}><button onClick={() => selectSession(item.session_id)} className="flex min-w-0 flex-1 items-center gap-3 px-3 py-3 text-left text-sm"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent/10"><MessageSquarePlus className="h-4 w-4" /></span><span className="min-w-0"><span className="block truncate font-medium">{item.title || "Untitled conversation"}</span><span className="block text-[11px] opacity-70">{new Date(item.updated_at).toLocaleString()}</span></span></button><div className="mr-1 flex shrink-0 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100"><button type="button" onClick={() => void editSession(item.session_id, item.title)} className="grid h-8 w-8 place-items-center rounded-lg text-muted transition hover:bg-accent/10 hover:text-accent" aria-label={`Rename ${item.title || "conversation"}`} title="Rename conversation"><Pencil className="h-3.5 w-3.5" /></button><button type="button" onClick={() => void removeSession(item.session_id, item.title)} disabled={!!activeRun && session?.session_id === item.session_id} className="grid h-8 w-8 place-items-center rounded-lg text-muted transition hover:bg-red-500/10 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-20" aria-label={`Delete ${item.title || "conversation"}`} title="Delete conversation"><Trash2 className="h-4 w-4" /></button></div></div>)}
        </div>
      </aside>

      <section className="flex min-h-0 min-w-0 flex-col overflow-hidden">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-line px-5">
          <div className="min-w-0"><h2 className="truncate font-semibold text-fg">{session?.title || "Steam data agent"}</h2><p className="truncate text-xs text-muted">Persistent session · read-only MCP tools</p></div>
          {activeRun && <div className="inline-flex items-center gap-2 rounded-full bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Step {activeRun.current_step}/{activeRun.max_steps}</div>}
        </header>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain bg-bg/40 p-4 md:p-6">
          {loading && <div className="grid h-full place-items-center text-muted"><Loader2 className="h-6 w-6 animate-spin" /></div>}
          {!loading && !session && <EmptyState onCreate={addSession} />}
          {!loading && session?.runs.length === 0 && <WelcomeState />}
          {session?.runs.map((run) => <ConversationTurn key={run.run_id} input={run.input} output={run.output} events={events[run.run_id] ?? []} status={run.run_id === activeRun?.run_id ? activeRun.status : run.status} />)}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={submit} className="shrink-0 border-t border-line bg-panel p-3 md:p-4">
          <div className="mx-auto flex max-w-4xl items-end gap-2 rounded-2xl border border-line bg-bg-soft p-2 shadow-inner focus-within:border-accent/50 focus-within:ring-2 focus-within:ring-accent/10">
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendDraft(); } }} disabled={!session || !!activeRun} rows={2} placeholder={session ? "Ask about games, reviews, trends, or request a chart…" : "Create a conversation to begin"} className="max-h-36 flex-1 resize-none bg-transparent px-3 py-2 text-sm text-fg outline-none placeholder:text-muted" />
            {activeRun ? <button type="button" onClick={cancel} className="inline-flex h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white hover:bg-red-700"><Square className="h-3.5 w-3.5 fill-current" /> Stop</button> : <button type="submit" disabled={!session || !draft.trim()} className="inline-flex h-10 items-center gap-2 rounded-xl bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-soft disabled:opacity-40"><Send className="h-4 w-4" /> Send</button>}
          </div>
          <p className="mt-2 text-center text-[11px] text-muted">Agent responses may be imperfect. Database access is restricted to approved read-only tools.</p>
        </form>
      </section>
    </div>
  );
}

function ConversationTurn({ input, output, events, status }: { input: string; output: string | null; events: AgentEvent[]; status: string }) {
  const charts = useMemo(() => events.flatMap((event) => { const chart = event.payload.result?.content?.chart; return chart ? [chart] : []; }), [events]);
  const toolEvents = events.filter((event) => event.type === "tool.started" || event.type === "tool.finished" || event.type === "run.recovered");
  return <div className="mx-auto max-w-4xl space-y-4">
    <div className="flex justify-end gap-3"><div className="max-w-[82%] rounded-2xl rounded-tr-md bg-accent px-4 py-3 text-sm leading-relaxed text-white shadow-sm whitespace-pre-wrap">{input}</div><Avatar kind="user" /></div>
    <div className="flex items-start gap-3"><Avatar kind="agent" /><div className="min-w-0 max-w-[90%] flex-1 space-y-3">
      {toolEvents.length > 0 && <div className="flex flex-wrap gap-2">{toolEvents.map((event) => <span key={event.sequence} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-panel px-2.5 py-1 text-[11px] text-muted">{event.type.startsWith("tool") ? <Wrench className="h-3 w-3" /> : <Database className="h-3 w-3" />}{event.payload.name || event.type}</span>)}</div>}
      {charts.map((chart, index) => <AgentChart key={`${chart.title}-${index}`} chart={chart} />)}
      {output ? <div className="rounded-2xl rounded-tl-md border border-line bg-panel px-4 py-3 text-sm leading-7 text-fg shadow-sm whitespace-pre-wrap">{output}</div> : <div className="inline-flex items-center gap-2 rounded-2xl border border-line bg-panel px-4 py-3 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin text-accent" /> {status === "queued" ? "Waiting to start…" : "Agent is working…"}</div>}
    </div></div>
  </div>;
}

function AgentChart({ chart }: { chart: AgentChartPayload }) {
  const { theme } = useTheme();
  const foreground = theme === "dark" ? "#e2e8f0" : "#334155";
  const grid = theme === "dark" ? "#334155" : "#e2e8f0";
  const requestedType = (chart.type || "line").toLowerCase();
  const isBar = requestedType === "bar";
  const isScatter = requestedType === "scatter";
  const isArea = requestedType === "area";
  const trace = isBar
    ? { x: chart.x, y: chart.y, type: "bar", name: chart.y_label || "Value", marker: { color: "#2563eb" }, hovertemplate: "%{x}<br>%{y:,}<extra></extra>" }
    : { x: chart.x, y: chart.y, type: "scatter", mode: isScatter ? "markers" : "lines+markers", name: chart.y_label || "Value", line: { color: "#2563eb", width: 2 }, marker: { color: "#2563eb", size: isScatter ? 7 : 4 }, fill: isArea ? "tozeroy" : "none", fillcolor: "rgba(37,99,235,.10)", hovertemplate: "%{x}<br>%{y:,}<extra></extra>" };
  const spec = { data: [trace], layout: { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: foreground }, margin: { l: 60, r: 20, t: 20, b: 60 }, hovermode: isScatter ? "closest" : "x unified", xaxis: { title: chart.x_label, gridcolor: grid, rangeslider: { visible: !isBar && chart.x.length > 100 } }, yaxis: { title: chart.y_label, gridcolor: grid, rangemode: "tozero" }, uirevision: theme } };
  return <div className="rounded-2xl border border-line bg-panel p-4 shadow-sm"><div className="mb-2"><h3 className="font-semibold text-fg">{chart.title}</h3><p className="text-xs text-muted">Hover, zoom, pan, select a range, expand, or download the chart.</p></div><PlotlyChartRenderer height={430} title={chart.title} spec={spec} /></div>;
}

function Avatar({ kind }: { kind: "user" | "agent" }) { return <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${kind === "agent" ? "bg-accent/10 text-accent" : "bg-bg-soft text-muted"}`}>{kind === "agent" ? <Bot className="h-5 w-5" /> : <User className="h-5 w-5" />}</span>; }
function EmptyState({ onCreate }: { onCreate: () => void }) { return <div className="grid h-full place-items-center"><div className="max-w-md text-center"><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-accent/10 text-accent"><MessageSquarePlus /></span><h2 className="mt-4 text-xl font-semibold text-fg">Start a durable conversation</h2><p className="mt-2 text-sm text-muted">Each session keeps its own context, runs and tool events.</p><button onClick={onCreate} className="mt-5 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white">Create conversation</button></div></div>; }
function WelcomeState() { return <div className="mx-auto mt-16 max-w-xl text-center"><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-accent/10 text-accent"><Bot /></span><h2 className="mt-4 text-xl font-semibold text-fg">What would you like to explore?</h2><p className="mt-2 text-sm leading-6 text-muted">Ask for catalogue totals, compare genres, inspect reviews, or generate a monthly release chart.</p></div>; }
