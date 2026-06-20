"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { GameDetailPanel } from "@/components/games/GameDetailPanel";
import { RoleGuard } from "@/components/auth/RoleGuard";

export default function GameDetailPage() {
  return (
    <RoleGuard allow={["viewer", "analyst", "scientist", "admin"]}>
      <Detail />
    </RoleGuard>
  );
}

function Detail() {
  const params = useParams<{ appid: string }>();
  const appid = Number(params.appid);

  if (!Number.isFinite(appid)) {
    return (
      <div className="p-6 text-sm text-white/60">
        Invalid AppID.
        <div className="mt-2">
          <Link href="/games" className="text-accent hover:underline">
            Back to games
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Link
        href="/games"
        className="inline-flex w-fit items-center gap-1 text-xs text-white/60 hover:text-white"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
        All games
      </Link>
      <GameDetailPanel appid={appid} />
    </div>
  );
}
