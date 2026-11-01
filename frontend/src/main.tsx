import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { createQueryClient } from "./api/queryClient";
import { ToastProvider } from "./components/ui/Toast";
import "@fontsource-variable/inter";
import "@fontsource-variable/manrope";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/inter";
import "./index.css";

// ToastProvider wraps the query client's provider because the client's global
// error handler publishes into the toast sink the provider registers.
const queryClient = createQueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ToastProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ToastProvider>
  </StrictMode>,
);
