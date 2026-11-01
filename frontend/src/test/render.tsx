import type { ReactElement, ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";
import { ToastProvider } from "../components/ui/Toast";

/**
 * A fresh QueryClient per test — a shared one would leak a resolved `me` from
 * one test into the next — and retries off so a deliberate failure is
 * immediate rather than a timeout.
 */
export function renderWithProviders(ui: ReactElement, { route = "/" } = {}) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ToastProvider>
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </QueryClientProvider>
      </ToastProvider>
    );
  }

  return { client, ...render(ui, { wrapper: Wrapper }) };
}
