"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default function ChatPage() {
  return (
    <RoleGuard allow={["analyst", "scientist", "admin"]}>
      <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-4xl flex-col gap-3">
        <header>
          <h1 className="text-2xl font-semibold">AI Chat</h1>
          <p className="text-sm text-white/60">
            Ask the AI to query the database, analyse data, create charts, or
            run Python code — all in one conversation.
          </p>
        </header>
        <div className="min-h-[480px] flex-1">
          <ChatWindow />
        </div>
      </div>
    </RoleGuard>
  );
}