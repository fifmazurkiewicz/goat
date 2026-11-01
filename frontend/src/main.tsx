import { ErrorBoundary } from "@sentry/react";
import { initMonitoring } from "./lib/monitoring";
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "@/App";
import "@/index.css";

initMonitoring();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary fallback={<p role="alert">Wystąpił błąd aplikacji. Odśwież stronę.</p>}><App /></ErrorBoundary>
    </QueryClientProvider>
  </React.StrictMode>
);
