"use client";
import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/hooks/use-auth";
import { PreferencesProvider } from "@/hooks/use-preferences";
import { PageMotionProvider } from "@/hooks/use-page-motion";
import { WorkspaceToolsProvider } from "@/components/workspace-tools";
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
            <WorkspaceToolsProvider>{children}</WorkspaceToolsProvider>
          </AuthProvider>
        </PageMotionProvider>
      </PreferencesProvider>
    </QueryClientProvider>
  );
}
