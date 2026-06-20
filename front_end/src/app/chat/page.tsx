"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default function ChatPage() {
  return (
    <RoleGuard allow={["analyst", "scientist", "admin"]}>
      <div className="grid h-[calc(100vh-7rem)] grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="flex min-w-0 flex-col gap-3">
          <header>
            <h1 className="text-2xl font-semibold">AI Chat</h1>
            <p className="text-sm text-white/60">
              Two modes are available: <b>SQL + Chart</b> (default) for fast
              read-only queries against the PostgreSQL database, or <b>Python
              (E2B)</b> for code execution in a sandbox when you need
              pandas/matplotlib.
            </p>
          </header>
          <div className="min-h-[480px] flex-1">
            <ChatWindow defaultMode="agent" />
          </div>
        </section>
        <section className="flex min-w-0 flex-col gap-3">
          <header>
            <h2 className="text-lg font-semibold">Python sandbox (E2B)</h2>
            <p className="text-sm text-white/60">
              Use a separate session for code execution. Files generated in the
              sandbox are listed under <code className="rounded bg-white/10 px-1">temp_data/</code>.
            </p>
          </header>
          <div className="min-h-[480px] flex-1">
            <ChatWindow defaultMode="e2b" />
          </div>
        </section>
      </div>
    </RoleGuard>
  );
}
