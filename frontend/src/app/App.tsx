import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createBrowserRouter, createMemoryRouter, RouterProvider } from "react-router-dom";
import { ActivityProvider } from "@/app/activity";
import { PreferencesProvider } from "@/app/preferences";
import { TooltipProvider } from "@/components/ui/primitives";
import { makeQueryClient } from "@/app/queryClient";
import { routes } from "@/app/routes";

/** Providers shared by the app and tests. */
export function AppProviders({ children, client }: { children: React.ReactNode; client?: QueryClient }) {
  const [queryClient] = useState(() => client ?? makeQueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <PreferencesProvider>
        <ActivityProvider>
          <TooltipProvider>{children}</TooltipProvider>
        </ActivityProvider>
      </PreferencesProvider>
    </QueryClientProvider>
  );
}

export function App({ initialPath }: { initialPath?: string }) {
  const [router] = useState(() =>
    initialPath
      ? createMemoryRouter(routes, { initialEntries: [initialPath] })
      : createBrowserRouter(routes, { basename: import.meta.env.BASE_URL.replace(/\/$/, "") || "/" }),
  );
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
