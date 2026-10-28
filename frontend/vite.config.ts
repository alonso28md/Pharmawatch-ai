import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: the app talks to /api/*, proxied to the FastAPI backend (root paths).
// Mock mode (`--mode mock`): MSW answers /api/* in the browser; no backend needed.
// Production build: served by FastAPI under /app and calls the API on the same origin.
export default defineConfig(({ command, isPreview }) => ({
  plugins: [react(), tailwindcss()],
  base: command === "build" || isPreview ? "/app/" : "/",
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  // No data: URIs: the backend's CSP is `default-src 'self'`, which blocks inlined fonts/images.
  build: { assetsInlineLimit: 0 },
  server: {
    // Mock mode imports the versioned evaluation summary from ../docs/results.
    fs: { allow: [".."] },
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.PHARMAWATCH_BACKEND ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
}));
