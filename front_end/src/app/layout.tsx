import type { Metadata, Viewport } from "next";

import "./globals.css";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { ServerStatusBoot } from "@/components/layout/ServerStatusBoot";
import { SWRConfig } from "swr";
import { ThemeProvider } from "@/components/layout/ThemeProvider";

export const metadata: Metadata = {
  title: "Steam Game Data Demo",
  description:
    "Browse Steam game metadata, reviews, and analytics with an AI assistant.",
};

export const viewport: Viewport = {
  themeColor: "#f8fafc",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-bg text-fg antialiased">
        <ThemeProvider>
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
        </ThemeProvider>
      </body>
    </html>
  );
}
