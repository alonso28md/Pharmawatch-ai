import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/app/App";
import "@/styles/index.css";

async function start() {
  // Mock mode: MSW answers /api/* in the browser with realistic fixtures (no backend, no model).
  if (import.meta.env.VITE_USE_MOCKS === "true") {
    const { worker } = await import("@/mocks/browser");
    await worker.start({
      onUnhandledFrame: "bypass",
      serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    });
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void start();
