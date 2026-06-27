import type { Metadata, Viewport } from "next";

import "./globals.css";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { ServerStatusBoot } from "@/components/layout/ServerStatusBoot";
import { SWRConfig } from "swr";

export const metadata: Metadata = {
  title: "Steam Game Data Demo",
  description:
    "Browse Steam game metadata, reviews, and analytics with an AI assistant.",
};

export const viewport: Viewport = {
  themeColor: "#0b1220",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-white antialiased">
        <SWRConfig
          value={{
            revalidateOnFocus: false,
            revalidateOnReconnect: false,
            dedupingInterval: 5000,
          }}
        >
          <ServerStatusBoot />
        <Header />
        <div className="flex">
          <Sidebar />
          <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
        </div>
        </SWRConfig>
      </body>
    </html>
  );
}
