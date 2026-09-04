"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AgentChatWorkspace } from "@/components/chat/AgentChatWorkspace";

export default function ChatPage() {
  return (
    <RoleGuard allow={["analyst", "scientist", "admin"]}>
      <div className="mx-auto h-[calc(100vh-7rem)] max-w-[1600px] overflow-hidden">
        <AgentChatWorkspace />
      </div>
    </RoleGuard>
  );
}
