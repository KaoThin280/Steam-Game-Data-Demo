"use client";

import { useAuth } from "@/hooks/useAuth";
import { GameListTable } from "@/components/games/GameListTable";
import { RoleGuard } from "@/components/auth/RoleGuard";

export default function GamesPage() {
  return (
    <RoleGuard allow={["viewer", "analyst", "scientist", "admin"]}>
      <GamesView />
    </RoleGuard>
  );
}

function GamesView() {
  const { user } = useAuth();
  const isViewer = user?.roles?.length === 1 && user.roles[0] === "viewer";

  return (
    <div className="flex flex-col gap-3">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Games</h1>
          <p className="text-sm text-white/60">
            {isViewer
              ? "Browse the Steam game catalogue."
              : "Browse and search games. Click a row to see details and reviews."}
          </p>
        </div>
      </header>
      <GameListTable />
    </div>
  );
}
