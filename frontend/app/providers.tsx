"use client";
import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/hooks/use-auth";
import { PreferencesProvider } from "@/hooks/use-preferences";
import { PageMotionProvider } from "@/hooks/use-page-motion";
import { WorkspaceToolsProvider } from "@/components/workspace-tools";
import { MineralWatchlistProvider } from "@/hooks/use-mineral-watchlist";
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <PreferencesProvider>
        <PageMotionProvider>
          <AuthProvider>
            <MineralWatchlistProvider>
              <WorkspaceToolsProvider>{children}</WorkspaceToolsProvider>
            </MineralWatchlistProvider>
          </AuthProvider>
        </PageMotionProvider>
      </PreferencesProvider>
    </QueryClientProvider>
  );
}
