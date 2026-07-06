/**
 * 404 Not Found page - Server Component (SSG).
 */
import Link from "next/link";
import { Home, Gamepad2 } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-md w-full text-center">
        <h1 className="text-6xl font-bold text-white/10 mb-4">404</h1>
        <h2 className="text-lg font-semibold text-white mb-2">
          Trang không tồn tại
        </h2>
        <p className="text-sm text-white/50 mb-6">
          Trang bạn tìm kiếm có thể đã bị xóa hoặc không tồn tại.
        </p>
        <div className="flex gap-3 justify-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            <Home className="h-4 w-4" />
            Trang chủ
          </Link>
          <Link
            href="/games"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-white/10 text-white/70 text-sm font-medium hover:bg-white/5 transition-colors"
          >
            <Gamepad2 className="h-4 w-4" />
            Duyệt game
          </Link>
        </div>
      </div>
    </div>
  );
}